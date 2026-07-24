from unittest.mock import AsyncMock

import pytest

from app.providers import live
from app.research.live_tools import LiveResearchTools
from app.research.query_planner import QueryContext
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
