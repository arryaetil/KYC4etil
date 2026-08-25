"""Identiteit- en scopeclassificatie van een gevonden bron.

Twee vragen, in deze volgorde: gaat deze bron über­haupt over de gevraagde
organisatie (identity), en zo ja — voor welk geheel geldt het getal (scope)?
Een bevestigd eigen domein beantwoordt de eerste vraag zonder LLM-call."""
from ..config import get_settings
from ..pipeline.evidence import IdentityClass, ScopeClass
from ..pipeline.identity_scope import domain_matches_company
from . import llm
from .prompts import IDENTITY_EN_SCOPE_PROMPT, SCOPE_PROMPT

settings = get_settings()


async def _llm_classify_scope(naam: str, adres: str | None, gemeente: str | None, context: str | None) -> str:

    from .llm import maak_client

    client = maak_client()
    response = await llm._create_response(client,
        model=llm._extraction_model(),
        input=SCOPE_PROMPT.format(naam=naam, adres=adres or "onbekend", gemeente=gemeente or "onbekend",
                                  context=(context or "")[:2000]),
        max_output_tokens=350,
        text={"format": {"type": "json_object"}},
    )
    data = await llm._parse_json_met_herstel(client, llm._extraction_model(), response.output_text)
    return (data or {}).get("scope_class") or ScopeClass.UNKNOWN.value


async def _llm_classify_identity_and_scope(
    naam: str, adres: str | None, gemeente: str | None, context: str | None, bron_url: str | None,
) -> tuple[str, str]:

    from .llm import maak_client

    client = maak_client()
    response = await llm._create_response(client,
        model=llm._extraction_model(),
        input=IDENTITY_EN_SCOPE_PROMPT.format(
            naam=naam, adres=adres or "onbekend", gemeente=gemeente or "onbekend",
            bron_url=bron_url or "onbekend", context=(context or "")[:2000],
        ),
        max_output_tokens=400,
        text={"format": {"type": "json_object"}},
    )
    data = await llm._parse_json_met_herstel(client, llm._extraction_model(), response.output_text)
    if not data:
        return IdentityClass.UNKNOWN.value, ScopeClass.UNKNOWN.value
    return (
        data.get("identity_class") or IdentityClass.UNKNOWN.value,
        data.get("scope_class") or ScopeClass.UNKNOWN.value,
    )


class LiveIdentityScopeClassifier:
    async def classify(
        self, naam: str, adres: str | None, gemeente: str | None,
        website_url: str | None, finding,
    ) -> tuple[str, str]:
        if finding is None:
            return IdentityClass.UNKNOWN.value, ScopeClass.UNKNOWN.value
        if domain_matches_company(finding.bron_url, website_url) is True:
            scope = await _llm_classify_scope(naam, adres, gemeente, finding.context)
            return IdentityClass.EXACT_ENTITY.value, scope
        return await _llm_classify_identity_and_scope(
            naam, adres, gemeente, finding.context, finding.bron_url,
        )
