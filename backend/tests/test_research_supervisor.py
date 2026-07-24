"""De supervisor routeert website-, document- en mediaonderzoek samen."""
from datetime import date

import pytest

from app.research.query_planner import QueryContext
from app.research.supervisor import ResearchSupervisor
from app.research.types import CombinedSearchResult, PlannedQuery
from app.research.validation import SourceDocument


class FakeResearchTools:
    def __init__(self):
        self.paden: list[str] = []

    async def search(self, query: PlannedQuery, max_results: int):
        self.paden.append(query.pad)
        if query.pad == "website":
            return [CombinedSearchResult(
                title="Ons team",
                url="https://voorbeeldzorg.nl/team",
                canonical_url="https://voorbeeldzorg.nl/team",
                snippets=["Ons team bestaat uit 47 medewerkers."],
                providers=["serper"],
                queries=[query.query],
            )]
        if query.pad == "document":
            return [CombinedSearchResult(
                title="Jaarverslag 2025",
                url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
                canonical_url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
                snippets=["Jaarverslag 2025"],
                providers=["duckduckgo", "serper"],
                queries=[query.query],
            )]
        return [CombinedSearchResult(
            title="Voorbeeld Zorg groeit",
            url="https://limburgnieuws.nl/voorbeeld-zorg-groeit",
            canonical_url="https://limburgnieuws.nl/voorbeeld-zorg-groeit",
            snippets=["De organisatie groeit naar 50 medewerkers."],
            providers=["serper"],
            queries=[query.query],
        )]

    async def inspect(self, context: QueryContext, query: PlannedQuery, result):
        if query.pad == "document":
            return SourceDocument(
                naam=context.naam,
                company_website_url=context.website_url,
                url=result.url,
                titel=result.title,
                tekst="Voorbeeld Zorg telde in 2025 47 medewerkers.",
                brontype="jaarverslag",
                documenttype="jaarverslag",
                gevraagd_jaar=context.gevraagd_jaar,
                verslagjaar=2025,
                publicatiedatum=date(2026, 4, 1),
                informatie_peilmoment="2025-12",
                wp_gevonden=47,
                eenheid="werkzame_personen",
                bewijsfragment="Voorbeeld Zorg telde in 2025 47 medewerkers.",
            )
        if query.pad == "website":
            return SourceDocument(
                naam=context.naam,
                company_website_url=context.website_url,
                url=result.url,
                titel=result.title,
                tekst="Ons team bestaat uit 47 medewerkers.",
                brontype="officiele_website",
                documenttype="teampagina",
                publicatiedatum=date(2026, 6, 1),
                informatie_peilmoment="2026-06",
                wp_gevonden=47,
                eenheid="werkzame_personen",
                bewijsfragment="Ons team bestaat uit 47 medewerkers.",
            )
        return SourceDocument(
            naam=context.naam,
            company_website_url=context.website_url,
            url=result.url,
            titel=result.title,
            tekst="Voorbeeld Zorg groeit naar 50 medewerkers.",
            brontype="media",
            documenttype="nieuwsartikel",
            publicatiedatum=date(2026, 7, 1),
            informatie_peilmoment="2026-07",
            wp_gevonden=50,
            eenheid="werkzame_personen",
            bewijsfragment="Voorbeeld Zorg groeit naar 50 medewerkers.",
        )


@pytest.mark.asyncio
async def test_supervisor_levert_top3_uit_alle_onderzoekspaden():
    tools = FakeResearchTools()
    supervisor = ResearchSupervisor(tools, max_queries=12, max_pages=20)

    outcome = await supervisor.run(QueryContext(
        naam="Voorbeeld Zorg",
        gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
        gemeente="Heerlen",
        huidig_jaar=2026,
    ))

    assert outcome.status == "review_nodig"
    assert len(outcome.kandidaten) == 3
    assert {"website", "document", "media"}.issubset(set(tools.paden))
    assert outcome.kandidaten[0].document.url.startswith("https://voorbeeldzorg.nl/")
    assert any(k.document.brontype == "media" for k in outcome.kandidaten)
    assert outcome.onderzochte_queries <= 12
    assert outcome.onderzochte_paginas == 3


class EmptyResearchTools(FakeResearchTools):
    async def search(self, query: PlannedQuery, max_results: int):
        return []


@pytest.mark.asyncio
async def test_supervisor_registreert_explicitiet_niet_gevonden():
    outcome = await ResearchSupervisor(
        EmptyResearchTools(), max_queries=3, max_pages=5,
    ).run(QueryContext(naam="Onvindbare Organisatie", huidig_jaar=2026))

    assert outcome.status == "niet_gevonden"
    assert outcome.kandidaten == []
    assert outcome.onderzochte_queries == 3
