"""De supervisor routeert website-, document- en mediaonderzoek samen."""
import asyncio
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
    assert outcome.diagnostiek["gelezen_documenten"] == 3
    assert outcome.diagnostiek["bruikbare_documenten"] == 3


class EmptyResearchTools(FakeResearchTools):
    async def search(self, query: PlannedQuery, max_results: int):
        return []


class ManyResultsResearchTools(FakeResearchTools):
    def __init__(self):
        super().__init__()
        self.geinspecteerde_paden: list[str] = []

    async def search(self, query: PlannedQuery, max_results: int):
        return [
            CombinedSearchResult(
                title=f"{query.pad} {index}",
                url=f"https://{query.pad}.example/{query.query[:8]}/{index}",
                canonical_url=(
                    f"https://{query.pad}.example/{query.query[:8]}/{index}"
                ),
                snippets=[],
                providers=["test"],
                queries=[query.query],
            )
            for index in range(8)
        ]

    async def inspect(self, context, query, result):
        self.geinspecteerde_paden.append(query.pad)
        return await super().inspect(context, query, result)


class VeleKandidatenResearchTools(FakeResearchTools):
    """Levert veel unieke, goedgekeurde documenten om de
    kandidaten-cap te kunnen testen los van het paginabudget."""

    async def search(self, query: PlannedQuery, max_results: int):
        return [
            CombinedSearchResult(
                title=f"{query.pad} bron {index}",
                url=f"https://voorbeeldzorg.nl/{query.pad}/{index}",
                canonical_url=f"https://voorbeeldzorg.nl/{query.pad}/{index}",
                snippets=[f"{index} medewerkers."],
                providers=["serper"],
                queries=[query.query],
            )
            for index in range(max_results)
        ]

    async def inspect(self, context, query, result):
        return SourceDocument(
            naam=context.naam,
            company_website_url=context.website_url,
            url=result.url,
            titel=result.title,
            tekst=f"Voorbeeld Zorg telde {result.title}.",
            brontype="officiele_website" if query.pad == "website" else (
                "jaarverslag" if query.pad == "document" else "media"
            ),
            documenttype="teampagina",
            wp_gevonden=47,
            eenheid="werkzame_personen",
            bewijsfragment=f"Voorbeeld Zorg telde {result.title}.",
        )


@pytest.mark.asyncio
async def test_kandidaten_limiet_is_configureerbaar():
    tools = VeleKandidatenResearchTools()

    outcome_default = await ResearchSupervisor(
        tools, max_queries=12, max_pages=9,
    ).run(QueryContext(
        naam="Voorbeeld Zorg",
        website_url="https://voorbeeldzorg.nl",
        huidig_jaar=2026,
    ))
    assert len(outcome_default.kandidaten) == 3

    outcome_ruim = await ResearchSupervisor(
        tools, max_queries=12, max_pages=9, max_kandidaten=8,
    ).run(QueryContext(
        naam="Voorbeeld Zorg",
        website_url="https://voorbeeldzorg.nl",
        huidig_jaar=2026,
    ))
    # De limiet is een bovengrens: per menselijke bronrol worden maximaal
    # twee alternatieven getoond om handmatig dubbelwerk te voorkomen.
    assert len(outcome_ruim.kandidaten) == 4
    assert len(outcome_ruim.kandidaten) <= 8


@pytest.mark.asyncio
async def test_klein_paginabudget_wordt_over_onderzoekspaden_verdeeld():
    tools = ManyResultsResearchTools()

    outcome = await ResearchSupervisor(
        tools, max_queries=12, max_pages=3,
    ).run(QueryContext(
        naam="Voorbeeld Zorg",
        gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
        huidig_jaar=2026,
    ))

    assert outcome.onderzochte_paginas == 3
    assert tools.geinspecteerde_paden == ["website", "document", "media"]


@pytest.mark.asyncio
async def test_supervisor_registreert_explicitiet_niet_gevonden():
    outcome = await ResearchSupervisor(
        EmptyResearchTools(), max_queries=3, max_pages=5,
    ).run(QueryContext(naam="Onvindbare Organisatie", huidig_jaar=2026))

    assert outcome.status == "niet_gevonden"
    assert outcome.kandidaten == []
    assert outcome.onderzochte_queries == 3
    assert outcome.diagnostiek["zoekresultaten"] == 0


@pytest.mark.asyncio
async def test_supervisor_neemt_gespecialiseerd_jaarverslag_als_seed_mee():
    seed = SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
        titel="Jaarverslag 2025",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        wp_gevonden=47,
        eenheid="werkzame_personen",
        bewijsfragment="Voorbeeld Zorg had 47 medewerkers.",
    )
    outcome = await ResearchSupervisor(
        EmptyResearchTools(), max_queries=3, max_pages=5,
    ).run(
        QueryContext(
            naam="Voorbeeld Zorg",
            gevraagd_jaar=2025,
            website_url="https://voorbeeldzorg.nl",
        ),
        seed_documents=[seed],
    )

    assert outcome.status == "review_nodig"
    assert [item.document.url for item in outcome.kandidaten] == [seed.url]
    assert outcome.diagnostiek["gelezen_documenten"] == 1


class TrageReviewTools(FakeResearchTools):
    """3 documenten (1 per pad), elk met een kunstmatige vertraging in
    inspect() zodat sequentieel vs. concurrent review meetbaar is."""

    async def inspect(self, context, query, result):
        await asyncio.sleep(0.05)
        return await super().inspect(context, query, result)


class TrageReviewer:
    async def review(self, context, document):
        from app.research.validation import valideer_bron
        await asyncio.sleep(0.05)
        return valideer_bron(document)


@pytest.mark.asyncio
async def test_bronreview_calls_lopen_concurrent():
    tools = TrageReviewTools()

    loop = asyncio.get_event_loop()
    start = loop.time()
    outcome = await ResearchSupervisor(
        tools, max_queries=12, max_pages=20, reviewer=TrageReviewer(),
    ).run(QueryContext(
        naam="Voorbeeld Zorg",
        gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
        huidig_jaar=2026,
    ))
    duur = loop.time() - start

    # 3 documenten x (0.05s ophalen + 0.05s review) sequentieel zou >= 0.30s
    # duren. Met concurrent ophalen (bestaand gedrag) én concurrent review
    # (nieuw) moet dit ruim onder die grens blijven.
    assert duur < 0.20
    assert len(outcome.kandidaten) == 3
