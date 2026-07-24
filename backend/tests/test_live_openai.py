import pytest
import httpx

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
            return [{"title": "Jaarverantwoording", "url": "https://mondriaan.eu/jaarverantwoording-2026.pdf",
                      "snippet": "", "bron": "serper"}]
        return [{"title": "Kwaliteitsverslag (fout document)", "url": "https://mondriaan.eu/kwaliteitsverslag.pdf",
                  "snippet": "", "bron": "serper"}]

    monkeypatch.setattr(live, "_web_search", fake_web_search)

    resultaat = await live._zoek_jaarverslag_pdf_voor_jaar(
        "Mondriaan", 2026, website_url="https://www.mondriaan.eu/",
    )

    assert resultaat == "https://mondriaan.eu/jaarverantwoording-2026.pdf"
    assert gedane_queries[0].startswith("site:mondriaan.eu")


@pytest.mark.asyncio
async def test_zoek_jaarverslag_pdf_valt_terug_op_open_zoekopdracht_zonder_domein_resultaat(monkeypatch):
    async def fake_web_search(query, max_results=8):
        if query.startswith("site:"):
            return []
        return [{"title": "Jaarverslag", "url": "https://example.test/jaarverslag.pdf",
                  "snippet": "", "bron": "serper"}]

    monkeypatch.setattr(live, "_web_search", fake_web_search)

    resultaat = await live._zoek_jaarverslag_pdf_voor_jaar(
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

    await live._zoek_jaarverslag_pdf_voor_jaar("Testbedrijf", 2026, website_url=None)

    assert len(gedane_queries) == 1
    assert not gedane_queries[0].startswith("site:")


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
