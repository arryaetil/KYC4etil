"""Een jaarverslag dat als website is gepubliceerd, moet ook gevonden worden."""
import pytest

from app.providers import fetch, jaarverslag, jaarverslag_zoeken


def _resultaat(titel: str, url: str) -> dict:
    return {"title": titel, "url": url, "snippet": ""}


@pytest.mark.asyncio
async def test_pdf_wint_van_een_webversie(monkeypatch):
    """Een PDF heeft vaste opmaak en paginanummers voor het bewijs.

    Daarom twee volledige rondes en niet één gecombineerde: een HTML-treffer van
    een nieuwer jaar mag een beschikbare PDF niet verdringen.
    """
    async def fake_fetch_text(url):
        return "jaarverslag 2024 " + ("medewerkers in dienst. " * 500)

    monkeypatch.setattr(fetch, "_fetch_text", fake_fetch_text)
    resultaten = [
        _resultaat("Jaarverslag 2024", "https://voorbeeld.nl/jaarverslag-2024"),
        _resultaat("Jaarverslag 2024 (pdf)", "https://voorbeeld.nl/jv-2024.pdf"),
    ]

    gevonden = await jaarverslag_zoeken._eerste_pdf_uit_resultaten(resultaten, 2024)
    assert gevonden == "https://voorbeeld.nl/jv-2024.pdf"


@pytest.mark.asyncio
async def test_webversie_wordt_gevonden_als_er_geen_pdf_is(monkeypatch):
    """Dit was het gat: zonder PDF-link op de pagina viel de bron helemaal weg."""
    async def fake_fetch_text(url):
        return "Jaarverslag 2024 van Voorbeeld. " + ("Onze medewerkers. " * 500)

    monkeypatch.setattr(fetch, "_fetch_text", fake_fetch_text)
    resultaten = [_resultaat("Jaarverslag 2024", "https://voorbeeld.nl/jaarverslag-2024")]

    assert await jaarverslag_zoeken._eerste_pdf_uit_resultaten(resultaten, 2024) is None
    gevonden = await jaarverslag_zoeken._eerste_html_uit_resultaten(resultaten, 2024)
    assert gevonden == "https://voorbeeld.nl/jaarverslag-2024"


@pytest.mark.asyncio
async def test_overzichtspagina_telt_niet_als_jaarverslag(monkeypatch):
    """Een pagina met links naar 2019 t/m 2024 is een index, geen verslag.

    Zulke pagina's zijn kort en bestaan vooral uit links; een verslag heeft
    lopende tekst. Die ondergrens scheidt de twee zonder model.
    """
    async def fake_fetch_text(url):
        return "Jaarverslagen 2019 2020 2021 2022 2023 2024 Download hier."

    monkeypatch.setattr(fetch, "_fetch_text", fake_fetch_text)
    resultaten = [_resultaat("Jaarverslagen", "https://voorbeeld.nl/jaarverslagen")]

    assert await jaarverslag_zoeken._eerste_html_uit_resultaten(resultaten, 2024) is None


@pytest.mark.asyncio
async def test_pagina_zonder_het_verslagjaar_telt_niet(monkeypatch):
    """Voorkomt dat een "over ons"-pagina die het woord jaarverslag noemt
    als bron wordt aangemerkt."""
    async def fake_fetch_text(url):
        return "Over ons. " + ("Wij hebben medewerkers. " * 500)

    monkeypatch.setattr(fetch, "_fetch_text", fake_fetch_text)
    resultaten = [_resultaat("Jaarverslag", "https://voorbeeld.nl/jaarverslag")]

    assert await jaarverslag_zoeken._eerste_html_uit_resultaten(resultaten, 2024) is None


@pytest.mark.asyncio
async def test_wp_extractie_leest_ook_een_webversie(monkeypatch):
    """`fitz.open` op HTML levert niets op, dus dit gaf altijd None terug."""
    async def fake_fetch_text(url):
        return "In 2024 waren er 412 medewerkers in dienst bij Voorbeeld."

    monkeypatch.setattr(fetch, "_fetch_text", fake_fetch_text)

    paginas = await jaarverslag._relevante_bronpaginas("https://voorbeeld.nl/jaarverslag-2024")

    assert len(paginas) == 1
    # Een webversie kent geen paginanummering; dat veld blijft leeg.
    assert paginas[0][0] is None
    assert "412 medewerkers" in paginas[0][1]


@pytest.mark.asyncio
async def test_webpagina_zonder_personeelswoorden_levert_niets(monkeypatch):
    async def fake_fetch_text(url):
        return "Onze producten en diensten voor de agrarische sector."

    monkeypatch.setattr(fetch, "_fetch_text", fake_fetch_text)

    assert await jaarverslag._relevante_bronpaginas("https://voorbeeld.nl/jv") == []
