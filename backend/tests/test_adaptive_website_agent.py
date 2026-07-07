"""Tests voor de adaptieve tool-use-loop van LiveWebsiteAgent."""
import json

import pytest

from app.providers import live


class _FakeHtmlResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        pass


class _FakeHtmlClient:
    def __init__(self, html: str):
        self._html = html

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, *args, **kwargs):
        return _FakeHtmlResponse(self._html)


HTML_MET_LINKS = """
<html><body>
<nav><a href="/negeer-dit">Navigatie</a></nav>
<p>Ons team bestaat uit 12 medewerkers.</p>
<a href="/over-ons/specialisten">Onze specialisten</a>
<a href="https://ander-domein.test/pagina">Extern</a>
<a href="/over-ons/specialisten">Onze specialisten</a>
<footer><a href="/negeer-ook-dit">Footer</a></footer>
</body></html>
"""


@pytest.mark.asyncio
async def test_haal_pagina_op_geeft_tekst_en_links(monkeypatch):
    monkeypatch.setattr(live.httpx, "AsyncClient", _FakeHtmlClient(HTML_MET_LINKS))

    resultaat = await live._haal_pagina_op("https://voorbeeld.test/over-ons")

    assert "12 medewerkers" in resultaat["tekst"]
    # nav/footer-links worden weggefilterd door dezelfde opschoning als _fetch_text
    urls = [link["url"] for link in resultaat["links"]]
    assert "https://voorbeeld.test/over-ons/specialisten" in urls
    assert "https://ander-domein.test/pagina" not in urls  # ander domein, genegeerd
    assert "https://voorbeeld.test/negeer-dit" not in urls  # nav, genegeerd
    assert "https://voorbeeld.test/negeer-ook-dit" not in urls  # footer, genegeerd
    # geen duplicaten
    assert urls.count("https://voorbeeld.test/over-ons/specialisten") == 1


class _FakeToolCall:
    def __init__(self, name: str, arguments: dict, call_id: str = "call_1"):
        self.type = "function_call"
        self.name = name
        self.arguments = json.dumps(arguments)
        self.call_id = call_id


class _FakeToolResponse:
    def __init__(self, output: list, response_id: str = "resp_1"):
        self.output = output
        self.id = response_id


class _FakeToolResponses:
    def __init__(self, antwoorden: list):
        self._antwoorden = antwoorden
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._antwoorden[len(self.calls) - 1]


class _FakeToolOpenAI:
    laatste_responses = None

    def __init__(self, api_key):
        self.api_key = api_key


def _maak_fake_openai(antwoorden):
    responses = _FakeToolResponses(antwoorden)

    class _Client(_FakeToolOpenAI):
        def __init__(self, api_key):
            super().__init__(api_key)
            self.responses = responses
            _FakeToolOpenAI.laatste_responses = responses

    return _Client


@pytest.mark.asyncio
async def test_tool_use_loop_bezoekt_pagina_en_meldt_resultaat(monkeypatch):
    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "openai_model", "gpt-test")
    monkeypatch.setattr(live.settings, "max_website_pages", 3)

    async def fake_haal_pagina_op(url):
        return {"tekst": "Ons team bestaat uit 12 medewerkers.", "links": []}

    monkeypatch.setattr(live, "_haal_pagina_op", fake_haal_pagina_op)

    eerste_antwoord = _FakeToolResponse(
        output=[_FakeToolCall("bezoek_pagina", {"url": "https://voorbeeld.test/over-ons"}, "call_1")],
        response_id="resp_1",
    )
    tweede_antwoord = _FakeToolResponse(
        output=[_FakeToolCall("meld_resultaat", {
            "wp_gevonden": 12, "context": "Ons team bestaat uit 12 medewerkers.",
            "zekerheid": "hoog", "reden": "letterlijk vermeld",
            "is_totaal_meerdere_vestigingen": False, "is_limburg_specifiek": True,
            "is_fte": False, "peilmoment": None,
        }, "call_2")],
        response_id="resp_2",
    )

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", _maak_fake_openai([eerste_antwoord, tweede_antwoord]))

    resultaat = await live._tool_use_loop("Testbedrijf", "Markt 1", "https://voorbeeld.test")

    assert resultaat["wp_gevonden"] == 12
    assert resultaat["zekerheid"] == "hoog"
    # Twee aanroepen: eerste zonder previous_response_id, tweede mét (vervolg op resp_1)
    calls = _FakeToolOpenAI.laatste_responses.calls
    assert len(calls) == 2
    assert "previous_response_id" not in calls[0]
    assert calls[1]["previous_response_id"] == "resp_1"
    assert calls[1]["input"][0]["type"] == "function_call_output"
    assert calls[1]["input"][0]["call_id"] == "call_1"


@pytest.mark.asyncio
async def test_tool_use_loop_stopt_bij_budget_op(monkeypatch):
    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(live.settings, "openai_model", "gpt-test")
    monkeypatch.setattr(live.settings, "max_website_pages", 2)

    async def fake_haal_pagina_op(url):
        return {"tekst": "Geen relevante informatie.", "links": []}

    monkeypatch.setattr(live, "_haal_pagina_op", fake_haal_pagina_op)

    # Het model blijft steeds een nieuwe pagina willen bezoeken, meldt nooit een resultaat
    antwoorden = [
        _FakeToolResponse(output=[_FakeToolCall("bezoek_pagina", {"url": f"https://voorbeeld.test/{i}"}, f"call_{i}")],
                          response_id=f"resp_{i}")
        for i in range(5)
    ]

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", _maak_fake_openai(antwoorden))

    resultaat = await live._tool_use_loop("Testbedrijf", "Markt 1", "https://voorbeeld.test")

    assert resultaat is None


@pytest.mark.asyncio
async def test_website_agent_gebruikt_tool_use_loop(monkeypatch):
    async def fake_tool_use_loop(naam, adres, start_url):
        assert start_url == "https://voorbeeld.test"
        return {
            "wp_gevonden": 25, "context": "25 medewerkers", "zekerheid": "hoog",
            "reden": "letterlijk vermeld", "is_totaal_meerdere_vestigingen": False,
            "is_limburg_specifiek": True, "is_fte": False, "peilmoment": "2026",
        }

    monkeypatch.setattr(live, "_tool_use_loop", fake_tool_use_loop)

    agent = live.LiveWebsiteAgent()
    finding = await agent.run("Testbedrijf", "Markt 1", "https://voorbeeld.test", gemeente="Maastricht")

    assert finding is not None
    assert finding.wp_gevonden == 25
    assert finding.bron_url == "https://voorbeeld.test"
    assert finding.bron_type == "website"


@pytest.mark.asyncio
async def test_website_agent_valt_terug_op_web_search_zonder_resultaat(monkeypatch):
    async def fake_tool_use_loop(naam, adres, start_url):
        return None

    async def fake_web_search_wp(naam, gemeente):
        return live.AgentFinding(
            wp_gevonden=8, context="nieuwsbericht", zekerheid="laag", reden="fallback",
            bron_url="https://nieuws.test/artikel", bron_type="media",
        )

    monkeypatch.setattr(live, "_tool_use_loop", fake_tool_use_loop)
    monkeypatch.setattr(live, "_web_search_wp", fake_web_search_wp)

    agent = live.LiveWebsiteAgent()
    finding = await agent.run("Testbedrijf", "Markt 1", "https://voorbeeld.test", gemeente="Maastricht")

    assert finding is not None
    assert finding.wp_gevonden == 8
    assert finding.bron_type == "media"
