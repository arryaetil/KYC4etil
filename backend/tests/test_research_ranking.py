"""Bronvalidatie en ranking blijven deterministisch en uitlegbaar."""
from datetime import date

from app.research.ranking import rank_bronnen
from app.research.validation import SourceDocument, valideer_bron


def test_verkeerde_entiteit_wordt_hard_afgewezen():
    document = SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url="https://anderbedrijf.nl/jaarverslag-2025.pdf",
        titel="Jaarverslag 2025 Ander Bedrijf",
        tekst="Ander Bedrijf had in 2025 900 medewerkers.",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        wp_gevonden=900,
        eenheid="werkzame_personen",
    )

    validatie = valideer_bron(document)

    assert validatie.is_afgewezen is True
    assert validatie.identity_class == "mismatch"
    assert "verkeerde organisatie" in validatie.afwijsredenen


def test_verslagjaar_en_publicatiedatum_worden_apart_gevalideerd():
    document = SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
        titel="Jaarverslag 2025",
        tekst="Voorbeeld Zorg telde in verslagjaar 2025 500 medewerkers.",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        publicatiedatum=date(2026, 5, 1),
        wp_gevonden=500,
        eenheid="werkzame_personen",
    )

    validatie = valideer_bron(document)

    assert validatie.is_afgewezen is False
    assert validatie.validaties["verslagjaar_match"] is True
    assert validatie.validaties["publicatie_in_n_plus_1"] is True


def test_ranking_kiest_officieel_bewijs_en_houdt_recente_media_zichtbaar():
    officieel = valideer_bron(SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
        titel="Jaarverslag 2025",
        tekst="Voorbeeld Zorg telde in 2025 500 medewerkers.",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        publicatiedatum=date(2026, 4, 1),
        informatie_peilmoment="2025-12",
        wp_gevonden=500,
        eenheid="werkzame_personen",
        bewijsfragment="Voorbeeld Zorg telde in 2025 500 medewerkers.",
    ))
    media = valideer_bron(SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url="https://limburgnieuws.nl/voorbeeld-zorg-reorganisatie",
        titel="Voorbeeld Zorg reorganiseert",
        tekst="Voorbeeld Zorg heeft na de reorganisatie ongeveer 470 medewerkers.",
        brontype="media",
        documenttype="nieuwsartikel",
        publicatiedatum=date(2026, 7, 1),
        informatie_peilmoment="2026-07",
        wp_gevonden=470,
        eenheid="werkzame_personen",
        bewijsfragment="Na de reorganisatie ongeveer 470 medewerkers.",
    ))

    ranked = rank_bronnen([media, officieel], referentiedatum=date(2026, 7, 24))

    assert [bron.document.url for bron in ranked] == [
        "https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
        "https://limburgnieuws.nl/voorbeeld-zorg-reorganisatie",
    ]
    assert ranked[0].score_breakdown["autoriteit"] > ranked[1].score_breakdown["autoriteit"]
    assert "recent_actualiteitssignaal" in ranked[1].waarschuwingen


def test_fte_bron_krijgt_waarschuwing_en_geen_wp_bewijsscore():
    fte = valideer_bron(SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
        titel="Jaarverslag 2025",
        tekst="Voorbeeld Zorg had gemiddeld 430 fte.",
        brontype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        wp_gevonden=430,
        eenheid="fte",
        bewijsfragment="Voorbeeld Zorg had gemiddeld 430 fte.",
    ))

    ranked = rank_bronnen([fte], referentiedatum=date(2026, 7, 24))

    assert "fte_geen_wp" in ranked[0].waarschuwingen
    assert ranked[0].score_breakdown["bewijs"] == 0.0
