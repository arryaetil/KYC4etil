"""Wat het scherm belooft voordat je een lijst start.

Het bedrag stond vast in de frontend ($0,01–$0,02 per organisatie), geschreven
in juli en daarna nooit bijgesteld terwijl het model wisselde en er routes bij
kwamen — werkelijk werd het $0,015–$0,056. En het rekende met de hele lijst,
terwijl een herstart overslaat wat al onderzocht is.
"""
from app.models import Batch, Company, ResearchRun
from app.research.kostenraming import (
    STANDAARD_HOOG_USD,
    STANDAARD_LAAG_USD,
    kosten_per_organisatie,
)


def _run(batch: Batch, company: Company, usd: float, status: str = "completed"):
    return ResearchRun(
        company_id=company.id, batch_id=batch.id, doel="kosten", status=status,
        configuratie={"kosten": {"totaal_usd": usd, "currency": "USD"}},
    )


def _lijst(db_session, aantal: int) -> tuple[Batch, list[Company]]:
    batch = Batch(naam="kosten", jaar=2026, totaal=aantal)
    db_session.add(batch)
    db_session.flush()
    companies = []
    for nummer in range(aantal):
        company = Company(batch_id=batch.id, naam=f"Organisatie {nummer}",
                          vestigingsnummer=f"K-{nummer}")
        db_session.add(company)
        companies.append(company)
    db_session.commit()
    return batch, companies


def test_zonder_historie_geldt_de_gemeten_standaardband(db_session):
    band = kosten_per_organisatie(db_session)

    assert band["laag_usd"] == STANDAARD_LAAG_USD
    assert band["hoog_usd"] == STANDAARD_HOOG_USD
    assert band["gebaseerd_op_runs"] == 0


def test_band_komt_uit_de_eerdere_runs(db_session):
    batch, companies = _lijst(db_session, 20)
    # Oplopende bedragen: p10 en p90 horen de uitschieters buiten te laten.
    for nummer, company in enumerate(companies):
        db_session.add(_run(batch, company, usd=0.01 * (nummer + 1)))
    db_session.commit()

    band = kosten_per_organisatie(db_session)

    assert band["gebaseerd_op_runs"] == 20
    assert band["laag_usd"] == 0.03      # p10, niet het minimum van 0,01
    assert band["hoog_usd"] == 0.19      # p90, niet het maximum van 0,20
    assert band["mediaan_usd"] == 0.105


def test_runs_zonder_kosten_tellen_niet_mee(db_session):
    """Een monitoringronde die niets deed kost niets en zegt niets."""
    batch, companies = _lijst(db_session, 12)
    for company in companies:
        db_session.add(_run(batch, company, usd=0.0))
    db_session.commit()

    band = kosten_per_organisatie(db_session)

    assert band["gebaseerd_op_runs"] == 0
    assert band["laag_usd"] == STANDAARD_LAAG_USD


def test_lijst_meldt_hoeveel_organisaties_er_nog_te_onderzoeken_zijn(
    client, db_session,
):
    batch, companies = _lijst(db_session, 5)
    # Twee zijn al afgerond; die slaat de run over, dus de kostenindicatie
    # hoort ze ook niet mee te rekenen.
    for company in companies[:2]:
        db_session.add(_run(batch, company, usd=0.04))
    # Een mislukte run telt niet als afgerond: die organisatie moet opnieuw.
    db_session.add(_run(batch, companies[2], usd=0.01, status="error"))
    db_session.commit()

    rij = next(
        item for item in client.get("/batches").json()
        if item["id"] == batch.id
    )

    assert rij["totaal"] == 5
    assert rij["nog_te_onderzoeken"] == 3


def test_kostenindicatie_endpoint_geeft_de_band(client, db_session):
    batch, companies = _lijst(db_session, 12)
    for company in companies:
        db_session.add(_run(batch, company, usd=0.03))
    db_session.commit()

    band = client.get("/batches/kostenindicatie").json()

    assert band["gebaseerd_op_runs"] == 12
    assert band["mediaan_usd"] == 0.03
