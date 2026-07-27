"""Tests voor de dashboard-niveau /monitoring-endpoints (geen batch_id in de URL)."""
from datetime import datetime, timezone
from io import BytesIO

from app.models import Candidate, Company, JaarverslagMonitoring, PipelineRun, User
from app.routers import monitoring as monitoring_router


def _zorg_voor_test_user(db_session):
    """Uploads koppelen geupload_door (FK naar users.id) aan de ingelogde
    testgebruiker; die rij bestaat niet automatisch in de testdatabase."""
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(id="test-user-id", naam="Test User", email="test@etil.nl",
                            rol="admin", password_hash=""))
        db_session.commit()


def test_monitoring_status_zonder_watchlist_geeft_lege_staat(client):
    response = client.get("/monitoring")

    assert response.status_code == 200
    assert response.json() == {
        "batch": None, "totaal": 0, "gecontroleerd": 0,
        "bronnen_gevonden": 0, "bronnen_ontbreken": 0,
        "nieuwe_bevindingen": 0, "fouten": 0, "companies": [],
    }


def test_monitoring_status_met_actieve_watchlist(client, db_session):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(
            b"naam\nGecontroleerde Organisatie\nNog Niet Gecontroleerd\n"
        ), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    companies = {c.naam: c for c in db_session.query(Company).filter_by(batch_id=batch_id)}
    gecontroleerd = companies["Gecontroleerde Organisatie"]

    nu = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(JaarverslagMonitoring(
        company_id=gecontroleerd.id, laatste_bron_url="https://voorbeeld.test/jaarverslag.pdf",
        laatst_gecontroleerd_op=nu,
    ))
    db_session.add(PipelineRun(batch_id=batch_id, company_id=gecontroleerd.id,
                               stap="jaarverslag_monitoring", status="new", duur_ms=100))
    db_session.add(Candidate(company_id=gecontroleerd.id, batch_id=batch_id,
                             wp_kandidaat=50, is_schatting=False,
                             confidence_score=0.9, confidence_label="hoog", strategie="auto"))
    db_session.commit()

    response = client.get("/monitoring")

    assert response.status_code == 200
    data = response.json()
    assert data["batch"] == {"id": batch_id, "naam": "watchlist", "jaar": 2026}
    assert data["totaal"] == 2
    assert data["gecontroleerd"] == 1
    assert data["bronnen_gevonden"] == 1
    assert data["bronnen_ontbreken"] == 1
    assert data["nieuwe_bevindingen"] == 1
    assert data["fouten"] == 0

    per_naam = {c["naam"]: c for c in data["companies"]}
    assert per_naam["Gecontroleerde Organisatie"]["nieuwe_bevinding"] is True
    assert per_naam["Gecontroleerde Organisatie"]["bron_status"] == "gevonden"
    assert per_naam["Gecontroleerde Organisatie"]["wp_kandidaat"] == 50
    assert per_naam["Nog Niet Gecontroleerd"]["laatst_gecontroleerd_op"] is None
    assert per_naam["Nog Niet Gecontroleerd"]["bron_status"] == "ontbreekt"


def test_monitoring_dashboard_toont_alleen_laatste_controleuitkomst(
    client, db_session,
):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-latest&jaar=2026&monitoringlijst=true",
        files={"file": (
            "orgs.csv",
            BytesIO(b"naam\nOrganisatie X\n"),
            "text/csv",
        )},
    )
    batch_id = upload.json()["batch_id"]
    company = db_session.query(Company).filter_by(batch_id=batch_id).one()
    db_session.add_all([
        PipelineRun(
            batch_id=batch_id,
            company_id=company.id,
            stap="jaarverslag_monitoring",
            status="ok",
            duur_ms=100,
            created_at=datetime(2026, 7, 1),
        ),
        PipelineRun(
            batch_id=batch_id,
            company_id=company.id,
            stap="jaarverslag_monitoring",
            status="skipped",
            duur_ms=100,
            created_at=datetime(2026, 7, 8),
        ),
    ])
    db_session.commit()

    data = client.get("/monitoring").json()

    assert data["nieuwe_bevindingen"] == 0
    assert data["companies"][0]["nieuwe_bevinding"] is False


def test_monitoring_dashboard_noemt_betere_extractie_geen_nieuw_jaarverslag(
    client, db_session,
):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-update&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie X\n"), "text/csv")},
    )
    batch_id = upload.json()["batch_id"]
    company = db_session.query(Company).filter_by(batch_id=batch_id).one()
    db_session.add(PipelineRun(
        batch_id=batch_id,
        company_id=company.id,
        stap="jaarverslag_monitoring",
        status="updated",
        duur_ms=100,
    ))
    db_session.commit()

    data = client.get("/monitoring").json()

    assert data["nieuwe_bevindingen"] == 0
    assert data["companies"][0]["nieuwe_bevinding"] is False


def test_monitoring_run_zonder_watchlist_geeft_404(client):
    response = client.post("/monitoring/run")
    assert response.status_code == 404


def test_monitoring_run_start_achtergrondtaak(client, db_session, monkeypatch):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-run&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie X\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    gestart = []

    def fake_run_monitoring_watchlist_background(
        limit=None, offset=0,
    ) -> None:
        gestart.append((limit, offset))

    monkeypatch.setattr(monitoring_router, "run_monitoring_watchlist_background",
                        fake_run_monitoring_watchlist_background)

    response = client.post("/monitoring/run")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch_id,
        "aantal_companies": 1,
        "offset": 0,
    }
    assert gestart == [(None, 0)]


def test_monitoring_run_met_limit_beperkt_aantal_companies(client, db_session, monkeypatch):
    """Met ?limit=N wordt maar een deel van de watchlist gecontroleerd — bedoeld
    om tijdens ontwikkelen/testen niet steeds de volledige (kostbare) live-lijst
    te hoeven doorlopen."""
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-run-groot&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(
            b"naam\nOrganisatie A\nOrganisatie B\nOrganisatie C\n"
        ), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    gestart = []

    def fake_run_monitoring_watchlist_background(
        limit=None, offset=0,
    ) -> None:
        gestart.append((limit, offset))

    monkeypatch.setattr(monitoring_router, "run_monitoring_watchlist_background",
                        fake_run_monitoring_watchlist_background)

    response = client.post("/monitoring/run?limit=2")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch_id,
        "aantal_companies": 2,
        "offset": 0,
    }
    assert gestart == [(2, 0)]


def test_monitoring_run_met_limit_groter_dan_watchlist_gebruikt_totaal(client, db_session, monkeypatch):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-run-klein&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie X\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    monkeypatch.setattr(
        monitoring_router,
        "run_monitoring_watchlist_background",
        lambda limit=None, offset=0: None,
    )

    response = client.post("/monitoring/run?limit=50")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch_id,
        "aantal_companies": 1,
        "offset": 0,
    }


def test_monitoring_run_met_offset_start_bij_latere_organisatie(
    client, db_session, monkeypatch,
):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-offset&jaar=2026&monitoringlijst=true",
        files={"file": (
            "orgs.csv",
            BytesIO(b"naam\nA\nB\nC\nD\n"),
            "text/csv",
        )},
    )
    batch_id = upload.json()["batch_id"]
    gestart = []
    monkeypatch.setattr(
        monitoring_router,
        "run_monitoring_watchlist_background",
        lambda limit=None, offset=0: gestart.append((limit, offset)),
    )

    response = client.post("/monitoring/run?limit=2&offset=2")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch_id,
        "aantal_companies": 2,
        "offset": 2,
    }
    assert gestart == [(2, 2)]
