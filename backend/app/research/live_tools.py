"""Adapter van bestaande live providers naar het researchcontract."""
import asyncio
import re
from urllib.parse import unquote, urljoin, urlsplit

from ..config import get_settings
from ..pipeline.identity_scope import heuristic_scope_class
from .query_planner import QueryContext
from .types import CombinedSearchResult, PlannedQuery
from .urls import canonicaliseer_url
from .validation import SourceDocument


class LiveResearchTools:
    def __init__(self):
        self._fallback_searches: dict[str, list[CombinedSearchResult]] = {}
        self._fallback_lock = asyncio.Lock()

    async def find_officiele_website(
        self,
        context: QueryContext,
    ) -> SourceDocument | None:
        """Neem een opgelost officieel domein altijd mee als reviewercontext.

        Kleine organisaties hebben vaak geen jaarverslag en zoekmachines tonen
        niet altijd de homepage. De officiële site mag dan niet verdwijnen
        alleen omdat er geen expliciet WP-getal op de eerste pagina staat.
        """
        if not context.website_url:
            return None
        query = PlannedQuery(
            "website",
            f"officiële website van {context.naam}",
            "door Places of websearch opgelost officieel domein",
        )
        return await self.inspect(
            context,
            query,
            CombinedSearchResult(
                title=f"{context.naam} — officiële website",
                url=context.website_url,
                canonical_url=canonicaliseer_url(context.website_url),
                snippets=[f"Officiële website van {context.naam}"],
                providers=["official_site_resolution"],
                queries=[query.query],
            ),
        )

    async def find_nieuwste_officiele_document(
        self,
        context: QueryContext,
    ) -> SourceDocument | None:
        """Zoek de gevraagde jaargang expliciet op het bevestigde domein.

        Dit pad valt buiten het brede paginabudget, zodat een actuele
        jaarrekening/overzichtspagina niet wordt verdrongen door algemene hits.
        Een officiële bron zonder WP-getal blijft reviewercontext.
        """
        if not context.website_url or context.gevraagd_jaar is None:
            return None
        from ..providers import fetch, search

        domein = urlsplit(context.website_url).netloc.lower().removeprefix(
            "www."
        )
        query_texts = [
            (
                f"site:{domein} {context.gevraagd_jaar} "
                "(jaarrekening OR jaarverslag OR jaarverantwoording)"
            ),
            (
                f'site:{domein} "{context.naam}" '
                f'"{context.gevraagd_jaar}" jaarrekening jaarverslag'
            ),
        ]
        geziene_urls: set[str] = set()
        for query_text in query_texts:
            results = await search._web_search(query_text, max_results=8)
            query = PlannedQuery(
                "document",
                query_text,
                "nieuwste document op het bevestigde officiële domein",
            )
            for result in results:
                url = result.get("url")
                if not url:
                    continue
                result_domein = urlsplit(url).netloc.lower().removeprefix(
                    "www."
                )
                canonical_url = canonicaliseer_url(url)
                if result_domein != domein or canonical_url in geziene_urls:
                    continue
                geziene_urls.add(canonical_url)
                combined = CombinedSearchResult(
                    title=result.get("title", ""),
                    url=url,
                    canonical_url=canonical_url,
                    snippets=result.get("snippets") or (
                        [result["snippet"]] if result.get("snippet") else []
                    ),
                    providers=result.get("bronnen")
                    or [result.get("bron", "web_search")],
                    queries=[query_text],
                )
                if ".pdf" not in urlsplit(url).path.lower():
                    try:
                        pagina = await fetch._haal_pagina_op(url)
                    except Exception:
                        pagina = None
                    if pagina:
                        for link in pagina.get("links", []):
                            link_url = link.get("url", "")
                            link_tekst = link.get("tekst", "")
                            zoektekst = unquote(
                                f"{link_tekst} {link_url}"
                            ).lower()
                            if (
                                str(context.gevraagd_jaar) not in zoektekst
                                or not any(
                                    token in zoektekst
                                    for token in (
                                        "jaarrekening",
                                        "jaarverslag",
                                        "jaarverantwoording",
                                        "annual report",
                                    )
                                )
                            ):
                                continue
                            link_domein = urlsplit(
                                link_url,
                            ).netloc.lower().removeprefix("www.")
                            if link_domein != domein:
                                continue
                            linked_document = await self.inspect(
                                context,
                                query,
                                CombinedSearchResult(
                                    title=link_tekst or unquote(
                                        urlsplit(link_url).path.rsplit(
                                            "/", 1,
                                        )[-1]
                                    ),
                                    url=link_url,
                                    canonical_url=canonicaliseer_url(link_url),
                                    snippets=[],
                                    providers=["official_site_link"],
                                    queries=[query_text],
                                ),
                            )
                            if (
                                linked_document is not None
                                and linked_document.verslagjaar
                                == context.gevraagd_jaar
                            ):
                                return linked_document
                document = await self.inspect(context, query, combined)
                if (
                    document is not None
                    and document.verslagjaar == context.gevraagd_jaar
                ):
                    return document

        # Een oudere officiële PDF bevestigt het domein, maar zoekmachines
        # indexeren de nieuwste overzichtspagina soms pas laat. Probeer daarom
        # ook de gangbare, stabiele publicatiepaden rechtstreeks. Dit is een
        # goedkope HTTP-probe en valt buiten het brede zoek-/paginabudget.
        origin = f"{urlsplit(context.website_url).scheme}://{urlsplit(context.website_url).netloc}/"
        for path in (
            "jaarrekening-en-maatschappelijk-verslag",
            "jaarverslag",
            "jaarverslagen",
            "publicaties",
        ):
            url = urljoin(origin, path)
            canonical_url = canonicaliseer_url(url)
            if canonical_url in geziene_urls:
                continue
            query_text = (
                f"directe officiële publicatiepagina voor "
                f"{context.gevraagd_jaar}"
            )
            query = PlannedQuery(
                "document",
                query_text,
                "nieuwste versie vanaf het bevestigde officiële domein",
            )
            # Een overzichtspagina is vooral een routekaart: volg eerst de
            # expliciete link naar de gevraagde jaargang. Zo krijgt de reviewer
            # de echte PDF en kan de bestaande PDF-extractor ook WP-bewijs
            # ophalen.
            try:
                pagina = await fetch._haal_pagina_op(url)
            except Exception:
                pagina = None
            if pagina:
                for link in pagina.get("links", []):
                    link_url = link.get("url", "")
                    link_tekst = link.get("tekst", "")
                    zoektekst = unquote(f"{link_tekst} {link_url}").lower()
                    if (
                        str(context.gevraagd_jaar) not in zoektekst
                        or not any(token in zoektekst for token in (
                            "jaarrekening",
                            "jaarverslag",
                            "jaarverantwoording",
                            "annual report",
                        ))
                    ):
                        continue
                    link_domein = urlsplit(
                        link_url,
                    ).netloc.lower().removeprefix("www.")
                    if link_domein != domein:
                        continue
                    document = await self.inspect(
                        context,
                        query,
                        CombinedSearchResult(
                            title=link_tekst or unquote(
                                urlsplit(link_url).path.rsplit("/", 1)[-1]
                            ),
                            url=link_url,
                            canonical_url=canonicaliseer_url(link_url),
                            snippets=[],
                            providers=["official_site_link"],
                            queries=[query_text],
                        ),
                    )
                    if (
                        document is not None
                        and document.verslagjaar == context.gevraagd_jaar
                    ):
                        return document
            try:
                document = await self.inspect(
                    context,
                    query,
                    CombinedSearchResult(
                        title=path.replace("-", " ").title(),
                        url=url,
                        canonical_url=canonical_url,
                        snippets=[],
                        providers=["official_site_probe"],
                        queries=[query_text],
                    ),
                )
            except Exception:
                continue
            if (
                document is not None
                and document.verslagjaar == context.gevraagd_jaar
            ):
                return document
        return None

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
        from ..providers import jaarverslag

        finding = await jaarverslag.LiveJaarverslagAgent().run(
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
        from ..providers import search

        results = await search._web_search(query.query, max_results=max_results)
        if not results:
            # De planner start meerdere queries per pad parallel. Door per pad
            # één fallback te cachen blijven kosten begrensd op maximaal drie
            # hosted searches per organisatie.
            async with self._fallback_lock:
                if query.pad not in self._fallback_searches:
                    fallback = await search._openai_web_search(
                        query.query,
                        max_results=max_results,
                    )
                    self._fallback_searches[query.pad] = [
                        CombinedSearchResult(
                            title=result.get("title", ""),
                            url=result["url"],
                            canonical_url=canonicaliseer_url(result["url"]),
                            snippets=result.get("snippets") or (
                                [result["snippet"]]
                                if result.get("snippet") else []
                            ),
                            providers=["openai_web_search"],
                            queries=[query.query],
                        )
                        for result in fallback
                        if result.get("url")
                    ]
                return self._fallback_searches[query.pad]
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
        from ..providers import fetch, jaarverslag, llm

        is_pdf = (
            ".pdf" in urlsplit(result.url).path.lower()
            or "digimv_direct" in result.providers
            or "/api/archivesearch/getdocument" in result.url.lower()
        )
        if is_pdf:
            try:
                finding = await jaarverslag.LiveJaarverslagAgent().run_with_pdf(
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
                scope_class="concern" if query.pad == "digimv" else None,
                research_route=query.pad,
                raw_data={
                    "providers": result.providers,
                    "queries": result.queries,
                },
            )

        try:
            tekst = await fetch._fetch_text(result.url)
        except Exception:
            tekst = " ".join(result.snippets)
        if not tekst.strip():
            return None

        data = None
        if get_settings().openai_api_key:
            try:
                data = await llm._llm_extract(
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
                _vind_jaar(
                    " ".join([
                        result.title,
                        *result.snippets,
                        tekst[:4000],
                    ]),
                    context.gevraagd_jaar,
                )
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
            research_route=query.pad,
            raw_data={
                "providers": result.providers,
                "queries": result.queries,
            },
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
