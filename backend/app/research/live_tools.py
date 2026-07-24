"""Adapter van bestaande live providers naar het researchcontract."""
import re
from urllib.parse import unquote, urlsplit

from ..pipeline.identity_scope import heuristic_scope_class
from .query_planner import QueryContext
from .types import CombinedSearchResult, PlannedQuery
from .urls import canonicaliseer_url
from .validation import SourceDocument


class LiveResearchTools:
    async def find_jaarverslag(
        self,
        context: QueryContext,
    ) -> SourceDocument | None:
        """Hergebruik het bewezen gespecialiseerde legacy-zoekpad als seed.

        Het publicatiejaar is één hoger dan het gevraagde verslagjaar. De
        legacy-agent probeert zelf dit jaar en het jaar ervoor, valideert de
        PDF-identiteit en retryt met een andere URL bij een mismatch.
        """
        if context.gevraagd_jaar is None:
            return None
        from ..providers import live

        finding = await live.LiveJaarverslagAgent().run(
            context.naam,
            context.gevraagd_jaar + 1,
            website_url=context.website_url,
        )
        if not finding or not finding.bron_url:
            return None
        titel = unquote(urlsplit(finding.bron_url).path.rsplit("/", 1)[-1])
        return SourceDocument(
            naam=context.naam,
            company_website_url=context.website_url,
            url=finding.bron_url,
            titel=titel or "Gevonden jaarverslag",
            tekst="",
            brontype="jaarverslag",
            documenttype=_documenttype(
                titel, finding.bron_url, is_pdf=True,
            ),
            gevraagd_jaar=context.gevraagd_jaar,
            verslagjaar=_vind_jaar(titel, context.gevraagd_jaar),
            informatie_peilmoment=finding.peilmoment,
            wp_gevonden=finding.wp_gevonden,
            eenheid=(
                "fte" if finding.is_fte
                else "werkzame_personen"
                if finding.wp_gevonden is not None
                else None
            ),
            bewijsfragment=finding.context,
            bron_pagina=finding.bron_pagina,
            scope_class=heuristic_scope_class(
                finding.is_limburg_specifiek, "jaarverslag",
            ),
        )

    async def search(
        self, query: PlannedQuery, max_results: int,
    ) -> list[CombinedSearchResult]:
        from ..providers import live

        results = await live._web_search(query.query, max_results=max_results)
        return [
            CombinedSearchResult(
                title=result.get("title", ""),
                url=result["url"],
                canonical_url=canonicaliseer_url(result["url"]),
                snippets=result.get("snippets") or (
                    [result["snippet"]] if result.get("snippet") else []
                ),
                providers=result.get("bronnen") or [result.get("bron", "web_search")],
                queries=[query.query],
            )
            for result in results
            if result.get("url")
        ]

    async def inspect(
        self,
        context: QueryContext,
        query: PlannedQuery,
        result: CombinedSearchResult,
    ) -> SourceDocument | None:
        from ..providers import live

        is_pdf = ".pdf" in urlsplit(result.url).path.lower()
        if is_pdf:
            try:
                finding = await live.LiveJaarverslagAgent().run_with_pdf(
                    context.naam, result.url,
                )
            except Exception:
                finding = None
            verslagjaar = _vind_jaar(
                result.title,
                context.gevraagd_jaar,
            )
            return SourceDocument(
                naam=context.naam,
                company_website_url=context.website_url,
                url=result.url,
                titel=result.title,
                # Zoekresultaatsnippets zijn geen documentinhoud en mogen de
                # identiteitsreview daarom nooit positief beïnvloeden.
                tekst="",
                brontype="jaarverslag" if query.pad == "document" else query.pad,
                documenttype=_documenttype(result.title, result.url, is_pdf=True),
                gevraagd_jaar=context.gevraagd_jaar,
                verslagjaar=verslagjaar,
                informatie_peilmoment=finding.peilmoment if finding else None,
                wp_gevonden=finding.wp_gevonden if finding else None,
                eenheid=(
                    "fte" if finding and finding.is_fte
                    else "werkzame_personen" if finding and finding.wp_gevonden is not None
                    else None
                ),
                bewijsfragment=finding.context if finding else None,
                bron_pagina=finding.bron_pagina if finding else None,
            )

        try:
            tekst = await live._fetch_text(result.url)
        except Exception:
            tekst = " ".join(result.snippets)
        if not tekst.strip():
            return None

        data = None
        if live.settings.openai_api_key:
            try:
                data = await live._llm_extract(
                    context.naam, context.gemeente, tekst,
                )
            except Exception:
                data = None
        data = data or {}
        domein = urlsplit(result.url).netloc.lower().removeprefix("www.")
        officieel_domein = (
            urlsplit(context.website_url).netloc.lower().removeprefix("www.")
            if context.website_url else None
        )
        brontype = (
            "officiele_website" if officieel_domein and domein == officieel_domein
            else "media" if query.pad == "media"
            else query.pad
        )
        return SourceDocument(
            naam=context.naam,
            company_website_url=context.website_url,
            url=result.url,
            titel=result.title,
            tekst=tekst,
            brontype=brontype,
            documenttype=_documenttype(result.title, result.url, is_pdf=False),
            gevraagd_jaar=context.gevraagd_jaar if query.pad == "document" else None,
            verslagjaar=(
                _vind_jaar(" ".join([result.title, tekst[:1000]]),
                           context.gevraagd_jaar)
                if query.pad == "document" else None
            ),
            informatie_peilmoment=data.get("peilmoment"),
            wp_gevonden=data.get("wp_gevonden"),
            eenheid=(
                "fte" if data.get("is_fte")
                else "werkzame_personen" if data.get("wp_gevonden") is not None
                else None
            ),
            bewijsfragment=data.get("context"),
            scope_class=data.get("scope_class"),
        )


def _vind_jaar(tekst: str, voorkeur: int | None) -> int | None:
    jaren = [int(match) for match in re.findall(r"\b(20\d{2})\b", tekst)]
    if voorkeur in jaren:
        return voorkeur
    return jaren[0] if jaren else None


def _documenttype(titel: str, url: str, is_pdf: bool) -> str:
    tekst = f"{titel} {url}".lower()
    for token, label in [
        ("jaarverslag", "jaarverslag"),
        ("annual-report", "jaarverslag"),
        ("annual report", "jaarverslag"),
        ("jaarrekening", "jaarrekening"),
        ("bestuursverslag", "bestuursverslag"),
        ("team", "teampagina"),
        ("nieuws", "nieuwsartikel"),
    ]:
        if token in tekst:
            return label
    return "pdf_document" if is_pdf else "webpagina"
