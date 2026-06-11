"""Tests voor de drie pipeline-verbeteringen:
1. Directe WP web search als Fase-C fallback in LiveWebsiteAgent
2. Jaarverslag-agent actief via web search
3. Lookup_failed blokkeert agents niet meer
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.base import AgentFinding, LocationInfo, PlacesResult
from app.providers.mock import MockWebsiteAgent


# --- Verbetering 1: MockWebsiteAgent accepteert gemeente-parameter ---

@pytest.mark.asyncio
async def test_mock_website_agent_accepteert_gemeente():
    agent = MockWebsiteAgent()
    # Moet niet crashen met gemeente-parameter
    result = await agent.run("Fysiosittard", None, None, gemeente="Sittard-Geleen")
    # Fysiosittard staat in mock_data, dus verwacht een finding
    assert result is not None
    assert result.wp_gevonden is not None


@pytest.mark.asyncio
async def test_mock_website_agent_zonder_gemeente_werkt_nog():
    agent = MockWebsiteAgent()
    result = await agent.run("Fysiosittard", None, None)
    assert result is not None


# --- Verbetering 2: LiveWebsiteAgent valt terug op web search als geen URL ---

@pytest.mark.asyncio
async def test_live_website_agent_roept_web_search_aan_zonder_url():
    """Als website_url=None, moet de agent _web_search_wp aanroepen (Fase C)."""
    mock_finding = AgentFinding(
        wp_gevonden=42, context="42 medewerkers", zekerheid="middel",
        reden="web search", bron_url="https://example.com", bron_type="media",
        is_limburg_specifiek=True,
    )
    with patch("app.providers.live._web_search_wp", new=AsyncMock(return_value=mock_finding)):
        from app.providers.live import LiveWebsiteAgent
        agent = LiveWebsiteAgent()
        result = await agent.run("TestBedrijf", None, None, gemeente="Maastricht")
    assert result is not None
    assert result.wp_gevonden == 42
    assert result.bron_type == "media"


@pytest.mark.asyncio
async def test_live_website_agent_slaat_web_search_over_als_scraping_slaagt():
    """Als website-scraping een resultaat geeft, moet web search NIET aangeroepen worden."""
    scrape_finding = AgentFinding(
        wp_gevonden=10, context="10 medewerkers", zekerheid="hoog",
        reden="website", bron_url="https://example.com/over-ons", bron_type="website",
    )
    with patch("app.providers.live._fetch_text", new=AsyncMock(return_value="tekst")), \
         patch("app.providers.live._llm_extract", new=AsyncMock(return_value={
             "wp_gevonden": 10, "context": "10 medewerkers", "zekerheid": "hoog",
             "reden": "ok", "is_totaal_meerdere_vestigingen": False,
             "is_limburg_specifiek": True, "is_fte": False, "peilmoment": "2024",
         })), \
         patch("app.providers.live._web_search_wp", new=AsyncMock(return_value=None)) as mock_ws, \
         patch("asyncio.sleep", new=AsyncMock()):
        from app.providers.live import LiveWebsiteAgent
        agent = LiveWebsiteAgent()
        result = await agent.run("TestBedrijf", None, "https://example.com", gemeente="Venlo")
    assert result is not None
    assert result.wp_gevonden == 10
    mock_ws.assert_not_called()


# --- Verbetering 3: LiveJaarverslagAgent gebruikt web search ---

@pytest.mark.asyncio
async def test_live_jaarverslag_agent_zoekt_pdf_via_web_search():
    """LiveJaarverslagAgent.run() moet _zoek_jaarverslag_pdf aanroepen."""
    with patch("app.providers.live._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value=None)) as mock_zoek:
        from app.providers.live import LiveJaarverslagAgent
        agent = LiveJaarverslagAgent()
        result = await agent.run("Mondriaan", 2025)
    mock_zoek.assert_called_once_with("Mondriaan", 2025)
    assert result is None  # geen PDF gevonden = None


@pytest.mark.asyncio
async def test_live_jaarverslag_agent_verwerkt_pdf_als_gevonden():
    """Als _zoek_jaarverslag_pdf een URL geeft, moet run_with_pdf aangeroepen worden."""
    wp_finding = AgentFinding(
        wp_gevonden=2281, context="2281 medewerkers", zekerheid="hoog",
        reden="jaarverslag", bron_url="https://example.com/jaarverslag.pdf",
        bron_type="jaarverslag",
    )
    with patch("app.providers.live._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value="https://example.com/jaarverslag.pdf")), \
         patch.object(
             __import__("app.providers.live", fromlist=["LiveJaarverslagAgent"]).LiveJaarverslagAgent,
             "run_with_pdf", new=AsyncMock(return_value=wp_finding)
         ):
        from app.providers.live import LiveJaarverslagAgent
        agent = LiveJaarverslagAgent()
        result = await agent.run("Mondriaan", 2025)
    assert result is not None
    assert result.wp_gevonden == 2281


@pytest.mark.asyncio
async def test_live_jaarverslag_agent_handelt_pdf_fout_af():
    """Als run_with_pdf faalt, moet run() None teruggeven (geen crash)."""
    with patch("app.providers.live._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value="https://example.com/broken.pdf")), \
         patch("app.providers.live.LiveJaarverslagAgent.run_with_pdf",
               new=AsyncMock(side_effect=Exception("download fout"))):
        from app.providers.live import LiveJaarverslagAgent
        agent = LiveJaarverslagAgent()
        result = await agent.run("TestBedrijf", 2025)
    assert result is None


# --- Verbetering 4: lookup_failed blokkeert agents niet meer ---

@pytest.mark.asyncio
async def test_runner_draait_agents_ook_bij_lookup_failed():
    """Agents moeten altijd draaien, ook als enrichment.lookup_failed=True."""
    from unittest.mock import MagicMock, AsyncMock, patch
    from app.pipeline.runner import verwerk_company

    # Minimale DB-mock
    db = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()

    batch = MagicMock()
    batch.id = "batch-1"
    batch.jaar = 2025

    company = MagicMock()
    company.id = "comp-1"
    company.naam = "TestBedrijf"
    company.adres = None
    company.gemeente = "Maastricht"
    company.kvk_nummer = None
    company.website_url = None
    company.telefoonnummer = None

    wp_finding = AgentFinding(
        wp_gevonden=5, context="5 medewerkers", zekerheid="middel",
        reden="web search", bron_url="https://example.com", bron_type="media",
        is_limburg_specifiek=True,
    )

    mock_lookup = MagicMock()
    mock_lookup.lookup = AsyncMock(return_value=None)  # lookup_failed scenario
    mock_lookup.locations = AsyncMock(return_value=LocationInfo(count_nl=None, count_lb=None, bron="web_search"))

    mock_website = MagicMock()
    mock_website.run = AsyncMock(return_value=wp_finding)  # agent vindt wél iets

    mock_jaarverslag = MagicMock()
    mock_jaarverslag.run = AsyncMock(return_value=None)

    with patch("app.pipeline.runner.get_providers",
               return_value=(mock_lookup, mock_website, mock_jaarverslag)):
        candidate = await verwerk_company(db, company, batch)

    # Agent moet aangeroepen zijn ondanks lookup_failed
    mock_website.run.assert_called_once()
    # En het gevonden WP moet in de candidate zitten
    assert candidate.wp_kandidaat == 5
