from unittest.mock import AsyncMock

import pytest

from app.providers import live
from app.research.live_tools import LiveResearchTools
from app.research.query_planner import QueryContext
from app.research.types import CombinedSearchResult, PlannedQuery
from app.research.validation import SourceDocument


@pytest.mark.asyncio
async def test_nieuwste_officiele_document_krijgt_eigen_site_search(
    monkeypatch,
):
    async def fake_web_search(query, max_results=8):
        return [{
            "title": "Jaarrekening en Maatschappelijk Verslag",
            "url": "https://www.mondriaan.eu/jaarrekening-en-maatschappelijk-verslag",
            "snippet": "Mondriaan Jaarrekening 2025",
            "bron": "serper",
        }]

    tools = LiveResearchTools()
    tools.inspect = AsyncMock(return_value=SourceDocument(
        naam="Mondriaan",
        company_website_url="https://www.mondriaan.eu",
        url="https://www.mondriaan.eu/jaarrekening-en-maatschappelijk-verslag",
        titel="Jaarrekening en Maatschappelijk Verslag",
        brontype="officiele_website",
        documenttype="jaarrekening",
        gevraagd_jaar=2025,
        verslagjaar=2025,
    ))
    monkeypatch.setattr(live, "_web_search", fake_web_search)

    document = await tools.find_nieuwste_officiele_document(QueryContext(
        naam="Mondriaan",
        gemeente="Heerlen",
        website_url="https://www.mondriaan.eu",
        gevraagd_jaar=2025,
    ))

    assert document is not None
    assert document.verslagjaar == 2025
    assert "site:mondriaan.eu" in tools.inspect.await_args.args[1].query


@pytest.mark.asyncio
async def test_documentjaar_mag_uit_zoeksnippet_komen(monkeypatch):
    async def fake_fetch_text(url):
        return "Navigatie en algemene informatie zonder zichtbaar jaartal."

    monkeypatch.setattr(live.settings, "openai_api_key", "")
    monkeypatch.setattr(live, "_fetch_text", fake_fetch_text)

    document = await LiveResearchTools().inspect(
        QueryContext(
            naam="Mondriaan",
            website_url="https://www.mondriaan.eu",
            gevraagd_jaar=2025,
        ),
        PlannedQuery("document", "site:mondriaan.eu 2025", "nieuwste"),
        CombinedSearchResult(
            title="Jaarrekening en Maatschappelijk Verslag",
            url="https://www.mondriaan.eu/jaarrekening-en-maatschappelijk-verslag",
            canonical_url="https://mondriaan.eu/jaarrekening-en-maatschappelijk-verslag",
            snippets=["Mondriaan Jaarrekening 2025"],
            providers=["serper"],
            queries=["site:mondriaan.eu 2025"],
        ),
    )

    assert document is not None
    assert document.verslagjaar == 2025


@pytest.mark.asyncio
async def test_nieuwste_officiele_document_probeert_stabiele_publicatiepagina(
    monkeypatch,
):
    async def fake_web_search(query, max_results=8):
        return []

    tools = LiveResearchTools()

    async def fake_inspect(context, query, result):
        if result.url.endswith("/jaarrekening-en-maatschappelijk-verslag"):
            return SourceDocument(
                naam=context.naam,
                company_website_url=context.website_url,
                url=result.url,
                titel="Jaarrekening en Maatschappelijk Verslag",
                brontype="officiele_website",
                documenttype="jaarrekening",
                gevraagd_jaar=2025,
                verslagjaar=2025,
            )
        return None

    tools.inspect = AsyncMock(side_effect=fake_inspect)
    monkeypatch.setattr(live, "_web_search", fake_web_search)

    document = await tools.find_nieuwste_officiele_document(QueryContext(
        naam="Mondriaan",
        website_url="https://www.mondriaan.eu/over-ons",
        gevraagd_jaar=2025,
    ))

    assert document is not None
    assert (
        document.url
        == "https://www.mondriaan.eu/jaarrekening-en-maatschappelijk-verslag"
    )
