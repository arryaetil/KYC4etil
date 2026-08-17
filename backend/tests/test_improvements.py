"""Tests voor de drie pipeline-verbeteringen:
1. Directe WP web search als Fase-C fallback in LiveWebsiteAgent
2. Jaarverslag-agent actief via web search
3. Lookup_failed blokkeert agents niet meer
"""
import httpx
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
    with patch("app.providers.wp_extractie._web_search_wp", new=AsyncMock(return_value=mock_finding)):
        from app.providers.live import LiveWebsiteAgent
        agent = LiveWebsiteAgent()
        result = await agent.run("TestBedrijf", None, None, gemeente="Maastricht")
    assert result is not None
    assert result.wp_gevonden == 42
    assert result.bron_type == "media"


@pytest.mark.asyncio
async def test_live_website_agent_slaat_web_search_over_als_scraping_slaagt():
    """Als de tool-use-loop een resultaat geeft, moet web search NIET aangeroepen worden."""
    with patch("app.providers.website_agent._tool_use_loop", new=AsyncMock(return_value={
             "wp_gevonden": 10, "context": "10 medewerkers", "zekerheid": "hoog",
             "reden": "ok", "is_totaal_meerdere_vestigingen": False,
             "is_limburg_specifiek": True, "is_fte": False, "peilmoment": "2024",
         })), \
         patch("app.providers.wp_extractie._web_search_wp", new=AsyncMock(return_value=None)) as mock_ws, \
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
    with patch("app.providers.jaarverslag_zoeken._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value=None)) as mock_zoek, \
         patch("app.providers.jaarverslag._web_search_jaarverslag_wp",
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
    with patch("app.providers.jaarverslag_zoeken._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value="https://example.com/jaarverslag.pdf")), \
         patch("app.providers.jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit",
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
    with patch("app.providers.jaarverslag_zoeken._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value="https://heijmans.test/jaarverslag-2025.pdf")), \
         patch("app.providers.jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit",
               new=AsyncMock(return_value=IdentityClass.MISMATCH)), \
         patch("app.providers.jaarverslag.LiveJaarverslagAgent.run_with_pdf",
               new=AsyncMock(return_value=None)) as mock_extract, \
         patch("app.providers.jaarverslag._web_search_jaarverslag_wp",
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
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

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

    with patch("app.providers.jaarverslag_zoeken._zoek_jaarverslag_pdf", new=fake_zoek_pdf), \
         patch("app.providers.jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit", new=fake_identiteit), \
         patch("app.providers.jaarverslag.LiveJaarverslagAgent.run_with_pdf",
               new=AsyncMock(return_value=goede_finding)):
        result = await jaarverslag.LiveJaarverslagAgent().run("Testbedrijf", 2025)

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
    with patch("app.providers.jaarverslag_zoeken._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value="https://jumborapportage.test/jaarverslag.pdf")), \
         patch("app.providers.jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit",
               new=AsyncMock(return_value=IdentityClass.SAME_BRAND_OR_GROUP)), \
         patch("app.providers.jaarverslag.LiveJaarverslagAgent.run_with_pdf",
               new=AsyncMock(return_value=wp_finding)):
        from app.providers.live import LiveJaarverslagAgent
        agent = LiveJaarverslagAgent()
        result = await agent.run("Jumbo Supermarkten B.V. - Filiaal", 2025)

    assert result is not None
    assert result.raw["identity_class"] == "same_brand_or_group"


@pytest.mark.asyncio
async def test_monitoringmodus_weigert_onzekere_of_alleen_groepsmatch():
    """Monitoring mag een twijfelachtige bron niet als nieuwe baseline opslaan."""
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    async def fake_zoek_pdf(
        naam, jaar, website_url=None, uitgesloten=None,
    ):
        return "https://onbekende-bron.test/jaarverslag-2025.pdf"

    with patch(
        "app.providers.jaarverslag_zoeken._zoek_jaarverslag_pdf",
        new=fake_zoek_pdf,
    ), patch(
        "app.providers.jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit",
        new=AsyncMock(return_value=IdentityClass.SAME_BRAND_OR_GROUP),
    ), patch(
        "app.providers.jaarverslag.LiveJaarverslagAgent.run_with_pdf",
        new=AsyncMock(),
    ) as extract:
        result = await jaarverslag.LiveJaarverslagAgent().run(
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
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

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

    monkeypatch.setattr(search, "_web_search", fake_web_search)

    result = await jaarverslag_zoeken._zoek_jaarverslag_pdf(
        "Testbedrijf",
        2025,
        zoekjaren=(2025,),
    )

    assert result == "https://example.test/jaarverslag-2025.pdf"


@pytest.mark.asyncio
async def test_jaarverslagzoeker_negeert_andere_pdf_op_officieel_domein(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    async def fake_web_search(query, max_results=8):
        return [{
            "title": "Privacy statement",
            "url": "https://example.test/privacy-statement.pdf",
        }]

    monkeypatch.setattr(search, "_web_search", fake_web_search)

    result = await jaarverslag_zoeken._zoek_jaarverslag_pdf(
        "Testbedrijf",
        2025,
        website_url="https://example.test",
        zoekjaren=(2025,),
    )

    assert result is None


@pytest.mark.asyncio
async def test_jaarverslagzoeker_gebruikt_hosted_fallback_bij_lege_indexen(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    monkeypatch.setattr(search, "_web_search",
        AsyncMock(return_value=[]),
    )
    hosted = AsyncMock(return_value=[{
        "title": "Testbedrijf jaarverslag 2025",
        "url": "https://testbedrijf.example/jaarverslag-2025.pdf",
        "snippet": "",
        "bron": "openai_web_search",
    }])
    monkeypatch.setattr(search, "_openai_web_search", hosted)

    result = await jaarverslag_zoeken._zoek_jaarverslag_pdf(
        "Testbedrijf",
        2025,
        website_url="https://testbedrijf.example",
        zoekjaren=(2025,),
    )

    assert result == "https://testbedrijf.example/jaarverslag-2025.pdf"
    hosted.assert_awaited_once()


@pytest.mark.asyncio
async def test_strikte_monitoring_weigert_oud_pdf_na_inhoudscontrole(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    monkeypatch.setattr(fetch, "_eerste_pdf_paginas",
        AsyncMock(return_value="Rijkswaterstaat Jaarverslag 2009"),
    )

    assert await jaarverslag_validatie._pdf_is_recent_jaarverslag(
        "https://example.test/opaque.pdf",
        2026,
    ) is False


@pytest.mark.asyncio
async def test_strikte_monitoring_accepteert_recent_pdf_na_inhoudscontrole(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    monkeypatch.setattr(fetch, "_eerste_pdf_paginas",
        AsyncMock(return_value="Bestuursverslag 2025 Zuyderland"),
    )

    assert await jaarverslag_validatie._pdf_is_recent_jaarverslag(
        "https://example.test/opaque.pdf",
        2026,
    ) is True


@pytest.mark.asyncio
async def test_strikte_monitoring_weigert_recente_toezichtbrief_die_jaarverslag_noemt(
    monkeypatch,
):
    """Een toezichtbrief over een jaarverslag is zelf geen jaarverslag."""
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    monkeypatch.setattr(fetch, "_eerste_pdf_paginas",
        AsyncMock(return_value=(
            "Toezichtbrief Autoriteit woningcorporaties 2024. "
            "Wij beoordeelden uw jaarverslag 2024."
        )),
    )

    assert await jaarverslag_validatie._pdf_is_recent_jaarverslag(
        "https://ilent.test/L0269-Stichting-ZOwonen.pdf",
        2026,
    ) is False


@pytest.mark.parametrize("documenttype", [
    "Jaarverslag cliëntenraad 2025",
    "Jaarverslag Commissie van Toezicht 2025",
    "Wederhoortabel jaarverslag 2025",
    "Investor Day transcript 2025 annual report",
    "Jaarverslag Raad en Griffie 2025",
    "Jaarverslag 2025 van de gouverneur",
    "Jaarverslag Raad van Toezicht 2025",
    "Jaarverslag VTH 2025",
    "https://example.test/dzjaarverslagccr2025.pdf",
    "https://example.test/dzjaarverslagrvt2025.pdf",
])
def test_jaarverslagherkenning_weigert_deelrapporten(documenttype):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    assert jaarverslag_zoeken._lijkt_jaarverslag(documenttype, 2025) is False


def test_hoofdverslag_mag_inhoudelijk_een_raad_van_toezicht_noemen():
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    assert jaarverslag_zoeken._lijkt_jaarverslag(
        "Bestuursverslag 2024\nInhoud\nVerslag van de Raad van Toezicht",
        2024,
        weiger_deelrapporten=False,
    ) is True


@pytest.mark.asyncio
async def test_officiele_jaarverslagpagina_verkiest_organisatiebreed_verslag(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    class Response:
        text = """
            <a href="/bestuursverslag-2024.pdf">Bestuursverslag 2024</a>
            <a href="/jaarverslag-rvt-2024.pdf">Jaarverslag Raad van Toezicht 2024</a>
            <a href="/jaarverslag-ccr-2024.pdf">Jaarverslag cliëntenraad 2024</a>
        """

        def raise_for_status(self):
            return None

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            return Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())

    result = await jaarverslag_zoeken._scrape_pdf_van_pagina(
        "https://organisatie.test/jaarverslagen",
        2024,
    )

    assert result == "https://organisatie.test/bestuursverslag-2024.pdf"


@pytest.mark.asyncio
async def test_geldige_jaarverslagbron_blijft_behouden_zonder_wp_getal(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    url = "https://organisatie.test/bestuursverslag-2024.pdf"

    async def fake_zoek(*args, uitgesloten=None, **kwargs):
        return None if url in (uitgesloten or set()) else url

    monkeypatch.setattr(jaarverslag_zoeken, "_zoek_jaarverslag_pdf", fake_zoek)
    monkeypatch.setattr(
        jaarverslag.LiveJaarverslagAgent,
        "run_with_pdf",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(jaarverslag_validatie, "_pdf_is_recent_jaarverslag", AsyncMock(return_value=True))
    monkeypatch.setattr(jaarverslag_validatie, "_is_organisatiebreed_jaarverslag",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(live.settings, "jaarverslag_web_fallback", False)

    finding = await jaarverslag._run_jaarverslag_research_graph(
        "Organisatie",
        2026,
        website_url="https://organisatie.test",
        strict_identity=True,
    )

    assert finding is not None
    assert finding.bron_url == url
    assert finding.wp_gevonden is None


@pytest.mark.asyncio
async def test_strikte_monitoring_weigert_jaarverslag_van_deelorganisatie(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    deelrapport = "https://organisatie.test/vrienden-jaarrekening-2025.pdf"
    hoofdrapport = "https://organisatie.test/bestuursverslag-2024.pdf"

    async def fake_zoek(*args, uitgesloten=None, **kwargs):
        uitgesloten = uitgesloten or set()
        if hoofdrapport in uitgesloten:
            return None
        return hoofdrapport if deelrapport in uitgesloten else deelrapport

    monkeypatch.setattr(jaarverslag_zoeken, "_zoek_jaarverslag_pdf", fake_zoek)
    monkeypatch.setattr(jaarverslag_validatie, "_is_organisatiebreed_jaarverslag",
        AsyncMock(side_effect=[False, True]),
    )
    monkeypatch.setattr(jaarverslag_validatie, "_pdf_is_recent_jaarverslag", AsyncMock(return_value=True))
    monkeypatch.setattr(
        jaarverslag.LiveJaarverslagAgent,
        "run_with_pdf",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(live.settings, "jaarverslag_web_fallback", False)

    finding = await jaarverslag._run_jaarverslag_research_graph(
        "Organisatie",
        2026,
        website_url="https://organisatie.test",
        strict_identity=True,
    )

    assert finding is not None
    assert finding.bron_url == hoofdrapport


@pytest.mark.asyncio
async def test_monitoring_sourcezoeker_slaat_wp_extractie_over(monkeypatch):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    url = "https://organisatie.test/bestuursverslag-2024.pdf"
    monkeypatch.setattr(jaarverslag_zoeken, "_zoek_jaarverslag_pdf", AsyncMock(return_value=url))
    monkeypatch.setattr(jaarverslag_validatie, "_is_organisatiebreed_jaarverslag",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(fetch, "_eerste_pdf_paginas",
        AsyncMock(return_value="Bestuursverslag Organisatie 2024"),
    )
    extract = AsyncMock()
    monkeypatch.setattr(jaarverslag.LiveJaarverslagAgent, "run_with_pdf", extract)

    finding = await jaarverslag.LiveJaarverslagAgent().find_latest_source(
        "Organisatie",
        2026,
        website_url="https://organisatie.test",
        strict_identity=True,
    )

    assert finding is not None
    assert finding.bron_url == url
    assert finding.wp_gevonden is None
    extract.assert_not_awaited()


@pytest.mark.asyncio
async def test_monitoring_sourcezoeker_zoekt_nieuwer_jaar_als_combined_search_oud_resultaat_geeft(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    oud = "https://organisatie.test/bestuursverslag-2023.pdf"
    nieuw = "https://organisatie.test/bestuursverslag-2025.pdf"

    async def fake_zoek(*args, uitgesloten=None, zoekjaren=None, **kwargs):
        if zoekjaren == (2025, 2024) and nieuw not in (uitgesloten or set()):
            return nieuw
        return None if oud in (uitgesloten or set()) else oud

    monkeypatch.setattr(jaarverslag_zoeken, "_zoek_jaarverslag_pdf", fake_zoek)
    monkeypatch.setattr(fetch, "_eerste_pdf_paginas",
        AsyncMock(side_effect=[
            "Jaarverslag Organisatie 2023",
            "Jaarverslag Organisatie 2025",
        ]),
    )
    monkeypatch.setattr(jaarverslag_validatie, "_is_organisatiebreed_jaarverslag",
        AsyncMock(return_value=True),
    )

    finding = await jaarverslag.LiveJaarverslagAgent().find_latest_source(
        "Organisatie",
        2026,
        website_url="https://organisatie.test",
        strict_identity=True,
    )

    assert finding is not None
    assert finding.bron_url == nieuw
    assert finding.raw["verslagjaar"] == 2025


@pytest.mark.parametrize(("tekst", "verwacht"), [
    ("4 February 2026\n2025 ANNUAL REPORT\nFY 2025", 2025),
    ("Inhoudelijk jaarverslag 2024\nVooruitblik 2025", 2024),
    ("Bestuursverslag\n2024\nVastgesteld in 2025", 2024),
])
def test_verslagjaar_komt_uit_documenttitel_niet_publicatiejaar(tekst, verwacht):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    assert jaarverslag_zoeken._verslagjaar_uit_pdftekst(tekst, 2026) == verwacht


@pytest.mark.asyncio
async def test_nederlandse_organisatie_weigert_belgische_naamgenoot(monkeypatch):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    belgisch = "https://koraal.be/jaarverslag-2024.pdf"
    monkeypatch.setattr(jaarverslag_zoeken, "_zoek_jaarverslag_pdf", AsyncMock(return_value=belgisch))
    monkeypatch.setattr(fetch, "_eerste_pdf_paginas",
        AsyncMock(return_value="Koraal jaarverslag 2024"),
    )
    scope = AsyncMock(return_value=True)
    monkeypatch.setattr(jaarverslag_validatie, "_is_organisatiebreed_jaarverslag", scope)

    finding = await jaarverslag.LiveJaarverslagAgent().find_latest_source(
        "Koraal Groep",
        2026,
        website_url="https://www.koraal.nl",
        strict_identity=True,
    )

    assert finding is None
    scope.assert_not_awaited()
    assert fetch._heeft_landdomein_conflict(
        belgisch,
        "https://www.koraal.nl",
    ) is True


@pytest.mark.asyncio
async def test_jaarverslagzoeker_zoekt_drie_jaren_in_een_provider_ronde(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    web_search = AsyncMock(return_value=[{
        "title": "Annual Report 2025",
        "url": "https://organisatie.test/annual-report-2025.pdf",
    }])
    hosted = AsyncMock(return_value=[])
    monkeypatch.setattr(search, "_web_search", web_search)
    monkeypatch.setattr(search, "_openai_web_search", hosted)

    result = await jaarverslag_zoeken._zoek_jaarverslag_pdf("Organisatie", 2026)

    assert result == "https://organisatie.test/annual-report-2025.pdf"
    # Eén provider-ronde voor drie verslagjaren: de jaarselectie gebeurt op de
    # resultaten (nieuwste-eerst), niet door de jaartallen in de zoekstring te
    # zetten — die verwateren de zoekopdracht juist.
    web_search.assert_awaited_once()
    query = web_search.await_args.args[0]
    assert "Organisatie" in query
    assert not any(str(jaar) in query for jaar in (2025, 2024, 2023))
    hosted.assert_not_awaited()


@pytest.mark.asyncio
async def test_generieke_eenwoordnaam_is_zonder_domein_geen_exacte_identiteit(
    monkeypatch,
):
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    monkeypatch.setattr(fetch, "_eerste_pdf_paginas",
        AsyncMock(return_value=(
            "Bestuursverslag 2025 van Zorggroep Sint Maarten"
        )),
    )

    identity = await jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit(
        "De Zorggroep",
        "https://andere-zorggroep.example/bestuursverslag-2025.pdf",
    )

    assert identity == IdentityClass.UNKNOWN


def test_safelink_wordt_teruggebracht_naar_echte_bron_url():
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    result = fetch._unwrap_safelink(
        "https://eur05.safelinks.protection.outlook.com/"
        "?url=https%3A%2F%2Fexample.test%2FJaarverslag%25202025.pdf"
        "&data=tracking",
    )

    assert result == "https://example.test/Jaarverslag%202025.pdf"


def test_deterministische_pdf_fallback_vindt_explicitiete_headcount():
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    result = jaarverslag._deterministische_wp_uit_pdf([
        (1, "Voorwoord"),
        (
            6,
            "Door de unieke samenstelling biedt Zuyderland aan bijna "
            "11.000 medewerkers de baan van hun leven.",
        ),
    ])

    assert result is not None
    assert result["wp_gevonden"] == 11000
    assert result["bron_pagina"] == 6
    assert result["extractiemethode"] == "deterministische_fallback"


def test_deterministische_pdf_fallback_negeert_deelnemersaantal():
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    result = jaarverslag._deterministische_wp_uit_pdf([
        (
            32,
            "Het medewerkersonderzoek had bijna 4.900 deelnemers en "
            "leverde waardevolle inzichten op.",
        ),
    ])

    assert result is None


@pytest.mark.asyncio
async def test_live_jaarverslag_agent_handelt_pdf_fout_af():
    """Als run_with_pdf faalt en de web search-fallback (Fase C) niets oplevert,
    geeft de agent toch de gevonden bron_url door (zonder wp_gevonden) — zodat de
    jaarverslag-monitoring in elk geval een baseline-URL heeft, in plaats van de
    gevonden link stilzwijgend te laten vervallen."""
    with patch("app.providers.jaarverslag_zoeken._zoek_jaarverslag_pdf",
               new=AsyncMock(return_value="https://example.com/broken.pdf")), \
         patch("app.providers.jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit",
               new=AsyncMock(return_value=IdentityClass.EXACT_ENTITY)), \
         patch("app.providers.jaarverslag.LiveJaarverslagAgent.run_with_pdf",
               new=AsyncMock(side_effect=Exception("download fout"))), \
         patch("app.providers.jaarverslag._web_search_jaarverslag_wp",
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
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")

    async def fake_fetch_text(url):
        return "Heijmans publiceerde een jaarverslag met 6158 medewerkers."

    async def fake_llm_extract(naam, gemeente, tekst):
        raise AssertionError("_llm_extract mag niet worden aangeroepen voor een mismatch")

    monkeypatch.setattr(fetch, "_fetch_text", fake_fetch_text)
    monkeypatch.setattr(llm, "_llm_extract", fake_llm_extract)

    bevindingen = await wp_extractie._extract_wp_van_zoekresultaten(
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
    from app.providers import fetch, jaarverslag, jaarverslag_validatie, jaarverslag_zoeken, live, llm, search, website_agent, wp_extractie

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")

    async def fake_fetch_text(url):
        raise AssertionError("_fetch_text mag niet worden aangeroepen voor vacaturepagina")

    monkeypatch.setattr(fetch, "_fetch_text", fake_fetch_text)

    bevindingen = await wp_extractie._extract_wp_van_zoekresultaten(
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


def test_llm_getal_dat_geen_getal_is_laat_de_controle_niet_klappen():
    """Regressie uit de live monitoringronde van 17-08-2026.

    Bij Stichting XONAR sloeg de hele jaarverslagcontrole stuk op
    `invalid literal for int() with base 10: '8d\xc2\x94...'`: de bron was een PDF
    die als platte tekst werd binnengehaald, de LLM kreeg bytes te zien en gaf
    een stuk van die ruis terug als `wp_gevonden`. Externe tekst is
    onbetrouwbare invoer, dus ook wat de LLM eruit terugkoppelt.
    """
    from app.providers.wp_extractie import _als_aantal

    assert _als_aantal("8d\x94\x159n\x10\x10\x7f") is None
    assert _als_aantal(None) is None
    assert _als_aantal("") is None
    assert _als_aantal("ongeveer 40") is None
    assert _als_aantal(True) is None
    # Duizendscheiding mag: zo staat het in Nederlandse jaarverslagen.
    assert _als_aantal("1.204") == 1204
    assert _als_aantal("1 204") == 1204
    assert _als_aantal(1204) == 1204
    assert _als_aantal(1204.0) == 1204
