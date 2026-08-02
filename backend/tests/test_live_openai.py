from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.providers import live


class _FakeResponse:
    output_text = '{"wp_gevonden": 7, "context": "Er werken 7 medewerkers.", "zekerheid": "hoog"}'


class _FakeResponses:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return _FakeResponse()


class _FakeOpenAI:
    last_responses = None

    def __init__(self, api_key):
        self.api_key = api_key
        self.responses = _FakeResponses()
        _FakeOpenAI.last_responses = self.responses


@pytest.mark.asyncio
async def test_openai_extract_parseert_json(monkeypatch):
    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "openai_model", "gpt-test")

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeOpenAI)

    result = await live._llm_extract("Testbedrijf", "Markt 1", "Er werken 7 medewerkers.")

    assert result["wp_gevonden"] == 7
    assert _FakeOpenAI.last_responses.kwargs["model"] == "gpt-test"
    assert _FakeOpenAI.last_responses.kwargs["text"]["format"]["type"] == "json_object"


@pytest.mark.asyncio
async def test_llm_extract_registreert_tokenverbruik(monkeypatch):
    from app.research import usage

    class UsageResponse:
        output_text = '{"wp_gevonden": 47}'
        usage = type("Usage", (), {"input_tokens": 120, "output_tokens": 30})()

    class UsageResponses:
        async def create(self, **kwargs):
            return UsageResponse()

    class UsageOpenAI:
        def __init__(self, api_key):
            self.responses = UsageResponses()

    import openai
    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(openai, "AsyncOpenAI", UsageOpenAI)

    usage.start_usage_tracking()
    await live._llm_extract("Voorbeeld Zorg", "Adres 1", "47 medewerkers.")

    assert usage.get_usage_totals() == (120, 30)


@pytest.mark.asyncio
async def test_openai_web_search_parseert_bronnen_en_citaties(monkeypatch):
    class SearchResponse:
        output_text = "De officiële website en het jaarverslag zijn gevonden."

        def model_dump(self):
            return {
                "output": [
                    {
                        "type": "web_search_call",
                        "action": {
                            "sources": None,
                        },
                    },
                    {
                        "type": "message",
                        "content": [{
                            "annotations": [{
                                "type": "url_citation",
                                "url": "https://example.test/jaarverslag.pdf",
                                "title": "Jaarverslag 2025",
                            }],
                        }],
                    },
                ],
            }

    class SearchResponses:
        async def create(self, **kwargs):
            assert kwargs["tools"][0]["type"] == "web_search"
            assert kwargs["tool_choice"] == "required"
            return SearchResponse()

    class SearchOpenAI:
        def __init__(self, api_key):
            self.responses = SearchResponses()

    import openai
    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "openai_web_search_model", "gpt-test")
    monkeypatch.setattr(openai, "AsyncOpenAI", SearchOpenAI)

    results = await live._openai_web_search("Example jaarverslag", 5)

    assert [item["url"] for item in results] == [
        "https://example.test/jaarverslag.pdf",
    ]
    assert all(item["bron"] == "openai_web_search" for item in results)


@pytest.mark.asyncio
async def test_openai_contact_fallback_negeert_bedrijvengids(monkeypatch):
    async def fake_search(query, max_results=6):
        return [
            {
                "title": "Okechamp jaarverslag",
                "url": "https://cdn.example.test/okechamp-jaarverslag.pdf",
                "snippet": "Okechamp",
            },
            {
                "title": "Okechamp bedrijvengids",
                "url": "https://drimble.nl/bedrijf/okechamp",
                "snippet": "Okechamp",
            },
            {
                "title": "OKECHAMP B.V.",
                "url": "https://www.okechamp.eu/",
                "snippet": "Official OKECHAMP website",
            },
        ]

    monkeypatch.setattr(live, "_openai_web_search", fake_search)

    result = await live._openai_contact_fallback(
        "Okechamp B.V.", "Horst aan de Maas",
    )

    assert result.website == "https://www.okechamp.eu/"
    assert result.raw["bron"] == "openai_web_search"


@pytest.mark.asyncio
async def test_web_search_contact_valt_terug_op_serper_als_duckduckgo_niets_geeft(monkeypatch):
    async def fake_ddg(query, max_results=6):
        return []

    async def fake_serper(query, max_results=6):
        return [{"title": "Testbedrijf", "url": "https://example.test",
                  "snippet": "", "bron": "serper"}]

    async def fake_fetch_text(url):
        return "Testbedrijf Maastricht. Bel ons op 043-1234567 voor meer info."

    monkeypatch.setattr(live, "_duckduckgo_search", fake_ddg)
    monkeypatch.setattr(live, "_serper_search", fake_serper)
    monkeypatch.setattr(live, "_fetch_text", fake_fetch_text)

    result = await live._web_search_contact("Testbedrijf", "Maastricht")

    assert result.website == "https://example.test"
    assert result.phone == "043-1234567"
    assert result.raw["bron"] == "serper"


@pytest.mark.asyncio
async def test_web_search_contact_geeft_none_als_geen_zoekresultaten(monkeypatch):
    async def fake_ddg(query, max_results=6):
        return []

    async def fake_serper(query, max_results=6):
        return []

    monkeypatch.setattr(live, "_duckduckgo_search", fake_ddg)
    monkeypatch.setattr(live, "_serper_search", fake_serper)

    result = await live._web_search_contact("Testbedrijf", "Maastricht")

    assert result is None


@pytest.mark.asyncio
async def test_web_search_combineert_duckduckgo_en_serper(monkeypatch):
    async def fake_duckduckgo(query, max_results=5):
        return [
            {"title": "Team", "url": "https://example.test/team?utm_source=ddg",
             "snippet": "47 medewerkers", "bron": "duckduckgo"},
        ]

    async def fake_serper(query, max_results=5):
        return [
            {"title": "Team", "url": "https://example.test/team",
             "snippet": "Team van Example", "bron": "serper"},
            {"title": "Nieuws", "url": "https://nieuws.test/example",
             "snippet": "Example groeit", "bron": "serper"},
        ]

    monkeypatch.setattr(live, "_duckduckgo_search", fake_duckduckgo)
    monkeypatch.setattr(live, "_serper_search", fake_serper)

    results = await live._web_search("Example medewerkers", max_results=5)

    assert len(results) == 2
    assert results[0]["bronnen"] == ["duckduckgo", "serper"]
    assert results[0]["bron"] == "duckduckgo+serper"


@pytest.mark.asyncio
async def test_places_lookup_valt_terug_op_web_search_bij_google_http_fout(monkeypatch):
    class FailingGoogleClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request("POST", live.PLACES_SEARCH_URL)
            response = httpx.Response(400, request=request)
            raise httpx.HTTPStatusError("Bad Request", request=request, response=response)

    async def fake_web_search_contact(naam, gemeente):
        return live.PlacesResult(
            website="https://fallback.test",
            phone="043-7654321",
            adres="Markt 2",
            raw={"bron": "openai_web_search"},
        )

    monkeypatch.setattr(live.settings, "google_places_api_key", "ongeldige-key")
    monkeypatch.setattr(live.httpx, "AsyncClient", FailingGoogleClient)
    monkeypatch.setattr(live, "_web_search_contact", fake_web_search_contact)

    result = await live.LivePlacesProvider().lookup("Testbedrijf", "Maastricht")

    assert result.website == "https://fallback.test"
    assert result.phone == "043-7654321"


@pytest.mark.asyncio
async def test_places_zonder_website_is_geen_succesvolle_lookup(monkeypatch):
    async def fake_serper_places(query):
        return {
            "title": "Mondriaan",
            "address": "Heerlen",
            "website": None,
        }

    async def fake_web_search_contact(naam, gemeente):
        return live.PlacesResult(
            website="https://www.mondriaan.eu",
            phone="088-5066262",
            adres="Heerlen",
            raw={"bron": "web_search"},
        )

    monkeypatch.setattr(live.settings, "google_places_api_key", "")
    monkeypatch.setattr(live, "_serper_places", fake_serper_places)
    monkeypatch.setattr(live, "_web_search_contact", fake_web_search_contact)

    result = await live.LivePlacesProvider().lookup("Mondriaan", "Heerlen")

    assert result.website == "https://www.mondriaan.eu"


@pytest.mark.asyncio
async def test_google_place_zonder_website_valt_terug_op_web_search(
    monkeypatch,
):
    class GoogleWithoutWebsiteClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            request = httpx.Request("POST", live.PLACES_SEARCH_URL)
            return httpx.Response(
                200,
                request=request,
                json={"places": [{
                    "formattedAddress": "Oude Venloseweg 84, Velden",
                }]},
            )

    async def fake_serper_places(query):
        return None

    async def fake_web_search_contact(naam, gemeente):
        return live.PlacesResult(
            website="https://www.okechamp.eu/",
            adres="Oude Venloseweg 84, Velden",
            raw={"bron": "web_search"},
        )

    monkeypatch.setattr(live.settings, "google_places_api_key", "test-key")
    monkeypatch.setattr(live.httpx, "AsyncClient", GoogleWithoutWebsiteClient)
    monkeypatch.setattr(live, "_serper_places", fake_serper_places)
    monkeypatch.setattr(
        live, "_web_search_contact", fake_web_search_contact,
    )

    result = await live.LivePlacesProvider().lookup(
        "Okechamp B.V.", "Horst aan de Maas",
    )

    assert result.website == "https://www.okechamp.eu/"


@pytest.mark.asyncio
async def test_web_search_contact_weigert_naamgenoot_buiten_gemeente(monkeypatch):
    async def fake_web_search(query, max_results=6):
        return [
            {
                "title": "ROC Mondriaan",
                "url": "https://www.rocmondriaan.nl",
                "snippet": "Onderwijs in Den Haag",
                "bron": "serper",
            },
            {
                "title": "Mondriaan",
                "url": "https://www.mondriaan.eu",
                "snippet": "Geestelijke gezondheidszorg in Heerlen",
                "bron": "serper",
            },
        ]

    async def fake_fetch_text(url):
        return {
            "https://www.rocmondriaan.nl": "ROC Mondriaan in Den Haag",
            "https://www.mondriaan.eu": "Mondriaan, John F. Kennedylaan in Heerlen",
        }[url]

    monkeypatch.setattr(live, "_web_search", fake_web_search)
    monkeypatch.setattr(live, "_fetch_text", fake_fetch_text)

    result = await live._web_search_contact("Mondriaan", "Heerlen")

    assert result.website == "https://www.mondriaan.eu"


@pytest.mark.asyncio
async def test_web_search_contact_accepteert_exact_merkdomein_bij_oude_gemeente(
    monkeypatch,
):
    async def fake_web_search(query, max_results=6):
        return [{
            "title": "OKECHAMP B.V.",
            "url": "https://www.okechamp.eu/",
            "snippet": "Mushroom processing in Velden",
            "bron": "serper",
        }]

    async def fake_fetch_text(url):
        return "OKECHAMP B.V. Oude Venloseweg 84, Velden"

    monkeypatch.setattr(live, "_web_search", fake_web_search)
    monkeypatch.setattr(live, "_fetch_text", fake_fetch_text)

    result = await live._web_search_contact(
        "Okechamp B.V.", "Horst aan de Maas",
    )

    assert result.website == "https://www.okechamp.eu/"


@pytest.mark.asyncio
async def test_web_search_contact_herprobeert_zonder_foutieve_gemeente(
    monkeypatch,
):
    queries = []

    async def fake_web_search(query, max_results=6):
        queries.append(query)
        if "Horst aan de Maas" in query:
            return []
        return [{
            "title": "OKECHAMP B.V.",
            "url": "https://www.okechamp.eu/",
            "snippet": "Official OKECHAMP website",
            "bron": "serper",
        }]

    async def fake_fetch_text(url):
        return "OKECHAMP B.V., Oude Venloseweg 84, Velden"

    monkeypatch.setattr(live, "_web_search", fake_web_search)
    monkeypatch.setattr(live, "_fetch_text", fake_fetch_text)

    result = await live._web_search_contact(
        "Okechamp B.V.", "Horst aan de Maas",
    )

    assert result.website == "https://www.okechamp.eu/"
    assert len(queries) == 2
    assert "Horst aan de Maas" not in queries[1]


@pytest.mark.asyncio
async def test_openai_extract_parseert_wp_uitsplitsing(monkeypatch):
    class _FakeUitsplitsingResponse:
        output_text = (
            '{"wp_gevonden": 100, "context": "ctx", "zekerheid": "hoog", '
            '"man": 60, "vrouw": 40, "voltijd": 80, "deeltijd": 20, '
            '"eigen_personeel": 70, "uitzend": 20, "detachering": 10, "wsw": 0, '
            '"pct_op_locatie": 90}'
        )

    class _FakeUitsplitsingResponses(_FakeResponses):
        async def create(self, **kwargs):
            self.kwargs = kwargs
            return _FakeUitsplitsingResponse()

    class _FakeUitsplitsingOpenAI(_FakeOpenAI):
        def __init__(self, api_key):
            self.api_key = api_key
            self.responses = _FakeUitsplitsingResponses()
            _FakeUitsplitsingOpenAI.last_responses = self.responses

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "openai_model", "gpt-test")

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeUitsplitsingOpenAI)

    result = await live._llm_extract("Testbedrijf", "Markt 1", "Er werken 100 medewerkers.")

    assert result["man"] == 60
    assert result["vrouw"] == 40
    assert result["voltijd"] == 80
    assert result["deeltijd"] == 20
    assert result["eigen_personeel"] == 70
    assert result["uitzend"] == 20
    assert result["detachering"] == 10
    assert result["wsw"] == 0
    assert result["pct_op_locatie"] == 90


@pytest.mark.asyncio
async def test_verzamel_extra_media_bronnen_verzamelt_meerdere(monkeypatch):
    zoekresultaten = [
        {"title": "LinkedIn", "url": "https://linkedin.com/company/testbedrijf", "snippet": "", "bron": "serper"},
        {"title": "KvK", "url": "https://kvk.nl/testbedrijf", "snippet": "", "bron": "serper"},
        {"title": "Nieuws", "url": "https://nieuws.test/testbedrijf", "snippet": "", "bron": "serper"},
    ]

    async def fake_web_search(query, max_results=5):
        return zoekresultaten

    teksten = {
        "https://linkedin.com/company/testbedrijf": "50 medewerkers volgens LinkedIn.",
        "https://kvk.nl/testbedrijf": "geen relevante informatie",
        "https://nieuws.test/testbedrijf": "60 medewerkers meldt het nieuwsartikel.",
    }

    async def fake_fetch_text(url):
        return teksten[url]

    async def fake_llm_extract(naam, gemeente, tekst):
        if "50 medewerkers" in tekst:
            return {"wp_gevonden": 50, "context": tekst, "zekerheid": "middel"}
        if "60 medewerkers" in tekst:
            return {"wp_gevonden": 60, "context": tekst, "zekerheid": "laag"}
        return {"wp_gevonden": None}

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "extra_bronnen_aantal", 2)
    monkeypatch.setattr(live, "_web_search", fake_web_search)
    monkeypatch.setattr(live, "_fetch_text", fake_fetch_text)
    monkeypatch.setattr(live, "_llm_extract", fake_llm_extract)

    resultaat = await live.verzamel_extra_media_bronnen("Testbedrijf", "Maastricht")

    assert len(resultaat) == 2
    assert {r.wp_gevonden for r in resultaat} == {50, 60}
    assert all(r.bron_type == "media" for r in resultaat)


@pytest.mark.asyncio
async def test_verzamel_extra_media_bronnen_sluit_bekende_urls_uit(monkeypatch):
    async def fake_web_search(query, max_results=5):
        return [{"title": "Website", "url": "https://example.test", "snippet": "", "bron": "serper"}]

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "extra_bronnen_aantal", 2)
    monkeypatch.setattr(live, "_web_search", fake_web_search)

    resultaat = await live.verzamel_extra_media_bronnen(
        "Testbedrijf", "Maastricht", uitsluiten={"https://example.test"},
    )

    assert resultaat == []


@pytest.mark.asyncio
async def test_verzamel_extra_media_bronnen_uit_via_config(monkeypatch):
    monkeypatch.setattr(live.settings, "extra_bronnen_aantal", 0)
    resultaat = await live.verzamel_extra_media_bronnen("Testbedrijf", "Maastricht")
    assert resultaat == []


@pytest.mark.asyncio
async def test_zoek_jaarverslag_pdf_probeert_eerst_site_scoped_zoekopdracht(monkeypatch):
    """Bij een bekend domein moet eerst site:-scoped gezocht worden — dat is veel
    minder gevoelig voor niet-determinisme dan een open zoekopdracht op alleen de naam
    (zie Mondriaan-casus: open zoeken vond soms een onverwant kwaliteitsverslag)."""
    gedane_queries = []

    async def fake_web_search(query, max_results=8):
        gedane_queries.append(query)
        if query.startswith("site:mondriaan.eu"):
            return [{"title": "Jaarverantwoording", "url": "https://mondriaan.eu/jaarverantwoording-2025.pdf",
                      "snippet": "", "bron": "serper"}]
        return [{"title": "Kwaliteitsverslag (fout document)", "url": "https://mondriaan.eu/kwaliteitsverslag.pdf",
                  "snippet": "", "bron": "serper"}]

    monkeypatch.setattr(live, "_web_search", fake_web_search)

    resultaat = await live._zoek_jaarverslag_pdf(
        "Mondriaan", 2026, website_url="https://www.mondriaan.eu/",
    )

    assert resultaat == "https://mondriaan.eu/jaarverantwoording-2025.pdf"
    assert gedane_queries[0].startswith("site:mondriaan.eu")


@pytest.mark.asyncio
async def test_zoek_jaarverslag_pdf_valt_terug_op_open_zoekopdracht_zonder_domein_resultaat(monkeypatch):
    async def fake_web_search(query, max_results=8):
        if query.startswith("site:"):
            return []
        return [{"title": "Jaarverslag", "url": "https://example.test/jaarverslag.pdf",
                  "snippet": "", "bron": "serper"}]

    monkeypatch.setattr(live, "_web_search", fake_web_search)

    resultaat = await live._zoek_jaarverslag_pdf(
        "Testbedrijf", 2026, website_url="https://www.example.test/",
    )

    assert resultaat == "https://example.test/jaarverslag.pdf"


@pytest.mark.asyncio
async def test_zoek_jaarverslag_pdf_zonder_bekend_domein_zoekt_alleen_open(monkeypatch):
    gedane_queries = []

    async def fake_web_search(query, max_results=8):
        gedane_queries.append(query)
        return []

    monkeypatch.setattr(live, "_web_search", fake_web_search)

    monkeypatch.setattr(live, "_openai_web_search", AsyncMock(return_value=[]))

    await live._zoek_jaarverslag_pdf("Testbedrijf", 2026, website_url=None)

    # Zonder bekend domein mag er geen site:-scoped zoekopdracht worden gedaan.
    assert not any(q.startswith("site:") for q in gedane_queries)


def test_vind_paginanummer_vindt_juiste_pagina():
    pagina_teksten = [
        (1, "Voorwoord van de directie."),
        (2, "In 2024 waren er 2294 medewerkers en vrijwilligers actief."),
        (3, "Financiële verantwoording."),
    ]
    resultaat = live._vind_paginanummer(
        "In 2024 waren er 2294 medewerkers en vrijwilligers actief.", pagina_teksten,
    )
    assert resultaat == 2


def test_vind_paginanummer_geeft_none_als_context_ontbreekt():
    assert live._vind_paginanummer(None, [(1, "tekst")]) is None


def test_vind_paginanummer_geeft_none_als_niet_gevonden():
    assert live._vind_paginanummer("dit staat nergens in", [(1, "andere tekst")]) is None


@pytest.mark.asyncio
async def test_web_search_jaarverslag_wp_geeft_uitsplitsing_door(monkeypatch):
    class _FakeJaarverslagResponse:
        output_text = (
            '{"wp_gevonden": 100, "context": "ctx", "zekerheid": "hoog", "reden": "t", '
            '"is_limburg_specifiek": true, "is_fte": false, "peilmoment": "2026", '
            '"man": 60, "vrouw": 40, "voltijd": 80, "deeltijd": 20, '
            '"eigen_personeel": 70, "uitzend": 20, "detachering": 10, "wsw": 0, '
            '"pct_op_locatie": 90}'
        )

    class _FakeJaarverslagResponses(_FakeResponses):
        async def create(self, **kwargs):
            self.kwargs = kwargs
            return _FakeJaarverslagResponse()

    class _FakeJaarverslagOpenAI(_FakeOpenAI):
        def __init__(self, api_key):
            self.api_key = api_key
            self.responses = _FakeJaarverslagResponses()
            _FakeJaarverslagOpenAI.last_responses = self.responses

    async def fake_web_search(query, max_results=5):
        return [{"title": "Testbedrijf jaarverslag", "url": "https://example.test/jaarverslag.pdf",
                  "snippet": "", "bron": "serper"}]

    async def fake_fetch_text(url):
        return "Jaarverslag 2026: er werken 100 medewerkers."

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "openai_model", "gpt-test")
    monkeypatch.setattr(live, "_web_search", fake_web_search)
    monkeypatch.setattr(live, "_fetch_text", fake_fetch_text)

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeJaarverslagOpenAI)

    result = await live._web_search_jaarverslag_wp("Testbedrijf", 2026)

    assert result.bron_type == "jaarverslag"
    assert result.bron_url == "https://example.test/jaarverslag.pdf"
    assert result.man == 60
    assert result.vrouw == 40
    assert result.voltijd == 80
    assert result.deeltijd == 20
    assert result.eigen_personeel == 70
    assert result.uitzend == 20
    assert result.detachering == 10
    assert result.wsw == 0
    assert result.pct_op_locatie == 0.9


@pytest.mark.asyncio
async def test_run_geeft_bron_url_door_als_pdf_gevonden_maar_geen_wp_geextraheerd(monkeypatch):
    async def fake_zoek_pdf(naam, jaar, website_url=None, uitgesloten=None):
        return "https://example.test/jaarverslag-2025.pdf"

    async def fake_run_with_pdf(self, naam, pdf_url):
        return None

    monkeypatch.setattr(live, "_zoek_jaarverslag_pdf", fake_zoek_pdf)
    monkeypatch.setattr(
        live,
        "_classificeer_jaarverslag_bron_identiteit",
        AsyncMock(return_value=live.IdentityClass.EXACT_ENTITY),
    )
    monkeypatch.setattr(live.LiveJaarverslagAgent, "run_with_pdf", fake_run_with_pdf)
    monkeypatch.setattr(live.settings, "jaarverslag_web_fallback", False)

    result = await live.LiveJaarverslagAgent().run("Testbedrijf", 2026)

    assert result is not None
    assert result.bron_url == "https://example.test/jaarverslag-2025.pdf"
    assert result.bron_type == "jaarverslag"
    assert result.wp_gevonden is None


@pytest.mark.asyncio
async def test_run_geeft_none_als_geen_pdf_gevonden(monkeypatch):
    async def fake_zoek_pdf(naam, jaar, website_url=None, uitgesloten=None):
        return None

    monkeypatch.setattr(live, "_zoek_jaarverslag_pdf", fake_zoek_pdf)
    monkeypatch.setattr(live.settings, "jaarverslag_web_fallback", False)

    result = await live.LiveJaarverslagAgent().run("Testbedrijf", 2026)

    assert result is None


@pytest.mark.asyncio
async def test_parse_json_met_herstel_parseert_geldige_json_direct():
    """Geldige JSON wordt meteen geparsed, zonder hersteloproep (geen extra kosten)."""
    client = _FakeOpenAI(api_key="test-key")

    resultaat = await live._parse_json_met_herstel(
        client, "gpt-test", '{"wp_gevonden": 100, "context": "ctx"}',
    )

    assert resultaat == {"wp_gevonden": 100, "context": "ctx"}
    assert client.responses.kwargs is None  # geen hersteloproep gedaan


@pytest.mark.asyncio
async def test_parse_json_met_herstel_valt_terug_op_hersteloproep(monkeypatch):
    """Bij ongeldige JSON wordt één goedkope hersteloproep gedaan (geen tools,
    wel json_object-mode) om het model de output te laten herformatteren."""
    class _HerstelResponse:
        output_text = '{"wp_gevonden": 42}'

    class _HerstelResponses(_FakeResponses):
        async def create(self, **kwargs):
            self.kwargs = kwargs
            return _HerstelResponse()

    class _HerstelOpenAI(_FakeOpenAI):
        def __init__(self, api_key):
            self.api_key = api_key
            self.responses = _HerstelResponses()

    client = _HerstelOpenAI(api_key="test-key")

    resultaat = await live._parse_json_met_herstel(
        client, "gpt-test", "Zeker, hier is het antwoord: {wp_gevonden: 42} (geen geldige json)",
    )

    assert resultaat == {"wp_gevonden": 42}
    assert client.responses.kwargs["text"]["format"]["type"] == "json_object"
    assert "tools" not in client.responses.kwargs


@pytest.mark.asyncio
async def test_parse_json_met_herstel_geeft_none_als_herstel_ook_faalt():
    """Faalt ook de hersteloproep, dan geeft de functie None terug in plaats
    van een exception te gooien — consistent met het bestaande 'niets gevonden'-gedrag."""
    class _NogSteedsFoutResponse:
        output_text = "nog steeds geen json"

    class _NogSteedsFoutResponses(_FakeResponses):
        async def create(self, **kwargs):
            return _NogSteedsFoutResponse()

    class _NogSteedsFoutOpenAI(_FakeOpenAI):
        def __init__(self, api_key):
            self.api_key = api_key
            self.responses = _NogSteedsFoutResponses()

    client = _NogSteedsFoutOpenAI(api_key="test-key")

    resultaat = await live._parse_json_met_herstel(client, "gpt-test", "helemaal geen json")

    assert resultaat is None


# --- determinisme en chain-of-thought in de classificatieprompts ---

@pytest.mark.asyncio
async def test_create_response_zet_temperatuur_op_de_configwaarde():
    """Zonder expliciete temperature draait elke call op de OpenAI-default 1.0;
    voor extractie en classificatie is dat onnodige niet-determinisme."""
    from app.providers import live

    gezien = {}

    class _Client:
        class responses:
            @staticmethod
            async def create(**kwargs):
                gezien.update(kwargs)
                return SimpleNamespace(output_text="{}", usage=None)

    await live._create_response(_Client(), model="gpt-4o-mini", input="x")

    assert gezien["temperature"] == live.settings.openai_temperature
    assert live.settings.openai_temperature == 0.0


@pytest.mark.asyncio
async def test_create_response_laat_expliciete_temperatuur_staan():
    from app.providers import live

    gezien = {}

    class _Client:
        class responses:
            @staticmethod
            async def create(**kwargs):
                gezien.update(kwargs)
                return SimpleNamespace(output_text="{}", usage=None)

    await live._create_response(_Client(), model="gpt-4o-mini", input="x", temperature=0.7)

    assert gezien["temperature"] == 0.7


def test_oordeelsprompts_vragen_eerst_om_redenering():
    """Chain-of-thought werkt alleen als het redeneerveld vóór de conclusie in
    de JSON staat — het model genereert op volgorde, dus daarna is het een
    rechtvaardiging achteraf in plaats van een afweging vooraf."""
    from app.providers.live import (EXTRACT_PROMPT, IDENTITY_EN_SCOPE_PROMPT,
                                    JAARVERSLAG_SCOPE_PROMPT, SCOPE_PROMPT)
    from app.research.source_reviewer import REVIEW_PROMPT

    for prompt in (EXTRACT_PROMPT, IDENTITY_EN_SCOPE_PROMPT,
                   JAARVERSLAG_SCOPE_PROMPT, SCOPE_PROMPT, REVIEW_PROMPT):
        assert '"redenering"' in prompt
        conclusie = min(
            prompt.index(veld) for veld in
            ('"identity_class"', '"scope_class"', '"document_scope"',
             '"wp_gevonden"', '"beslissing"')
            if veld in prompt
        )
        assert prompt.index('"redenering"') < conclusie


# --- stille degradatie van Serper zichtbaar maken ---

def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://google.serper.dev/search")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("fout", request=request, response=response)


class _FailingClient:
    def __init__(self, status):
        self._status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        raise _http_error(self._status)


@pytest.mark.asyncio
async def test_serper_zonder_quota_registreert_geen_kosten(monkeypatch):
    """De kosten werden vóór de request geregistreerd, dus een mislukte call
    telde mee als betaalde call. Daardoor bleef de kostenrapportage Serper-calls
    tonen die nooit gelukt zijn."""
    from app.research import usage

    monkeypatch.setattr(live.settings, "serper_api_key", "test-key")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _FailingClient(403))
    usage.start_usage_tracking()

    resultaten = await live._serper_search("Testbedrijf jaarverslag")

    assert resultaten == []
    assert "serper_search" not in usage.get_cost_summary()["providers"]


@pytest.mark.asyncio
async def test_serper_succes_registreert_wel_kosten(monkeypatch):
    from app.research import usage

    class _OkClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *args, **kwargs):
            return httpx.Response(
                200, json={"organic": [{"title": "T", "link": "https://x.test", "snippet": "s"}]},
                request=httpx.Request("POST", "https://google.serper.dev/search"),
            )

    monkeypatch.setattr(live.settings, "serper_api_key", "test-key")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _OkClient())
    usage.start_usage_tracking()

    resultaten = await live._serper_search("Testbedrijf")

    assert len(resultaten) == 1
    assert usage.get_cost_summary()["providers"]["serper_search"]["calls"] == 1


@pytest.mark.asyncio
async def test_serper_quotafout_wordt_gelogd_als_waarschuwing(monkeypatch, caplog):
    """Een uitgeputte quota geeft 403 en was niet te onderscheiden van 'niets
    gevonden'. Zonder signaal draait het systeem stilletjes door op een veel
    zwakkere zoekindex."""
    monkeypatch.setattr(live.settings, "serper_api_key", "test-key")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _FailingClient(403))

    with caplog.at_level("WARNING"):
        await live._serper_search("Testbedrijf")

    assert any("serper" in r.message.lower() for r in caplog.records)
    assert any("403" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_serper_places_quotafout_wordt_ook_gelogd(monkeypatch, caplog):
    monkeypatch.setattr(live.settings, "serper_api_key", "test-key")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _FailingClient(429))

    with caplog.at_level("WARNING"):
        resultaat = await live._serper_places("Testbedrijf Weert")

    assert resultaat is None
    assert any("serper" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_serper_zonder_tegoed_geeft_400_en_wordt_herkend(monkeypatch, caplog):
    """Serper meldt een leeg tegoed met HTTP 400 en de body
    {"message":"Not enough credits"} — niet met 401/402/403. Een guard op
    statuscodes alleen mist daardoor precies het scenario waarvoor hij bedoeld is."""
    class _GeenTegoed:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *args, **kwargs):
            request = httpx.Request("POST", "https://google.serper.dev/search")
            return httpx.Response(
                400, json={"message": "Not enough credits", "statusCode": 400},
                request=request,
            )

    monkeypatch.setattr(live.settings, "serper_api_key", "test-key")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _GeenTegoed())

    with caplog.at_level("WARNING"):
        resultaten = await live._serper_search("Testbedrijf jaarverslag")

    assert resultaten == []
    meldingen = " ".join(r.message.lower() for r in caplog.records)
    assert "serper" in meldingen
    assert "tegoed" in meldingen or "credit" in meldingen


# --- verslagjaar bepalen: uploadpad is geen verslagjaar ---

def test_verslagjaar_negeert_uploadpad_bij_afwijzen():
    """servatius.nl/media/2026/jaarverslag.pdf werd afgewezen omdat het enige
    jaar in de tekst het uploadjaar 2026 was. Het pad zegt niets over het
    verslagjaar; zonder jaar in titel of bestandsnaam mag het niet vetoën."""
    tekst = "Jaarverslag https://www.servatius.nl/media/2026/jaarverslag.pdf"
    assert live._lijkt_jaarverslag(tekst, 2025)


def test_verslagjaar_accepteert_geen_verouderd_verslag_via_uploadpad():
    """Andersom net zo fout: 'Jaarverslag 2017' met /uploads/2024/01/ in de URL
    werd als verslagjaar 2024 geaccepteerd. Titel en bestandsnaam zijn leidend."""
    tekst = ("Jaarverslag 2017 "
             "https://heemwonen.nl/wp-content/uploads/2024/01/jaarverslag-hm-2017.pdf")
    assert not live._lijkt_jaarverslag(tekst, 2024)


def test_verslagjaar_uit_bestandsnaam_blijft_leidend():
    tekst = ("JAARVERANTWOORDING 2022 "
             "https://www.zorgboog.nl/wp-content/uploads/2025/11/Jaarverantwoording-2022.pdf")
    assert not live._lijkt_jaarverslag(tekst, 2025)
    assert live._lijkt_jaarverslag(tekst, 2022)


def test_verslagjaar_in_bestandsnaam_wordt_wel_gebruikt():
    tekst = "Jaarverslag https://example.nl/uploads/2026/03/jaarverslag-2025.pdf"
    assert live._lijkt_jaarverslag(tekst, 2025)
    assert not live._lijkt_jaarverslag(tekst, 2023)


# --- zoekopdracht mag niet verwateren ---

@pytest.mark.asyncio
async def test_jaarverslagquery_is_beknopt_en_bevat_de_naam(monkeypatch):
    """Gemeten op 10 organisaties die aantoonbaar publiceren: de oude query
    ('"naam" jaarverslag bestuursverslag annual report pdf 2025 2024 2023')
    vond er 2, een beknopte query ('naam jaarverslag pdf') vond er 8. De
    opsomming van synoniemen en jaartallen verwatert de zoekopdracht zo dat de
    index vooral op 'jaarverslag pdf' matcht in plaats van op de organisatie."""
    queries = []

    async def vang(query, max_results=5):
        queries.append(query)
        return []

    monkeypatch.setattr(live, "_web_search", vang)
    monkeypatch.setattr(live, "_openai_web_search", AsyncMock(return_value=[]))

    await live._zoek_jaarverslag_pdf("Stichting Pergamijn", 2026, website_url=None)

    # De eerste zoekopdracht is de bepalende; daarna volgt hooguit nog de
    # jaarstukken-ronde voor overheden.
    q = queries[0]
    assert "Stichting Pergamijn" in q
    assert '"' not in q
    for verwaterend in ("bestuursverslag", "annual report", "2025", "2024", "2023"):
        assert verwaterend not in q, f"{verwaterend!r} verwatert de zoekopdracht"


@pytest.mark.asyncio
async def test_site_scoped_query_blijft_ook_beknopt(monkeypatch):
    queries = []

    async def vang(query, max_results=5):
        queries.append(query)
        return []

    monkeypatch.setattr(live, "_web_search", vang)
    monkeypatch.setattr(live, "_openai_web_search", AsyncMock(return_value=[]))

    await live._zoek_jaarverslag_pdf("Servatius", 2026, website_url="https://www.servatius.nl/")

    assert queries[0].startswith("site:servatius.nl")
    for verwaterend in ("bestuursverslag", "jaarverantwoording", "2025", "2024"):
        assert verwaterend not in queries[0]


# --- domein voor site:-scoping ---

def test_domein_valt_terug_op_hoofddomein_bij_subdomein():
    """Een jaarverslag staat op de hoofdsite, niet op de helpdesk of de
    vacaturesite. site:support.hollandcasino.nl levert per definitie niets op."""
    assert live._domein_van_url("https://support.hollandcasino.nl/hc/nl/artikel") == "hollandcasino.nl"
    assert live._domein_van_url("https://werkenbij.arriva.nl/vacatures") == "arriva.nl"
    assert live._domein_van_url("https://shop.mitsubishi-motors.nl/") == "mitsubishi-motors.nl"
    assert live._domein_van_url("https://nu.venlo.nl/nieuws") == "venlo.nl"


def test_domein_blijft_ongemoeid_zonder_subdomein():
    assert live._domein_van_url("https://www.servatius.nl/") == "servatius.nl"
    assert live._domein_van_url("https://ou.nl/onderwijs") == "ou.nl"
    assert live._domein_van_url("https://www.sif-group.com/nl") == "sif-group.com"


def test_gidsdomein_geeft_geen_domein_voor_site_scoping():
    """allebiz.nl, companyinfo.nl en eur-lex stonden als 'website' van
    organisaties in de watchlist. site:-scoping daarop is gegarandeerd zinloos;
    beter meteen de open zoekopdracht, die 8/10 scoort."""
    for gids in ("https://www.allebiz.nl/team-verkeer-politie-limburg",
                 "https://companyinfo.nl/bedrijf/okechamp",
                 "https://www.zorgkiezer.nl/zorginstelling/x",
                 "https://eur-lex.europa.eu/legal-content/NL/TXT/",
                 "https://www.belastingadviseur-info.nl/newtone"):
        assert live._domein_van_url(gids) is None, gids


# --- documenttypen van overheden ---

def test_jaarstukken_telt_als_jaarverslag():
    """Gemeenten en provincies publiceren geen 'jaarverslag' maar jaarstukken en
    een programmarekening. Die stonden niet in de markers, dus werd de correcte
    'Jaarstukken 2024' van Gemeente Maastricht afgewezen."""
    assert live._lijkt_jaarverslag("Jaarstukken 2024 Gemeente Maastricht", 2024)
    assert live._lijkt_jaarverslag("Programmarekening 2024", 2024)
    assert live._lijkt_jaarverslag("Programmaverantwoording 2024", 2024)


def test_vth_jaarverslag_blijft_geweerd_ongeacht_schrijfwijze():
    """De blocklist kende 'jaarverslag-vth' maar niet 'VTH-jaarverslag', waardoor
    een deelrapport over vergunningen als jaarverslag van de gemeente doorging."""
    for schrijfwijze in ("VTH-jaarverslag 2024", "jaarverslag VTH 2024",
                         "VTH jaarverslag 2024", "jaarverslag_vth 2024"):
        assert not live._lijkt_jaarverslag(schrijfwijze, 2024), schrijfwijze


@pytest.mark.asyncio
async def test_tweede_poging_met_jaarstukken_alleen_als_eerste_niets_geeft(monkeypatch):
    """Gemeenten zijn met 'jaarverslag' niet te vinden. Een tweede zoekopdracht
    op 'jaarstukken' kost 0,1 ct en wordt alleen gedaan als de eerste faalt."""
    queries = []

    async def vang(query, max_results=5):
        queries.append(query)
        if "jaarstukken" in query:
            return [{"title": "Jaarstukken 2025", "url": "https://maastricht.nl/jaarstukken-2025.pdf"}]
        return []

    monkeypatch.setattr(live, "_web_search", vang)
    monkeypatch.setattr(live, "_openai_web_search", AsyncMock(return_value=[]))

    result = await live._zoek_jaarverslag_pdf("Gemeente Maastricht", 2026, website_url=None)

    assert result == "https://maastricht.nl/jaarstukken-2025.pdf"
    assert any("jaarstukken" in q for q in queries)


@pytest.mark.asyncio
async def test_geen_tweede_poging_als_eerste_al_raak_is(monkeypatch):
    queries = []

    async def vang(query, max_results=5):
        queries.append(query)
        return [{"title": "Jaarverslag 2025", "url": "https://x.test/jaarverslag-2025.pdf"}]

    monkeypatch.setattr(live, "_web_search", vang)
    monkeypatch.setattr(live, "_openai_web_search", AsyncMock(return_value=[]))

    await live._zoek_jaarverslag_pdf("Bedrijf", 2026, website_url=None)

    assert not any("jaarstukken" in q for q in queries)


@pytest.mark.asyncio
async def test_wp_zoekopdrachten_stapelen_geen_synoniemen(monkeypatch):
    """Zelfde patroon als de jaarverslagquery die van 2/10 naar 8/10 ging:
    'medewerkers werknemers personeel headcount' achter elkaar laat de index op
    de trefwoorden matchen in plaats van op de organisatie."""
    queries = []

    async def vang(query, max_results=5):
        queries.append(query)
        return []

    monkeypatch.setattr(live, "_web_search", vang)
    monkeypatch.setattr(live, "_openai_web_search", AsyncMock(return_value=[]))
    monkeypatch.setattr(live.settings, "extra_bronnen_aantal", 2)

    await live._web_search_wp("Testbedrijf", "Weert")
    await live._web_search_jaarverslag_wp("Testbedrijf", 2025)
    await live.verzamel_extra_media_bronnen("Testbedrijf", "Weert", set())

    assert queries, "geen zoekopdrachten uitgevoerd"
    synoniemen = {"medewerkers", "werknemers", "personeel", "headcount",
                  "jaarverslag", "bestuursverslag"}
    for q in queries:
        overlap = set(q.lower().split()) & synoniemen
        assert len(overlap) <= 2, f"{q!r} stapelt {sorted(overlap)}"
        assert "Testbedrijf" in q
