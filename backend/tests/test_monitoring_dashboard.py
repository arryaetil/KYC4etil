"""Tests voor de dashboard-niveau /monitoring-endpoints (geen batch_id in de URL)."""
from datetime import datetime, timezone
from io import BytesIO

from app.models import Candidate, Company, JaarverslagMonitoring, PipelineRun
from app.routers import monitoring as monitoring_router


def test_monitoring_status_zonder_watchlist_geeft_lege_staat(client):
    response = client.get("/monitoring")

    assert response.status_code == 200
    assert response.json() == {
        "batch": None, "totaal": 0, "gecontroleerd": 0,
        "bronnen_gevonden": 0, "bronnen_ontbreken": 0,
        "nieuwe_bevindingen": 0, "fouten": 0, "companies": [],
    }


def test_monitoring_status_met_actieve_watchlist(client, db_session):
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
                               stap="jaarverslag_monitoring", status="ok", duur_ms=100))
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


def test_monitoring_run_zonder_watchlist_geeft_404(client):
    response = client.post("/monitoring/run")
    assert response.status_code == 404


def test_monitoring_run_start_achtergrondtaak(client, monkeypatch):
    upload = client.post(
        "/batches/upload?naam=watchlist-run&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie X\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    gestart = []

    def fake_run_monitoring_watchlist_background(limit=None) -> None:
        gestart.append(limit)

    monkeypatch.setattr(monitoring_router, "run_monitoring_watchlist_background",
                        fake_run_monitoring_watchlist_background)

    response = client.post("/monitoring/run")

    assert response.status_code == 200
    assert response.json() == {"batch_id": batch_id, "aantal_companies": 1}
    assert gestart == [None]


def test_monitoring_run_met_limit_beperkt_aantal_companies(client, monkeypatch):
    """Met ?limit=N wordt maar een deel van de watchlist gecontroleerd — bedoeld
    om tijdens ontwikkelen/testen niet steeds de volledige (kostbare) live-lijst
    te hoeven doorlopen."""
    upload = client.post(
        "/batches/upload?naam=watchlist-run-groot&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(
            b"naam\nOrganisatie A\nOrganisatie B\nOrganisatie C\n"
        ), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    gestart = []

    def fake_run_monitoring_watchlist_background(limit=None) -> None:
        gestart.append(limit)

    monkeypatch.setattr(monitoring_router, "run_monitoring_watchlist_background",
                        fake_run_monitoring_watchlist_background)

    response = client.post("/monitoring/run?limit=2")

    assert response.status_code == 200
    assert response.json() == {"batch_id": batch_id, "aantal_companies": 2}
    assert gestart == [2]


def test_monitoring_run_met_limit_groter_dan_watchlist_gebruikt_totaal(client, monkeypatch):
    upload = client.post(
        "/batches/upload?naam=watchlist-run-klein&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie X\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    monkeypatch.setattr(monitoring_router, "run_monitoring_watchlist_background",
                        lambda limit=None: None)

    response = client.post("/monitoring/run?limit=50")

    assert response.status_code == 200
    assert response.json() == {"batch_id": batch_id, "aantal_companies": 1}
