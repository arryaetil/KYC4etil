"""Researchregie volgens het Open Deep Research-patroon.

Deze eerste productievertical voert gespecialiseerde querypaden parallel uit,
normaliseert bewijs, valideert deterministisch en levert een top 3. Een
volgende iteratie voegt de reflectie/follow-up-rondes toe zonder het
kandidaatcontract te veranderen.
"""
import asyncio
from dataclasses import dataclass
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

    async def run(self, context: QueryContext) -> ResearchOutcome:
        queries = plan_queries(context)[:self.max_queries]
        search_results = await asyncio.gather(*[
            self.tools.search(query, self.max_results_per_query)
            for query in queries
        ], return_exceptions=True)

        fouten: list[str] = []
        te_inspecteren: list[tuple[PlannedQuery, CombinedSearchResult]] = []
        geziene_urls: set[str] = set()
        for query, results in zip(queries, search_results):
            if isinstance(results, BaseException):
                fouten.append(f"{query.pad}: {results}")
                continue
            for result in results:
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
        for item in inspected:
            if isinstance(item, BaseException):
                fouten.append(f"inspectie: {item}")
                continue
            if item is not None:
                if self.reviewer is not None:
                    try:
                        validaties.append(
                            await self.reviewer.review(context, item)
                        )
                    except Exception as exc:
                        fouten.append(f"bronreview: {exc}")
                else:
                    validaties.append(valideer_bron(item))

        ranked = rank_bronnen(validaties)[:3]
        return ResearchOutcome(
            status="review_nodig" if ranked else "niet_gevonden",
            kandidaten=ranked,
            onderzochte_queries=len(queries),
            onderzochte_paginas=len(te_inspecteren),
            fouten=fouten,
        )
