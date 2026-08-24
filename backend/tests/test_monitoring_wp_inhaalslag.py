"""Een bronkaart zonder WP-getal moet alsnog doorzocht worden."""
from app.models import Batch, BronKandidaat, Company, ResearchRun
from app.pipeline.monitoring import (
    WP_EXTRACTIE,
    WP_GEVONDEN,
    WP_GEZOCHT_NIETS_GEVONDEN,
    _bronkaart_zonder_wp_extractie,
    _markeer_wp_gezocht,
)


def _kaart(db_session, url: str, **velden) -> BronKandidaat:
    batch = Batch(naam="watchlist", jaar=2026, totaal=1, is_monitoringlijst=True)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Zorggroep Voorbeeld")
    db_session.add(company)
    db_session.flush()
    run = ResearchRun(
        company_id=company.id, batch_id=batch.id,
        doel="monitoring", status="completed",
    )
    db_session.add(run)
    db_session.flush()
    kandidaat = BronKandidaat(
        research_run_id=run.id, company_id=company.id,
        url=url, canonical_url=url, brontype="jaarverslag", status="voorgesteld",
        **velden,
    )
    db_session.add(kandidaat)
    db_session.commit()
    return company, kandidaat


def test_kaart_zonder_getal_komt_in_aanmerking(db_session):
    """Deze bleven voorgoed leeg: hun URL verandert niet meer, dus elke ronde
    kwam uit op "ongewijzigd" en de extractie draaide nooit."""
    url = "https://voorbeeld.nl/jaarverslag-2024.pdf"
    company, kandidaat = _kaart(db_session, url)

    gevonden = _bronkaart_zonder_wp_extractie(db_session, company, url)

    assert gevonden is not None
    assert gevonden.id == kandidaat.id


def test_kaart_met_een_getal_wordt_met_rust_gelaten(db_session):
    url = "https://voorbeeld.nl/jaarverslag-2025.pdf"
    company, _ = _kaart(
        db_session, url, wp_gevonden=412, eenheid="werkzame_personen",
    )

    assert _bronkaart_zonder_wp_extractie(db_session, company, url) is None


def test_een_eerdere_vergeefse_poging_wordt_niet_herhaald(db_session):
    """Een verslag zonder personeelsgetal hoeft niet elke ronde opnieuw
    ~1 cent te kosten voor hetzelfde antwoord."""
    url = "https://voorbeeld.nl/jaarverslag-2023.pdf"
    company, kandidaat = _kaart(db_session, url)
    _markeer_wp_gezocht(kandidaat, gevonden=False)
    db_session.commit()

    assert _bronkaart_zonder_wp_extractie(db_session, company, url) is None
    assert kandidaat.validaties[WP_EXTRACTIE] == WP_GEZOCHT_NIETS_GEVONDEN


def test_markering_laat_bestaande_validaties_staan(db_session):
    url = "https://voorbeeld.nl/jv.pdf"
    _, kandidaat = _kaart(
        db_session, url, validaties={"domein_match": True},
    )

    _markeer_wp_gezocht(kandidaat, gevonden=True)

    assert kandidaat.validaties["domein_match"] is True
    assert kandidaat.validaties[WP_EXTRACTIE] == WP_GEVONDEN
