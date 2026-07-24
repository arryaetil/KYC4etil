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

from .query_planner import QueryContext, plan_queries
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
        reviewer=None,
    ):
        self.tools = tools
        self.max_queries = max_queries
        self.max_pages = max_pages
        self.max_results_per_query = max_results_per_query
        self.reviewer = reviewer

    async def run(
        self,
        context: QueryContext,
        seed_documents: list[SourceDocument] | None = None,
    ) -> ResearchOutcome:
        queries = plan_queries(context)[:self.max_queries]
        search_results = await asyncio.gather(*[
            self.tools.search(query, self.max_results_per_query)
            for query in queries
        ], return_exceptions=True)

        fouten: list[str] = []
        te_inspecteren: list[tuple[PlannedQuery, CombinedSearchResult]] = []
        seed_documents = seed_documents or []
        geziene_urls: set[str] = {
            document.url for document in seed_documents
        }
        resultaten_per_pad: dict[
            str, list[tuple[PlannedQuery, CombinedSearchResult]]
        ] = {}
        for query, results in zip(queries, search_results):
            if isinstance(results, BaseException):
                fouten.append(f"{query.pad}: {results}")
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
        validaties = []
        afwijzingen = []
        documenten = 0
        for item in [*seed_documents, *inspected]:
            if isinstance(item, BaseException):
                fouten.append(f"inspectie: {item}")
                continue
            if item is not None:
                documenten += 1
                if self.reviewer is not None:
                    try:
                        validatie = await self.reviewer.review(context, item)
                        validaties.append(validatie)
                    except Exception as exc:
                        fouten.append(f"bronreview: {exc}")
                        continue
                else:
                    validatie = valideer_bron(item)
                    validaties.append(validatie)
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

        ranked = rank_bronnen(validaties)[:3]
        reden_teller = Counter(
            reden
            for validatie in validaties
            if validatie.is_afgewezen
            for reden in validatie.afwijsredenen
        )
        return ResearchOutcome(
            status="review_nodig" if ranked else "niet_gevonden",
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
            },
        )
