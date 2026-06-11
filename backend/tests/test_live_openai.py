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
