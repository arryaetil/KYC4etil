"""Voer meerdere zoekproviders uit en fuseer hun bewijs per canonieke URL."""
import asyncio
from collections.abc import Awaitable, Callable

from .types import CombinedSearchResult, SearchResult
from .urls import canonicaliseer_url

SearchProvider = Callable[[str, int], Awaitable[list[SearchResult]]]


async def combineer_zoekresultaten(
    query: str,
    providers: list[SearchProvider],
    max_results_per_provider: int = 8,
) -> list[CombinedSearchResult]:
    resultaten = await asyncio.gather(*[
        provider(query, max_results_per_provider) for provider in providers
    ], return_exceptions=True)

    combined: dict[str, CombinedSearchResult] = {}
    for provider_resultaten in resultaten:
        if isinstance(provider_resultaten, BaseException):
            continue
        for result in provider_resultaten:
            canonical = canonicaliseer_url(result.url)
            bestaand = combined.get(canonical)
            if bestaand is None:
                bestaand = CombinedSearchResult(
                    title=result.title,
                    url=result.url,
                    canonical_url=canonical,
                )
                combined[canonical] = bestaand
            if result.snippet and result.snippet not in bestaand.snippets:
                bestaand.snippets.append(result.snippet)
            if result.provider not in bestaand.providers:
                bestaand.providers.append(result.provider)
            if result.query not in bestaand.queries:
                bestaand.queries.append(result.query)

    return list(combined.values())
