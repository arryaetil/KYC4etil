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
