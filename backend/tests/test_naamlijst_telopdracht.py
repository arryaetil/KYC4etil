"""Een namenlijst die niet het personeelsbestand van déze vestiging is,
levert een telopdracht voor de reviewer op in plaats van een WP-voorstel.

De gevallen hieronder komen uit de productieruns van 16-08-2026: Okechamp
kreeg zes bestuurders van de Poolse moedergroep als WP-getal, Mondriaan drie
voornamen uit een opleidingspagina. Poulissen, Dreessen en Hallux staan er
als regressiebewaking bij — daar is het tellen van de teampagina juist het
goede antwoord en dat moet zo blijven.
"""
from app.research.ranking import rank_bronnen
from app.research.validation import SourceDocument, valideer_bron


def _naamlijstbron(**overrides) -> SourceDocument:
    basis = dict(
        naam="Voorbeeld B.V.",
        company_website_url="https://voorbeeld.nl",
        url="https://voorbeeld.nl/team/",
        titel="Ons team",
        tekst="Jan Jansen, Marie de Vries, Piet Peters",
        brontype="officiele_website",
        documenttype="teampagina",
        wp_gevonden=3,
        eenheid="werkzame_personen",
        bewijsfragment="Jan Jansen, Marie de Vries, Piet Peters",
        scope_class="unknown",
        raw_data={
            "wp_afgeleid_uit_naamlijst": True,
            "genoemde_namen": [
                "Jan Jansen (adviseur)", "Marie de Vries", "Piet Peters",
            ],
        },
    )
    return SourceDocument(**{**basis, **overrides})


def test_bestuurspagina_levert_telopdracht_in_plaats_van_wp_getal():
    """Okechamp: zes C-level bestuurders zijn geen zes werkzame personen."""
    document = _naamlijstbron(
        naam="Okechamp B.V.",
        company_website_url="https://okechamp.pl/nl/",
        url="https://okechamp.pl/nl/kim-jestesmy/zarzad/",
        titel="Management Team",
        wp_gevonden=6,
        scope_class="concern",
        raw_data={
            "wp_afgeleid_uit_naamlijst": True,
            "genoemde_namen": [
                "Robin Barkmeijer (CEO)", "Wojciech Kocikowski (CFO)",
                "Frank Van der Linden (COO)",
            ],
        },
    )

    validatie = valideer_bron(document)

    assert validatie.document.wp_gevonden is None
    assert validatie.document.eenheid is None
    assert "naamlijst_telling_aan_reviewer" in validatie.waarschuwingen
    telopdracht = validatie.validaties["naamlijst_telling_aan_reviewer"]
    assert telopdracht["reden"] == "leidinggevendenlijst"
    assert telopdracht["afgeleid_aantal"] == 6
    assert len(telopdracht["genoemde_namen"]) == 3
    assert validatie.validaties["heeft_wp"] is False


def test_namenlijst_buiten_de_vestigingsscope_levert_telopdracht():
    """Mondriaan: drie voornamen op een landelijke opleidingspagina."""
    document = _naamlijstbron(
        naam="Mondriaan",
        company_website_url="https://www.mondriaan.eu/",
        url="https://www.mondriaan.eu/nl/werken-en-leren/opleiding-tot-psychiater",
        titel="Werken en leren bij Mondriaan",
        scope_class="nederland",
    )

    validatie = valideer_bron(document)

    assert validatie.document.wp_gevonden is None
    assert (
        validatie.validaties["naamlijst_telling_aan_reviewer"]["reden"]
        == "scope_buiten_vestiging"
    )


def test_onbekende_scope_behoudt_de_telling():
    """Poulissen en Dreessen staan op scope 'unknown' en tellen daar correct.

    Zou 'unknown' als onbruikbaar gelden, dan verdwijnt precies het gedrag dat
    de teamlijst-telling moest opleveren.
    """
    validatie = valideer_bron(_naamlijstbron(scope_class="unknown"))

    assert validatie.document.wp_gevonden == 3
    assert "naamlijst_telling_aan_reviewer" not in validatie.waarschuwingen


def test_vestigingsscope_behoudt_de_telling():
    validatie = valideer_bron(_naamlijstbron(scope_class="vestiging"))

    assert validatie.document.wp_gevonden == 3


def test_letterlijk_genoemd_concerngetal_blijft_ongemoeid():
    """Alleen afgeleide tellingen worden ingetrokken, geen echte cijfers."""
    document = _naamlijstbron(
        url="https://voorbeeld.nl/jaarverslag-2025.pdf",
        titel="Jaarverslag 2025",
        documenttype="jaarverslag",
        brontype="jaarverslag",
        wp_gevonden=61,
        bewijsfragment="Medewerkers: gemiddeld 2025: 61",
        scope_class="concern",
        raw_data={"wp_afgeleid_uit_naamlijst": False},
    )

    validatie = valideer_bron(document)

    assert validatie.document.wp_gevonden == 61


def test_telopdracht_krijgt_een_eigen_rol_in_de_ranking():
    ranked = rank_bronnen([valideer_bron(_naamlijstbron(
        url="https://voorbeeld.nl/over-ons/directie/",
        titel="Directie",
    ))])

    waarde = ranked[0].validaties["menselijke_waarde"]
    assert waarde["rol"] == "telopdracht"
    assert waarde["aantal_namen"] == 3
    # Zonder WP-getal telt deze bron niet langer als hard bewijs.
    assert ranked[0].score_breakdown["bewijs"] == 0.0
