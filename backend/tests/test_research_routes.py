"""Minimale, deterministische routeselectie per organisatieprofiel."""

from app.research.query_planner import QueryContext, plan_routes


def _routes(context: QueryContext) -> dict[str, dict]:
    return {item["route"]: item for item in plan_routes(context)}


def test_onderwijs_krijgt_duo_en_documentroute():
    routes = _routes(QueryContext(
        naam="Voorbeeldschool",
        sbi_code="85201",
        sbi_omschrijving="Basisonderwijs",
    ))

    assert routes["duo"]["verplicht"] is True
    assert routes["document"]["verplicht"] is True
    assert routes["duo"]["status"] == "wachtend"
    assert "digimv" not in routes


def test_zorg_krijgt_digimv_en_documentroute():
    routes = _routes(QueryContext(
        naam="Voorbeeld Zorg",
        sbi_code="86101",
        sbi_omschrijving="Ziekenhuizen",
    ))

    assert routes["digimv"]["verplicht"] is True
    assert routes["document"]["verplicht"] is True
    assert "duo" not in routes


def test_lokale_zorgpraktijk_krijgt_teamroute_en_digimv_voorwaardelijk():
    routes = _routes(QueryContext(
        naam="Voorbeeld Tandarts",
        sbi_code="86231",
        sbi_omschrijving="Praktijken van tandartsen",
    ))

    assert routes["team_afspraak"]["verplicht"] is True
    assert routes["digimv"]["verplicht"] is False
    assert "document" not in routes


def test_kapper_krijgt_team_afspraakroute_zonder_documentroute():
    routes = _routes(QueryContext(
        naam="Voorbeeldkapper",
        sbi_code="96021",
        sbi_omschrijving="Haarverzorging",
    ))

    assert routes["team_afspraak"]["verplicht"] is True
    assert "document" not in routes
    assert {"website", "media"}.issubset(routes)


def test_onbekend_profiel_houdt_het_bestaande_basisplan():
    routes = _routes(QueryContext(naam="Voorbeeldbedrijf"))

    assert set(routes) == {"website", "document", "media"}
    assert routes["document"]["verplicht"] is False


def test_zorgnaam_krijgt_digimv_ook_zonder_sbi_code():
    """
    Regressie: KvK-verrijking levert niet altijd een SBI-code op. Een
    bedrijfsnaam als "Hospice de Ark" is ook zonder sbi_code herkenbaar als
    Wlz-zorgaanbieder — jaarverantwoordingzorg.nl is wettelijk verplicht voor
    elke Wlz/Zvw-zorgaanbieder, ongeacht grootte of SBI-registratie.
    """
    for naam in (
        "Hospice de Ark",
        "Woonzorgcentrum Amaliahof",
        "Groene Kruis Kraamzorg - Regio Westelijke Mijnstreek",
        "Groene Kruis Wijkverpleging, Team Echt Zuid",
        "Groepswoningen Eldershof",
        "Revalidatiekliniek Noord-Limburg - Venray",
        "Integr. Expert.centr. Psychogeriatrie Venray",
        "Stichting Punt Welzijn",
    ):
        routes = _routes(QueryContext(naam=naam))
        assert "digimv" in routes, f"{naam} zou digimv moeten krijgen"


def test_onderwijsnaam_krijgt_duo_ook_zonder_sbi_code():
    for naam in ("Zuyd Hogeschool", "Open Universiteit"):
        routes = _routes(QueryContext(naam=naam))
        assert routes["duo"]["verplicht"] is True, f"{naam} zou duo moeten krijgen"


def test_sbi_code_blijft_leidend_ook_als_naam_neutraal_is():
    """Een sbi-treffer werkt onafhankelijk van wat de naam wel of niet bevat."""
    routes = _routes(QueryContext(
        naam="Okechamp B.V.", sbi_code="1039", sbi_omschrijving="Groente verwerken",
    ))

    assert "digimv" not in routes
    assert "duo" not in routes


def test_merknaam_zonder_sectorwoord_wordt_niet_geforceerd():
    """
    Een generieke merknaam zonder sbi-code en zonder sectorwoord in de naam
    (zoals "Stichting Philadelphia") wordt terecht niet herkend — de fallback
    raadt niet, hij herkent alleen expliciete sectorwoorden.
    """
    routes = _routes(QueryContext(naam="Stichting Philadelphia"))

    assert "digimv" not in routes
