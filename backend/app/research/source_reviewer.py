"""Intelligente, fail-closed beoordeling van bronkandidaten vóór ranking."""
import json
from dataclasses import replace
from typing import Any
from urllib.parse import urlsplit

from ..config import get_settings
from ..pipeline.identity_scope import domain_matches_company
from .query_planner import QueryContext
from .validation import BronValidatie, SourceDocument, valideer_bron


REVIEW_PROMPT = """Je bent een strenge bronreviewer voor een Nederlands
vestigingsregister. Beoordeel uitsluitend of de bron over de gezochte
organisatie gaat en of het bewijs bruikbaar is. Een gelijksoortige naam,
zoekresultaatsnippet, medewerkerprofiel of jaarverslag van een andere
organisatie is altijd een mismatch. Bij twijfel wijs je af.

GEZOCHTE ORGANISATIE
Naam: {naam}
Gemeente: {gemeente}
Officiële website: {website}
Gevraagd verslagjaar: {jaar}
Gewenste metriek: werkzame personen
Gewenste scope: vestiging of Limburg

BRON
URL: {url}
Titel: {titel}
Brontype: {brontype}
Gevonden jaar: {verslagjaar}
Gevonden waarde: {wp}
Eenheid: {eenheid}
Bewijsfragment: {bewijs}
Inhoud uit de bron zelf:
{tekst}

Antwoord uitsluitend met JSON:
{{
  "beslissing": "tonen_aan_reviewer|context_only|afwijzen",
  "identity_class": "exact_entity|same_brand_or_group|possible_match|mismatch|unknown",
  "scope_class": "vestiging|limburg|nederland|concern|unknown",
  "gevonden_organisatie": "naam uit de bron of onbekend",
  "reden": "korte concrete uitleg"
}}

Alleen exact_entity of een aantoonbare same_brand_or_group-relatie mag worden
getoond. possible_match en unknown moeten worden afgewezen. Concern- of
landelijke cijfers zijn hoogstens context_only."""

_ALLOWED_IDENTITIES = {
    "exact_entity", "same_brand_or_group", "possible_match", "mismatch", "unknown",
}
_ALLOWED_SCOPES = {"vestiging", "limburg", "nederland", "concern", "unknown"}
_SOCIAL_DOMAINS = {
    "linkedin.com", "nl.linkedin.com", "be.linkedin.com",
    "facebook.com", "instagram.com", "x.com",
}


def _domain(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


class IntelligentSourceReviewer:
    """Combineert harde regels met een LLM-judge; iedere fout is fail-closed."""

    async def review(
        self,
        context: QueryContext,
        document: SourceDocument,
    ) -> BronValidatie:
        validatie = valideer_bron(document)
        domein = _domain(document.url)
        if domein in _SOCIAL_DOMAINS or any(
            domein.endswith(f".{social}") for social in _SOCIAL_DOMAINS
        ):
            validatie.is_afgewezen = True
            validatie.afwijsredenen.append(
                "sociaal_profiel_geen_primaire_wp_bron"
            )
            return validatie

        if validatie.is_afgewezen:
            return validatie

        if (
            document.wp_gevonden is None
            and not document.bewijsfragment
            and domain_matches_company(
                document.url, document.company_website_url,
            ) is not True
        ):
            validatie.is_afgewezen = True
            validatie.afwijsredenen.append("geen_concreet_wp_bewijs")
            return validatie

        if domain_matches_company(
            document.url, document.company_website_url,
        ) is True:
            validatie.identity_class = "exact_entity"
            validatie.validaties["intelligente_review"] = {
                "beslissing": "tonen_aan_reviewer",
                "identity_class": "exact_entity",
                "scope_class": document.scope_class or "unknown",
                "reden": "Bron staat op het bevestigde officiële domein.",
            }
            return validatie

        try:
            oordeel = await self._llm_review(context, document)
        except Exception as exc:
            oordeel = {
                "beslissing": "afwijzen",
                "identity_class": "unknown",
                "scope_class": "unknown",
                "gevonden_organisatie": "onbekend",
                "reden": f"Review niet betrouwbaar uitgevoerd: {exc}",
            }

        identity = oordeel.get("identity_class", "unknown")
        scope = oordeel.get("scope_class", "unknown")
        beslissing = oordeel.get("beslissing", "afwijzen")
        if identity not in _ALLOWED_IDENTITIES:
            identity = "unknown"
        if scope not in _ALLOWED_SCOPES:
            scope = "unknown"
        if identity not in {"exact_entity", "same_brand_or_group"}:
            beslissing = "afwijzen"
        if beslissing not in {
            "tonen_aan_reviewer", "context_only", "afwijzen",
        }:
            beslissing = "afwijzen"
        if scope in {"nederland", "concern"} and beslissing != "afwijzen":
            beslissing = "context_only"

        reviewed_document = replace(document, scope_class=scope)
        validatie.document = reviewed_document
        validatie.identity_class = identity
        validatie.validaties["intelligente_review"] = {
            **oordeel,
            "beslissing": beslissing,
            "identity_class": identity,
            "scope_class": scope,
        }
        validatie.validaties["scope_is_bruikbaar"] = scope in {
            "vestiging", "limburg",
        }
        if beslissing == "context_only":
            validatie.waarschuwingen.append("alleen_context_geen_wp_voorstel")
        if beslissing == "afwijzen":
            validatie.is_afgewezen = True
            validatie.afwijsredenen.append("intelligente_review_afgewezen")
        return validatie

    async def _llm_review(
        self,
        context: QueryContext,
        document: SourceDocument,
    ) -> dict[str, Any]:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY ontbreekt")
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.responses.create(
            model=settings.openai_model_extraction or settings.openai_model,
            input=REVIEW_PROMPT.format(
                naam=context.naam,
                gemeente=context.gemeente or "onbekend",
                website=context.website_url or "onbekend",
                jaar=context.gevraagd_jaar or "onbekend",
                url=document.url,
                titel=document.titel or "onbekend",
                brontype=document.brontype,
                verslagjaar=document.verslagjaar or "onbekend",
                wp=document.wp_gevonden if document.wp_gevonden is not None else "onbekend",
                eenheid=document.eenheid or "onbekend",
                bewijs=document.bewijsfragment or "geen",
                tekst=(document.tekst or "")[:12000],
            ),
            max_output_tokens=500,
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text)
