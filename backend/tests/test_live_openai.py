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
async def test_openai_web_search_contact_fallback(monkeypatch):
    class ContactResponse:
        output_text = '{"website_url": "https://example.test", "telefoonnummer": "043-1234567", "adres": "Markt 1", "reden": "gevonden"}'

    class ContactResponses(_FakeResponses):
        async def create(self, **kwargs):
            self.kwargs = kwargs
            return ContactResponse()

    class ContactOpenAI(_FakeOpenAI):
        def __init__(self, api_key):
            self.api_key = api_key
            self.responses = ContactResponses()
            ContactOpenAI.last_responses = self.responses

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "openai_model", "gpt-test")

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", ContactOpenAI)

    result = await live._web_search_contact("Testbedrijf", "Maastricht")

    assert result.website == "https://example.test"
    assert result.phone == "043-1234567"
    assert ContactOpenAI.last_responses.kwargs["tools"][0]["type"] == "web_search"
    assert "text" not in ContactOpenAI.last_responses.kwargs


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
async def test_web_search_jaarverslag_wp_geeft_uitsplitsing_door(monkeypatch):
    class _FakeJaarverslagResponse:
        output_text = (
            '{"wp_gevonden": 100, "context": "ctx", "zekerheid": "hoog", "reden": "t", '
            '"is_limburg_specifiek": true, "is_fte": false, "peilmoment": "2026", '
            '"bron_url": "https://example.test/jaarverslag.pdf", '
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

    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "openai_model", "gpt-test")

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeJaarverslagOpenAI)

    result = await live._web_search_jaarverslag_wp("Testbedrijf", 2026)

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
    async def fake_zoek_pdf(naam, jaar):
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
    async def fake_zoek_pdf(naam, jaar):
        return None

    monkeypatch.setattr(live, "_zoek_jaarverslag_pdf", fake_zoek_pdf)
    monkeypatch.setattr(live.settings, "jaarverslag_web_fallback", False)

    result = await live.LiveJaarverslagAgent().run("Testbedrijf", 2026)

    assert result is None
