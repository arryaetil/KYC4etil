"""Fase B: klopt deze bron wel?

Drie onafhankelijke controles op een gevonden PDF: gaat hij over déze
organisatie (identiteit), is het het organisatiebrede verslag en niet dat van
een deelorgaan, en is hij recent genoeg. Samen vangen ze de duurste foutklasse
af — een keurig ogend getal uit het jaarverslag van een ander."""
import re
import unicodedata

from ..config import get_settings
from ..pipeline.evidence import IdentityClass
from . import fetch, llm
from .jaarverslag_zoeken import _lijkt_jaarverslag
from .naam_matching import _naam_tokens
from .prompts import JAARVERSLAG_SCOPE_PROMPT

settings = get_settings()

async def _classificeer_jaarverslag_bron_identiteit(
    naam: str,
    pdf_url: str | None,
    eerste_paginas: str | None = None,
) -> IdentityClass:
    """Classificeert of een gevonden jaarverslag-PDF waarschijnlijk bij het bedrijf hoort.

    Dit vangt de duurste foutklasse af: een generieke jaarverslag-zoekopdracht die
    een PDF van een ander bedrijf vindt. Brand/group matches blijven toegestaan,
    maar moeten later via scope-reconciliatie beoordeeld worden.
    """
    import unicodedata

    if not pdf_url:
        return IdentityClass.UNKNOWN
    if eerste_paginas is None:
        try:
            eerste_paginas = await fetch._eerste_pdf_paginas(pdf_url)
        except Exception:
            return IdentityClass.UNKNOWN

    tokens = _naam_tokens(naam)
    if not tokens:
        return IdentityClass.UNKNOWN
    if len(tokens) == 1 and tokens[0] in {
        "zorggroep",
        "gemeente",
        "provincie",
        "universiteit",
        "college",
        "ziekenhuis",
    }:
        # Eén generiek organisatiewoord maakt een gelijknamige derde partij
        # nog niet tot exact dezelfde entiteit. Een bevestigd officieel domein
        # wordt al vóór deze inhoudsclassificatie geaccepteerd.
        return IdentityClass.UNKNOWN
    haystack = unicodedata.normalize("NFKD", eerste_paginas).encode("ascii", "ignore").decode("ascii").lower()
    matches = sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", haystack))
    if matches >= min(2, len(tokens)):
        return IdentityClass.EXACT_ENTITY
    if matches == 1:
        return IdentityClass.SAME_BRAND_OR_GROUP
    return IdentityClass.MISMATCH


async def _is_organisatiebreed_jaarverslag(
    naam: str,
    pdf_url: str,
    eerste_paginas: str | None = None,
) -> bool | None:
    """True voor het hoofdverslag, False voor deelorganen, None bij twijfel/falen."""
    from openai import AsyncOpenAI

    try:
        if eerste_paginas is None:
            eerste_paginas = await fetch._eerste_pdf_paginas(pdf_url)
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await llm._create_response(
            client,
            model=llm._extraction_model(),
            input=JAARVERSLAG_SCOPE_PROMPT.format(
                naam=naam,
                bron_url=pdf_url,
                context=eerste_paginas[:12000],
            ),
            max_output_tokens=300,
            text={"format": {"type": "json_object"}},
        )
        data = await llm._parse_json_met_herstel(
            client,
            llm._extraction_model(),
            response.output_text,
        )
    except Exception:
        return None
    scope = (data or {}).get("document_scope")
    if scope == "organization_wide":
        return True
    if scope in {"subentity_or_body", "not_annual_report"}:
        return False
    return None


async def _pdf_is_recent_jaarverslag(
    pdf_url: str,
    jaar: int,
) -> bool:
    try:
        eerste_paginas = await fetch._eerste_pdf_paginas(pdf_url)
    except Exception:
        return False
    return any(
        _lijkt_jaarverslag(
            eerste_paginas,
            verslagjaar,
            weiger_deelrapporten=False,
        )
        for verslagjaar in (jaar - 1, jaar - 2, jaar - 3)
    )

