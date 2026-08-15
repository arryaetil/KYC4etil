"""Leesweergave van webbronnen: markering van het bewijsfragment en escaping."""
from app.research.bewijspagina import render_bewijspagina


def test_markeert_het_bewijsfragment():
    html = render_bewijspagina(
        url="https://example.nl/team",
        titel="Ons team",
        tekst="Welkom.\nAl 40 jaar staan onze 10 specialisten voor u klaar.\nContact.",
        citaat="Al 40 jaar staan onze 10 specialisten voor u klaar.",
    )
    assert '<mark id="citaat">Al 40 jaar staan onze 10 specialisten voor u klaar.</mark>' in html


def test_markeert_ook_bij_afwijkende_witruimte_in_het_citaat():
    html = render_bewijspagina(
        url="https://example.nl/team",
        titel="Ons team",
        tekst="Ons team bestaat uit 3 podotherapeuten.",
        citaat="Ons team   bestaat\nuit 3 podotherapeuten.",
    )
    assert '<mark id="citaat">' in html


def test_escapet_html_uit_de_brontekst_tegen_xss():
    html = render_bewijspagina(
        url="https://kwaadwillend.nl/",
        titel="<script>alert(1)</script>",
        tekst="<script>alert(document.cookie)</script>",
        citaat=None,
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_geen_citaat_gevonden_toont_toelichting_maar_faalt_niet():
    html = render_bewijspagina(
        url="https://example.nl/team",
        titel="Ons team",
        tekst="De pagina is intussen gewijzigd.",
        citaat="Deze zin staat niet meer op de pagina.",
    )
    assert "niet letterlijk teruggevonden" in html
    assert "De pagina is intussen gewijzigd." in html


def test_lege_tekst_toont_nette_toelichting():
    html = render_bewijspagina(
        url="https://example.nl/leeg", titel="Leeg", tekst="", citaat=None,
    )
    assert "geen leesbare" in html


def test_bevat_altijd_een_link_naar_het_origineel():
    html = render_bewijspagina(
        url="https://example.nl/pagina", titel="Iets", tekst="Tekst.", citaat=None,
    )
    assert 'href="https://example.nl/pagina"' in html
    assert 'target="_blank"' in html
