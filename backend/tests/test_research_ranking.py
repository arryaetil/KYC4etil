"""Bronvalidatie en ranking blijven deterministisch en uitlegbaar."""
from datetime import date

from app.research.ranking import (
    behoud_vestigingsanker, rank_bronnen, selecteer_bronportfolio,
)
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


def test_uit_naamlijst_afgeleid_wp_getal_krijgt_waarschuwing():
    """
    Regressie: Dreessen Advocaten noemt in gewone HTML vier advocaten en één
    ondersteunende medewerker bij naam, zonder los personeelsgetal. Zo'n
    afgeleide telling is bruikbaar bewijs, maar moet zichtbaar anders zijn dan
    een letterlijk genoemd getal (zie EXTRACT_PROMPT).
    """
    document = SourceDocument(
        naam="Dreessen Advocaten",
        company_website_url="https://dreessenadvocaten.nl",
        url="https://dreessenadvocaten.nl/advocaten",
        titel="Onze advocaten",
        tekst="Vier advocaten en één ondersteunend medewerker.",
        brontype="officiele_website",
        wp_gevonden=5,
        eenheid="werkzame_personen",
        bewijsfragment="Vier advocaten en één ondersteunend medewerker.",
        raw_data={
            "wp_afgeleid_uit_naamlijst": True,
            "genoemde_namen": ["Jan Dreessen (advocaat)", "Marie de Vries (advocaat)"],
        },
    )

    validatie = valideer_bron(document)

    assert "wp_afgeleid_uit_naamlijst" in validatie.waarschuwingen


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


def test_bronportfolio_levert_complementaire_routes_met_menselijke_actie():
    documenten = [
        SourceDocument(
            naam="Voorbeeld Zorg",
            company_website_url="https://voorbeeldzorg.nl",
            url="https://voorbeeldzorg.nl/team",
            titel="Ons team",
            tekst="Maak kennis met ons team.",
            brontype="officiele_website",
            documenttype="teampagina",
        ),
        SourceDocument(
            naam="Voorbeeld Zorg",
            company_website_url="https://voorbeeldzorg.nl",
            url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
            titel="Jaarverslag 2025",
            tekst="Jaarverslag van Voorbeeld Zorg.",
            brontype="jaarverslag",
            documenttype="jaarverslag",
            gevraagd_jaar=2025,
            verslagjaar=2025,
        ),
        SourceDocument(
            naam="Voorbeeld Zorg",
            company_website_url="https://voorbeeldzorg.nl",
            url="https://nieuws.example/voorbeeld-zorg-breidt-uit",
            titel="Voorbeeld Zorg breidt uit",
            tekst="Voorbeeld Zorg opent een nieuwe locatie.",
            brontype="media",
            documenttype="nieuwsartikel",
            publicatiedatum=date(2026, 7, 1),
        ),
    ]
    ranked = rank_bronnen([valideer_bron(item) for item in documenten])

    portfolio = selecteer_bronportfolio(ranked, maximum=3)

    rollen = {
        item.validaties["menselijke_waarde"]["rol"]
        for item in portfolio
    }
    assert rollen == {"teamoverzicht", "formeel_document", "actuele_context"}
    assert all(
        item.validaties["menselijke_waarde"]["actie"]
        for item in portfolio
    )


def test_vestigingsanker_verdringt_niet_maar_wordt_ook_niet_zomaar_gedropt():
    """
    Regressie: Hallux Podotherapie Roermond. De juiste vestigingspagina (vier
    genoemde medewerkers) werd gevonden, maar viel buiten de top-3 doordat een
    algemenere concernpagina met net iets hogere score de top vulde. Ranking
    beloont autoriteit/actualiteit/bewijs, maar niet expliciet "gaat dit over
    déze vestiging" — behoud_vestigingsanker repareert dat na het ranken.
    """
    vestigingspagina = valideer_bron(SourceDocument(
        naam="Hallux Podotherapie",
        company_website_url="https://hallux.nl",
        url="https://hallux.nl/roermond/ons-team",
        titel="Ons team in Roermond",
        tekst="In Roermond werken vier podotherapeuten voor u klaar.",
        brontype="officiele_website",
        documenttype="teampagina",
        wp_gevonden=4,
        eenheid="werkzame_personen",
        bewijsfragment="In Roermond werken vier podotherapeuten voor u klaar.",
        scope_class="vestiging",
    ))
    algemene_paginas = [
        valideer_bron(SourceDocument(
            naam="Hallux Podotherapie",
            company_website_url="https://hallux.nl",
            url=f"https://hallux.nl/over-ons-{index}",
            titel=f"Over Hallux {index}",
            tekst="Hallux Podotherapie is een landelijke keten.",
            brontype="officiele_website",
            documenttype="organisatiepagina",
            wp_gevonden=120,
            eenheid="werkzame_personen",
            bewijsfragment="Hallux telt landelijk 120 medewerkers.",
            scope_class="concern",
            publicatiedatum=date(2026, 7, 1),
        ))
        for index in range(3)
    ]
    ranked = rank_bronnen(
        [*algemene_paginas, vestigingspagina], referentiedatum=date(2026, 7, 24),
    )
    # De vestigingspagina staat niet vanzelf in de kale top-3.
    assert vestigingspagina.document.url not in [
        bron.document.url for bron in ranked[:3]
    ]

    top = behoud_vestigingsanker(ranked, maximum=3)

    assert len(top) == 3
    assert vestigingspagina.document.url in [bron.document.url for bron in top]


def test_vestigingsanker_verandert_niets_als_de_top_er_al_een_bevat():
    document = SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url="https://voorbeeldzorg.nl/vestiging",
        titel="Vestiging",
        tekst="In Heerlen werken 10 medewerkers.",
        brontype="officiele_website",
        wp_gevonden=10,
        eenheid="werkzame_personen",
        bewijsfragment="In Heerlen werken 10 medewerkers.",
        scope_class="vestiging",
    )
    ranked = rank_bronnen([valideer_bron(document)])

    top = behoud_vestigingsanker(ranked, maximum=3)

    assert top == ranked[:3]


def test_vestigingsanker_doet_niets_zonder_kandidaten():
    assert behoud_vestigingsanker([], maximum=3) == []


def test_bronportfolio_beperkt_dubbele_rollen_tot_twee():
    documenten = [
        SourceDocument(
            naam="Voorbeeld Zorg",
            company_website_url="https://voorbeeldzorg.nl",
            url=f"https://voorbeeldzorg.nl/pagina-{index}",
            titel=f"Organisatiepagina {index}",
            tekst="Voorbeeld Zorg",
            brontype="officiele_website",
            documenttype="organisatiepagina",
        )
        for index in range(5)
    ]
    ranked = rank_bronnen([valideer_bron(item) for item in documenten])

    portfolio = selecteer_bronportfolio(ranked, maximum=8)

    assert len(portfolio) == 2
    assert {
        item.validaties["menselijke_waarde"]["rol"]
        for item in portfolio
    } == {"officiele_route"}
