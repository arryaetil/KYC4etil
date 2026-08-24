"""Een aangeleverde website-URL is niet vanzelf nog geldig."""
import httpx
import pytest

from app.providers import website_check
from app.providers.website_check import controleer_website


# De echte klasse vasthouden vóór het patchen: binnen de vervanger verwijst
# httpx.AsyncClient naar de vervanger zelf.
_ECHTE_CLIENT = httpx.AsyncClient


def _client(handler):
    """Vervang de HTTP-laag door een transport dat het scenario naspeelt."""
    class _Client:
        def __init__(self, *args, **kwargs):
            self._echt = _ECHTE_CLIENT(
                transport=httpx.MockTransport(handler),
                follow_redirects=kwargs.get("follow_redirects", False),
            )

        async def __aenter__(self):
            return self._echt

        async def __aexit__(self, *exc):
            await self._echt.aclose()

    return _Client


@pytest.mark.asyncio
async def test_bereikbare_site_blijft_ongewijzigd(monkeypatch):
    def handler(request):
        return httpx.Response(200, text="<html>Welkom</html>")

    monkeypatch.setattr(website_check.httpx, "AsyncClient", _client(handler))
    uitkomst = await controleer_website("https://voorbeeld.nl/")

    assert uitkomst.bruikbaar is True
    assert uitkomst.reden == "bereikbaar"


@pytest.mark.asyncio
async def test_verhuizing_naar_ander_domein_levert_het_nieuwe_adres(monkeypatch):
    """Na een fusie of naamswijziging is de doorverwijzing het juiste adres."""
    def handler(request):
        if request.url.host == "oudnaam.nl":
            return httpx.Response(
                301, headers={"Location": "https://nieuwnaam.nl/"},
            )
        return httpx.Response(200, text="<html>Nieuw</html>")

    monkeypatch.setattr(website_check.httpx, "AsyncClient", _client(handler))
    uitkomst = await controleer_website("https://oudnaam.nl/")

    assert uitkomst.bruikbaar is True
    assert uitkomst.url == "https://nieuwnaam.nl/"
    assert uitkomst.reden == "verhuisd"


@pytest.mark.asyncio
async def test_http_naar_https_telt_niet_als_verhuizing(monkeypatch):
    def handler(request):
        if request.url.scheme == "http":
            return httpx.Response(
                301, headers={"Location": "https://voorbeeld.nl/"},
            )
        return httpx.Response(200, text="<html>ok</html>")

    monkeypatch.setattr(website_check.httpx, "AsyncClient", _client(handler))
    uitkomst = await controleer_website("http://www.voorbeeld.nl/")

    assert uitkomst.reden == "bereikbaar"


@pytest.mark.asyncio
async def test_verlopen_domein_is_niet_bruikbaar(monkeypatch):
    """Zonder deze controle onderzocht de agent een dood adres.

    Dat leverde "niets gevonden" op, wat iets heel anders betekent dan "deze
    organisatie is niet online te vinden".
    """
    def handler(request):
        raise httpx.ConnectError("naam niet op te lossen")

    monkeypatch.setattr(website_check.httpx, "AsyncClient", _client(handler))
    uitkomst = await controleer_website("https://bestaatniet.invalid/")

    assert uitkomst.bruikbaar is False
    assert uitkomst.url is None
    assert uitkomst.reden.startswith("onbereikbaar:")


@pytest.mark.asyncio
async def test_foutstatus_is_niet_bruikbaar(monkeypatch):
    def handler(request):
        return httpx.Response(404, text="weg")

    monkeypatch.setattr(website_check.httpx, "AsyncClient", _client(handler))
    uitkomst = await controleer_website("https://voorbeeld.nl/oud")

    assert uitkomst.bruikbaar is False
    assert uitkomst.reden == "status:404"


@pytest.mark.asyncio
async def test_zonder_url_geen_controle():
    uitkomst = await controleer_website(None)
    assert uitkomst.bruikbaar is False
    assert uitkomst.reden == "geen_url"
