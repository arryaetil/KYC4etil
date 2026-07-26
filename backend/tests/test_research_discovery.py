"""Discoverytests: queryplanning, URL-normalisatie en providerfusie."""
from types import SimpleNamespace

import pytest

from app.research.query_planner import (
    QueryContext,
    plan_queries,
    vereenvoudigde_zoeknaam,
)
from app.research.search import combineer_zoekresultaten
from app.research.service import _dedupliceer_kandidaten
from app.research.types import SearchResult
from app.research.urls import canonicaliseer_url


def test_queryplanner_dekt_website_documenten_en_recente_media():
    queries = plan_queries(QueryContext(
        naam="Voorbeeld Zorg",
        gevraagd_jaar=2025,
        website_url="https://www.voorbeeldzorg.nl",
        gemeente="Heerlen",
    ))

    assert any(q.pad == "website" and "site:voorbeeldzorg.nl" in q.query for q in queries)
    assert any(q.pad == "document" and "jaarverslag 2025" in q.query for q in queries)
    assert any(q.pad == "document" and "2026" in q.query for q in queries)
    assert any(q.pad == "media" and "nieuws" in q.query for q in queries)
    site_document_index = next(
        index for index, query in enumerate(queries)
        if query.pad == "document" and "site:voorbeeldzorg.nl" in query.query
    )
    open_document_index = next(
        index for index, query in enumerate(queries)
        if query.pad == "document" and "site:" not in query.query
    )
    assert site_document_index < open_document_index
    assert len({q.query for q in queries}) == len(queries)


def test_administratieve_subwoning_krijgt_zoekalias_op_eigennaam():
    assert vereenvoudigde_zoeknaam("Groepswoning Piushof B 2") == "Piushof"

    queries = plan_queries(QueryContext(
        naam="Groepswoning Piushof B 2",
        gemeente="Venlo",
        gevraagd_jaar=2025,
    ))

    assert any(
        query.pad == "website"
        and '"Piushof"' in query.query
        and query.doel.startswith("openbare bronnen")
        for query in queries
    )
    assert any(
        query.query.startswith("Piushof ")
        and query.doel.startswith("spellingtolerante")
        for query in queries
    )


def test_normale_bedrijfsnaam_wordt_niet_onnodig_vereenvoudigd():
    assert vereenvoudigde_zoeknaam("Mondriaan") is None


def test_canonicaliseer_url_verwijdert_tracking_fragment_en_www():
    assert canonicaliseer_url(
        "HTTPS://WWW.Example.nl/team/?utm_source=test&id=12#medewerkers"
    ) == "https://example.nl/team?id=12"


def test_parallelle_paden_worden_voor_opslag_canoniek_gededupliceerd():
    specialist = SimpleNamespace(document=SimpleNamespace(
        url="https://www.mondriaan.eu/jaarverslag-2024.pdf",
    ))
    breed_zoekpad = SimpleNamespace(document=SimpleNamespace(
        url="https://mondriaan.eu/jaarverslag-2024.pdf?utm_source=search",
    ))

    uniek = _dedupliceer_kandidaten([specialist, breed_zoekpad])

    assert uniek == [
        (specialist, "https://mondriaan.eu/jaarverslag-2024.pdf"),
    ]


@pytest.mark.asyncio
async def test_combineer_zoekresultaten_voert_alle_providers_uit_en_dedupliceert():
    calls: list[str] = []

    async def duckduckgo(query: str, max_results: int):
        calls.append("duckduckgo")
        return [
            SearchResult(
                title="Team",
                url="https://www.example.nl/team?utm_source=ddg",
                snippet="47 medewerkers",
                provider="duckduckgo",
                query=query,
            ),
        ]

    async def serper(query: str, max_results: int):
        calls.append("serper")
        return [
            SearchResult(
                title="Team van Example",
                url="https://example.nl/team",
                snippet="Ons team telt 47 medewerkers",
                provider="serper",
                query=query,
            ),
            SearchResult(
                title="Nieuws",
                url="https://nieuws.example/example-groeit",
                snippet="recente groei",
                provider="serper",
                query=query,
            ),
        ]

    results = await combineer_zoekresultaten(
        "Example medewerkers",
        providers=[duckduckgo, serper],
        max_results_per_provider=5,
    )

    assert calls == ["duckduckgo", "serper"]
    assert len(results) == 2
    team = next(result for result in results if "example.nl/team" in result.url)
    assert team.providers == ["duckduckgo", "serper"]
    assert "47 medewerkers" in team.snippets
