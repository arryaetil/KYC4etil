from datetime import datetime, timezone
from io import BytesIO

from app.models import BronKandidaat, Company, JaarverslagMonitoring, ResearchRun, User


def test_batch_met_monitoring_status_kan_verwijderd_worden(client, db_session):
    """Regressie: JaarverslagMonitoring-rijen blokkeerden het verwijderen van een
    batch (foreign-key-fout) omdat delete_batch ze niet opruimde vóór de
    company-rijen te verwijderen."""
    db_session.add(User(id="test-user-id", naam="Test User", email="test@etil.nl",
                        rol="admin", password_hash=""))
    db_session.commit()
    upload = client.post(
        "/batches/upload?naam=delete-monitoring-test&jaar=2026",
        files={"file": ("bedrijven.csv", BytesIO(b"naam\nGemonitord B.V.\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    company = db_session.query(Company).filter_by(batch_id=batch_id).one()
    db_session.add(JaarverslagMonitoring(
        company_id=company.id, laatste_bron_url="https://voorbeeld.test/jaarverslag.pdf",
        laatst_gecontroleerd_op=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db_session.commit()

    response = client.delete(f"/batches/{batch_id}")

    assert response.status_code == 200
    assert response.json() == {"deleted": batch_id}
    assert db_session.query(JaarverslagMonitoring).filter_by(company_id=company.id).count() == 0


def test_batch_met_researchresultaten_kan_verwijderd_worden(client, db_session):
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(id="test-user-id", naam="Test User", email="test@etil.nl",
                            rol="admin", password_hash=""))
        db_session.commit()
    upload = client.post(
        "/batches/upload?naam=delete-research-test&jaar=2026",
        files={"file": ("bedrijven.csv", BytesIO(b"naam\nOnderzocht B.V.\n"), "text/csv")},
    )
    batch_id = upload.json()["batch_id"]
    company = db_session.query(Company).filter_by(batch_id=batch_id).one()
    run = ResearchRun(
        company_id=company.id,
        batch_id=batch_id,
        doel="bronreview",
        status="completed",
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url="https://onderzocht.example/over-ons",
        canonical_url="https://onderzocht.example/over-ons",
        brontype="officiele_website",
    ))
    db_session.commit()

    response = client.delete(f"/batches/{batch_id}")

    assert response.status_code == 200
    assert db_session.query(BronKandidaat).filter_by(company_id=company.id).count() == 0
    assert db_session.query(ResearchRun).filter_by(company_id=company.id).count() == 0
