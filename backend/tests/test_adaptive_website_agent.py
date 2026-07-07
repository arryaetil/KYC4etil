"""Tests voor de adaptieve tool-use-loop van LiveWebsiteAgent."""
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
