"""Tests voor de drie pipeline-verbeteringen:
1. Directe WP web search als Fase-C fallback in LiveWebsiteAgent
2. Jaarverslag-agent actief via web search
3. Lookup_failed blokkeert agents niet meer
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.base import AgentFinding, LocationInfo, PlacesResult
from app.pipeline.evidence import IdentityClass
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
    """Als de tool-use-loop een resultaat geeft, moet web search NIET aangeroepen worden."""
    with patch("app.providers.live._tool_use_loop", new=AsyncMock(return_value={
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
    """LiveJaarverslagAgent.run() moet _zoek_jaarverslag_pdf aanroepen; fallback gemockt als None."""
    with patch("app.providers.live._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value=None)) as mock_zoek, \
         patch("app.providers.live._web_search_jaarverslag_wp",
               new=AsyncMock(return_value=None)):
        from app.providers.live import LiveJaarverslagAgent
        agent = LiveJaarverslagAgent()
        result = await agent.run("Mondriaan", 2025)
    mock_zoek.assert_called_once_with("Mondriaan", 2025, website_url=None, uitgesloten=set())
    assert result is None  # PDF niet gevonden, Fase-C fallback ook None


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
         patch("app.providers.live._classificeer_jaarverslag_bron_identiteit",
               new=AsyncMock(return_value=IdentityClass.EXACT_ENTITY)), \
         patch.object(
             __import__("app.providers.live", fromlist=["LiveJaarverslagAgent"]).LiveJaarverslagAgent,
             "run_with_pdf", new=AsyncMock(return_value=wp_finding)
         ):
        from app.providers.live import LiveJaarverslagAgent
        agent = LiveJaarverslagAgent()
        result = await agent.run("Mondriaan", 2025)
    assert result is not None
    assert result.wp_gevonden == 2281
    assert result.raw["identity_class"] == "exact_entity"


@pytest.mark.asyncio
async def test_live_jaarverslag_agent_keurt_pdf_van_ander_bedrijf_af():
    """Een gevonden PDF die aantoonbaar niet over het bedrijf gaat, mag niet worden
    verwerkt. Dit vangt o.a. Salon Handmade -> Heijmans-achtige mismatches af."""
    with patch("app.providers.live._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value="https://heijmans.test/jaarverslag-2025.pdf")), \
         patch("app.providers.live._classificeer_jaarverslag_bron_identiteit",
               new=AsyncMock(return_value=IdentityClass.MISMATCH)), \
         patch("app.providers.live.LiveJaarverslagAgent.run_with_pdf",
               new=AsyncMock(return_value=None)) as mock_extract, \
         patch("app.providers.live._web_search_jaarverslag_wp",
               new=AsyncMock(return_value=None)):
        from app.providers.live import LiveJaarverslagAgent
        agent = LiveJaarverslagAgent()
        result = await agent.run("Salon Handmade", 2025)

    assert result is None
    mock_extract.assert_not_called()


@pytest.mark.asyncio
async def test_live_jaarverslag_agent_probeert_opnieuw_na_afgewezen_bron():
    """Als de eerste gevonden PDF wordt afgewezen (verkeerd bedrijf), moet de graaf
    een ANDER zoekresultaat proberen i.p.v. meteen op te geven — dit was letterlijk
    het Mondriaan/Salon Handmade-scenario in productie."""
    from app.providers import live

    zoek_calls = []

    async def fake_zoek_pdf(naam, jaar, website_url=None, uitgesloten=None):
        zoek_calls.append(set(uitgesloten or set()))
        if not zoek_calls[-1]:
            return "https://onverwant-bedrijf.test/jaarverslag.pdf"
        return "https://echte-bron.test/jaarverslag.pdf"

    async def fake_identiteit(naam, pdf_url):
        if "onverwant-bedrijf" in (pdf_url or ""):
            return IdentityClass.MISMATCH
        return IdentityClass.EXACT_ENTITY

    goede_finding = AgentFinding(
        wp_gevonden=21, context="21 medewerkers", zekerheid="hoog",
        reden="jaarverslag", bron_url="https://echte-bron.test/jaarverslag.pdf",
        bron_type="jaarverslag",
    )

    with patch("app.providers.live._zoek_jaarverslag_pdf", new=fake_zoek_pdf), \
         patch("app.providers.live._classificeer_jaarverslag_bron_identiteit", new=fake_identiteit), \
         patch("app.providers.live.LiveJaarverslagAgent.run_with_pdf",
               new=AsyncMock(return_value=goede_finding)):
        result = await live.LiveJaarverslagAgent().run("Testbedrijf", 2025)

    assert result is not None
    assert result.bron_url == "https://echte-bron.test/jaarverslag.pdf"
    assert len(zoek_calls) == 2  # eerste poging afgewezen, tweede poging geslaagd
    assert "https://onverwant-bedrijf.test/jaarverslag.pdf" in zoek_calls[1]  # uitgesloten bij retry


@pytest.mark.asyncio
async def test_live_jaarverslag_agent_laat_brand_of_group_match_door():
    """Een concern/brandbron is niet hetzelfde als een mismatch. Die mag door naar
    extractie, waarna scope/reconciliatie bepaalt of het getal bruikbaar is."""
    wp_finding = AgentFinding(
        wp_gevonden=44485, context="Jumbo telt 44.485 medewerkers", zekerheid="middel",
        reden="jaarverslag", bron_url="https://jumborapportage.test/jaarverslag.pdf",
        bron_type="jaarverslag", is_limburg_specifiek=False,
    )
    with patch("app.providers.live._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value="https://jumborapportage.test/jaarverslag.pdf")), \
         patch("app.providers.live._classificeer_jaarverslag_bron_identiteit",
               new=AsyncMock(return_value=IdentityClass.SAME_BRAND_OR_GROUP)), \
         patch("app.providers.live.LiveJaarverslagAgent.run_with_pdf",
               new=AsyncMock(return_value=wp_finding)):
        from app.providers.live import LiveJaarverslagAgent
        agent = LiveJaarverslagAgent()
        result = await agent.run("Jumbo Supermarkten B.V. - Filiaal", 2025)

    assert result is not None
    assert result.raw["identity_class"] == "same_brand_or_group"


@pytest.mark.asyncio
async def test_monitoringmodus_weigert_onzekere_of_alleen_groepsmatch():
    """Monitoring mag een twijfelachtige bron niet als nieuwe baseline opslaan."""
    from app.providers import live

    async def fake_zoek_pdf(
        naam, jaar, website_url=None, uitgesloten=None,
    ):
        return "https://onbekende-bron.test/jaarverslag-2025.pdf"

    with patch(
        "app.providers.live._zoek_jaarverslag_pdf",
        new=fake_zoek_pdf,
    ), patch(
        "app.providers.live._classificeer_jaarverslag_bron_identiteit",
        new=AsyncMock(return_value=IdentityClass.SAME_BRAND_OR_GROUP),
    ), patch(
        "app.providers.live.LiveJaarverslagAgent.run_with_pdf",
        new=AsyncMock(),
    ) as extract:
        result = await live.LiveJaarverslagAgent().run(
            "Testbedrijf Limburg",
            2026,
            strict_identity=True,
        )

    assert result is None
    extract.assert_not_called()


@pytest.mark.asyncio
async def test_jaarverslagzoeker_slaat_aantoonbaar_verouderde_hit_over(
    monkeypatch,
):
    from app.providers import live

    async def fake_web_search(query, max_results=8):
        return [
            {
                "title": "Jaarverslag 2012",
                "url": "https://example.test/jaarverslag-2012.pdf",
            },
            {
                "title": "Jaarverslag 2025",
                "url": "https://example.test/jaarverslag-2025.pdf",
            },
        ]

    monkeypatch.setattr(live, "_web_search", fake_web_search)

    result = await live._zoek_jaarverslag_pdf_voor_jaar(
        "Testbedrijf",
        2025,
    )

    assert result == "https://example.test/jaarverslag-2025.pdf"


@pytest.mark.asyncio
async def test_jaarverslagzoeker_negeert_andere_pdf_op_officieel_domein(
    monkeypatch,
):
    from app.providers import live

    async def fake_web_search(query, max_results=8):
        return [{
            "title": "Privacy statement",
            "url": "https://example.test/privacy-statement.pdf",
        }]

    monkeypatch.setattr(live, "_web_search", fake_web_search)

    result = await live._zoek_jaarverslag_pdf_voor_jaar(
        "Testbedrijf",
        2025,
        website_url="https://example.test",
    )

    assert result is None


@pytest.mark.asyncio
async def test_live_jaarverslag_agent_handelt_pdf_fout_af():
    """Als run_with_pdf faalt en de web search-fallback (Fase C) niets oplevert,
    geeft de agent toch de gevonden bron_url door (zonder wp_gevonden) — zodat de
    jaarverslag-monitoring in elk geval een baseline-URL heeft, in plaats van de
    gevonden link stilzwijgend te laten vervallen."""
    with patch("app.providers.live._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value="https://example.com/broken.pdf")), \
         patch("app.providers.live._classificeer_jaarverslag_bron_identiteit",
               new=AsyncMock(return_value=IdentityClass.EXACT_ENTITY)), \
         patch("app.providers.live.LiveJaarverslagAgent.run_with_pdf",
               new=AsyncMock(side_effect=Exception("download fout"))), \
         patch("app.providers.live._web_search_jaarverslag_wp",
               new=AsyncMock(return_value=None)):
        from app.providers.live import LiveJaarverslagAgent
        agent = LiveJaarverslagAgent()
        result = await agent.run("TestBedrijf", 2025)
    assert result is not None
    assert result.bron_url == "https://example.com/broken.pdf"
    assert result.wp_gevonden is None


@pytest.mark.asyncio
async def test_extract_wp_zoekresultaten_slaat_cross_company_resultaat_over(monkeypatch):
    """Zoekresultaten waarvan titel/snippet/tekst de bedrijfsnaam niet noemen,
    worden niet naar de LLM gestuurd."""
    from app.providers import live

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")

    async def fake_fetch_text(url):
        return "Heijmans publiceerde een jaarverslag met 6158 medewerkers."

    async def fake_llm_extract(naam, gemeente, tekst):
        raise AssertionError("_llm_extract mag niet worden aangeroepen voor een mismatch")

    monkeypatch.setattr(live, "_fetch_text", fake_fetch_text)
    monkeypatch.setattr(live, "_llm_extract", fake_llm_extract)

    bevindingen = await live._extract_wp_van_zoekresultaten(
        "Salon Handmade",
        "Weert",
        [{
            "title": "Jaarverslag Heijmans 2025",
            "url": "https://heijmans.test/jaarverslag-2025.pdf",
            "snippet": "Heijmans publiceert jaarverslag",
            "bron": "test",
        }],
        bron_type="jaarverslag",
    )

    assert bevindingen == []


@pytest.mark.asyncio
async def test_extract_wp_zoekresultaten_slaat_vacaturepagina_over(monkeypatch):
    from app.providers import live

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")

    async def fake_fetch_text(url):
        raise AssertionError("_fetch_text mag niet worden aangeroepen voor vacaturepagina")

    monkeypatch.setattr(live, "_fetch_text", fake_fetch_text)

    bevindingen = await live._extract_wp_van_zoekresultaten(
        "IKEA Heerlen",
        "Heerlen",
        [{
            "title": "IKEA Heerlen jobs",
            "url": "https://jobs.ikea.com/nl/plaats/heerlen-jobs/22908/4",
            "snippet": "4 vacatures in Heerlen",
            "bron": "test",
        }],
        bron_type="media",
    )

    assert bevindingen == []


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
    mock_lookup.scrape_email = AsyncMock(return_value=None)

    mock_website = MagicMock()
    mock_website.run = AsyncMock(return_value=wp_finding)  # agent vindt wél iets
    mock_website.extra_bronnen = AsyncMock(return_value=[])

    mock_jaarverslag = MagicMock()
    mock_jaarverslag.run = AsyncMock(return_value=None)

    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(return_value=("unknown", "unknown"))

    with patch("app.pipeline.runner.get_providers",
               return_value=(mock_lookup, mock_website, mock_jaarverslag, mock_classifier)):
        candidate = await verwerk_company(db, company, batch)

    # Agent moet aangeroepen zijn ondanks lookup_failed
    mock_website.run.assert_called_once()
    # En het gevonden WP moet in de candidate zitten
    assert candidate.wp_kandidaat == 5


# --- Verbetering 5: jaarverslag-agent wordt overgeslagen bij hoog-zekerheid website ---

@pytest.mark.asyncio
async def test_runner_slaat_jaarverslag_agent_over_bij_hoog_zekerheid():
    """Kostenbeheersing én kwaliteit: bij een hoog-zekerheidsbevinding van de website-
    agent wordt de jaarverslag-agent overgeslagen. Dit voorkomt ook dat een generieke
    jaarverslag-zoekopdracht (vooral riskant bij kleine bedrijven zonder eigen
    jaarverslag) een onverwant document van een heel ander bedrijf oppikt."""
    from unittest.mock import MagicMock, AsyncMock, patch
    from app.pipeline.runner import verwerk_company

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

    hoog_finding = AgentFinding(
        wp_gevonden=100, context="100 medewerkers", zekerheid="hoog",
        reden="website", bron_url="https://example.com", bron_type="website",
        is_limburg_specifiek=True,
    )

    mock_lookup = MagicMock()
    mock_lookup.lookup = AsyncMock(return_value=None)
    mock_lookup.locations = AsyncMock(return_value=LocationInfo(count_nl=None, count_lb=None, bron="web_search"))
    mock_lookup.scrape_email = AsyncMock(return_value=None)

    mock_website = MagicMock()
    mock_website.run = AsyncMock(return_value=hoog_finding)
    mock_website.extra_bronnen = AsyncMock(return_value=[])

    mock_jaarverslag = MagicMock()
    mock_jaarverslag.run = AsyncMock(return_value=None)

    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(return_value=("unknown", "unknown"))

    with patch("app.pipeline.runner.get_providers",
               return_value=(mock_lookup, mock_website, mock_jaarverslag, mock_classifier)):
        await verwerk_company(db, company, batch)

    mock_jaarverslag.run.assert_not_called()
