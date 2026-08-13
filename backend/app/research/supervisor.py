"""Researchregie volgens het Open Deep Research-patroon.

Deze eerste productievertical voert gespecialiseerde querypaden parallel uit,
normaliseert bewijs, valideert deterministisch en levert een top 3. Een
volgende iteratie voegt de reflectie/follow-up-rondes toe zonder het
kandidaatcontract te veranderen.
"""
import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from .query_planner import QueryContext, plan_queries, plan_routes
from .ranking import RankedBron, rank_bronnen
from .types import CombinedSearchResult, PlannedQuery
from .validation import SourceDocument, valideer_bron


class ResearchTools(Protocol):
    async def search(
        self, query: PlannedQuery, max_results: int,
    ) -> list[CombinedSearchResult]: ...

    async def inspect(
        self,
        context: QueryContext,
        query: PlannedQuery,
        result: CombinedSearchResult,
    ) -> SourceDocument | None: ...


@dataclass
class ResearchOutcome:
    status: str
    kandidaten: list[RankedBron]
    onderzochte_queries: int
    onderzochte_paginas: int
    fouten: list[str]
    diagnostiek: dict = field(default_factory=dict)


class ResearchSupervisor:
    def __init__(
        self,
        tools: ResearchTools,
        max_queries: int,
        max_pages: int,
        max_results_per_query: int = 8,
        max_kandidaten: int = 3,
        reviewer=None,
    ):
        self.tools = tools
        self.max_queries = max_queries
        self.max_pages = max_pages
        self.max_results_per_query = max_results_per_query
        self.max_kandidaten = max_kandidaten
        self.reviewer = reviewer

    async def run(
        self,
        context: QueryContext,
        seed_documents: list[SourceDocument] | None = None,
    ) -> ResearchOutcome:
        route_plan = plan_routes(context)
        seed_documents = seed_documents or []
        directe_routes = {
            document.research_route
            for document in seed_documents
            if document.research_route
        }
        queries = [
            query for query in plan_queries(context)
            if query.pad not in directe_routes
        ][:self.max_queries]
        query_aantallen = Counter(query.pad for query in queries)
        search_results = await asyncio.gather(*[
            self.tools.search(query, self.max_results_per_query)
            for query in queries
        ], return_exceptions=True)

        fouten: list[str] = []
        zoekfouten_per_route: Counter = Counter()
        te_inspecteren: list[tuple[PlannedQuery, CombinedSearchResult]] = []
        geziene_urls: set[str] = {
            document.url for document in seed_documents
        }
        resultaten_per_pad: dict[
            str, list[tuple[PlannedQuery, CombinedSearchResult]]
        ] = {}
        for query, results in zip(queries, search_results):
            if isinstance(results, BaseException):
                fouten.append(f"{query.pad}: {results}")
                zoekfouten_per_route[query.pad] += 1
                continue
            resultaten_per_pad.setdefault(query.pad, []).extend(
                (query, result) for result in results
            )

        # Verdeel het paginabudget over alle zoekpaden. De oude sequentiële
        # selectie kon het hele budget vullen met de eerste websitequery,
        # waardoor jaarstukken en media nooit werden gelezen zodra het budget
        # lager werd. Round-robin bewaart diversiteit én de harde kostenlimiet.
        grootste_resultaatset = max(
            (len(results) for results in resultaten_per_pad.values()),
            default=0,
        )
        for resultaat_index in range(grootste_resultaatset):
            for results in resultaten_per_pad.values():
                if resultaat_index >= len(results):
                    continue
                query, result = results[resultaat_index]
                if result.canonical_url in geziene_urls:
                    continue
                geziene_urls.add(result.canonical_url)
                te_inspecteren.append((query, result))
                if len(te_inspecteren) >= self.max_pages:
                    break
            if len(te_inspecteren) >= self.max_pages:
                break

        inspected = await asyncio.gather(*[
            self.tools.inspect(context, query, result)
            for query, result in te_inspecteren
        ], return_exceptions=True)
        inspectiefouten_per_route: Counter = Counter()
        documenten_met_route: list[tuple[SourceDocument, str]] = []
        for document in seed_documents:
            if document.research_route:
                route = document.research_route
            elif document.documenttype in {
                    "jaarverslag", "jaarrekening", "bestuursverslag", "pdf_document",
            }:
                route = "document"
            else:
                route = "website"
            documenten_met_route.append((document, route))
        for (query, _), item in zip(te_inspecteren, inspected):
            if isinstance(item, BaseException):
                fouten.append(f"inspectie: {item}")
                inspectiefouten_per_route[query.pad] += 1
            elif item is not None:
                documenten_met_route.append((item, query.pad))
        documenten_om_te_beoordelen = [
            document for document, _ in documenten_met_route
        ]

        # Lokaal (per run) zodat gelijktijdige runs elkaar niet blokkeren; cap
        # voorkomt dat een rate-limit-fout een bron stil laat verdwijnen.
        review_semaphore = asyncio.Semaphore(5)

        async def _beoordeel(document):
            async with review_semaphore:
                if self.reviewer is not None:
                    try:
                        return await self.reviewer.review(context, document)
                    except Exception as exc:
                        return exc
                return valideer_bron(document)

        beoordelingen = await asyncio.gather(*[
            _beoordeel(document) for document in documenten_om_te_beoordelen
        ])

        validaties = []
        afwijzingen = []
        documenten = len(documenten_om_te_beoordelen)
        bruikbaar_per_route: Counter = Counter()
        for (item, route), validatie in zip(documenten_met_route, beoordelingen):
            if isinstance(validatie, BaseException):
                fouten.append(f"bronreview: {validatie}")
                continue
            validaties.append(validatie)
            if not validatie.is_afgewezen:
                bruikbaar_per_route[route] += 1
            if validatie.is_afgewezen and len(afwijzingen) < 12:
                intelligente_review = validatie.validaties.get(
                    "intelligente_review", {}
                )
                afwijzingen.append({
                    "titel": item.titel,
                    "url": item.url,
                    "identity_class": validatie.identity_class,
                    "redenen": list(validatie.afwijsredenen),
                    "review_reden": intelligente_review.get("reden"),
                })

        # Bewaar alle relevante kandidaten tot de eenvoudige harde bovengrens.
        # Bij de gebruikelijke circa vijf bronnen is een diversiteitsfilter
        # schadelijker dan behulpzaam: het kan een derde relevante team- of
        # documentbron stil laten verdwijnen.
        ranked = rank_bronnen(validaties)[:self.max_kandidaten]
        reden_teller = Counter(
            reden
            for validatie in validaties
            if validatie.is_afgewezen
            for reden in validatie.afwijsredenen
        )
        route_statussen = []
        for gepland in route_plan:
            route = gepland["route"]
            query_count = query_aantallen[route]
            fout_count = (
                zoekfouten_per_route[route] + inspectiefouten_per_route[route]
            )
            if bruikbaar_per_route[route]:
                status = "afgerond"
                statusreden = "bruikbare bronnen gevonden"
            elif query_count == 0:
                status = "overgeslagen"
                statusreden = "niet uitgevoerd binnen het querybudget"
            elif query_count and zoekfouten_per_route[route] == query_count:
                status = "mislukt"
                statusreden = "alle zoekopdrachten voor deze route mislukten"
            elif fout_count and bruikbaar_per_route[route] == 0:
                status = "mislukt"
                statusreden = "bronnen konden technisch niet worden verwerkt"
            else:
                status = "afgerond"
                statusreden = "geen bruikbare bron gevonden"
            route_statussen.append({
                **gepland,
                "status": status,
                "statusreden": statusreden,
                "aantal_bronnen": bruikbaar_per_route[route],
                "aantal_queries": query_count,
            })
        technisch_onvolledig = any(
            item["verplicht"] and item["status"] in {"mislukt", "overgeslagen"}
            for item in route_statussen
        )
        resultaat_status = (
            "technisch_onvolledig"
            if technisch_onvolledig
            else "review_nodig" if ranked else "niet_gevonden"
        )
        return ResearchOutcome(
            status=resultaat_status,
            kandidaten=ranked,
            onderzochte_queries=len(queries),
            onderzochte_paginas=len(te_inspecteren),
            fouten=fouten,
            diagnostiek={
                "zoekresultaten": len(geziene_urls),
                "onderzochte_paginas": len(te_inspecteren),
                "gelezen_documenten": documenten,
                "afgewezen_documenten": sum(
                    1 for item in validaties if item.is_afgewezen
                ),
                "bruikbare_documenten": sum(
                    1 for item in validaties if not item.is_afgewezen
                ),
                "afwijsredenen": dict(reden_teller),
                "afwijzingen": afwijzingen,
                "route_statussen": route_statussen,
            },
        )
