from datetime import datetime, timezone
from io import BytesIO

from app.models import Candidate, Company, JaarverslagMonitoring, PipelineRun
from app.routers import batches as batches_router


def test_monitor_batch_start_achtergrondtaak(client, monkeypatch):
    upload = client.post(
        "/batches/upload?naam=monitor-endpoint-test&jaar=2026",
        files={"file": ("monitor.csv", BytesIO(b"naam\nOkechamp B.V.\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    scheduled = []

    def fake_run_monitoring_background(batch_id_arg: str) -> None:
        scheduled.append(batch_id_arg)

    monkeypatch.setattr(batches_router, "run_monitoring_background", fake_run_monitoring_background)

    response = client.post(f"/batches/{batch_id}/monitor")

    assert response.status_code == 200
    assert response.json() == {"batch_id": batch_id, "aantal_companies": 1}
    assert scheduled == [batch_id]


def test_monitoring_status_toont_gecontroleerde_en_ongecontroleerde_vestigingen(client, db_session):
    upload = client.post(
        "/batches/upload?naam=monitoring-status-test&jaar=2026",
        files={"file": ("bedrijven.csv", BytesIO(
            b"naam\nGecontroleerd B.V.\nNog Niet Gecontroleerd B.V.\nFoutbedrijf B.V.\n"
        ), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    companies = {c.naam: c for c in db_session.query(Company).filter_by(batch_id=batch_id)}
    gecontroleerd = companies["Gecontroleerd B.V."]
    niet_gecontroleerd = companies["Nog Niet Gecontroleerd B.V."]
    fout_bedrijf = companies["Foutbedrijf B.V."]

    nu = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(JaarverslagMonitoring(
        company_id=gecontroleerd.id, laatste_bron_url="https://voorbeeld.test/jaarverslag-2026.pdf",
        laatst_gecontroleerd_op=nu,
    ))
    db_session.add(PipelineRun(batch_id=batch_id, company_id=gecontroleerd.id,
                               stap="jaarverslag_monitoring", status="ok", duur_ms=120))
    db_session.add(Candidate(company_id=gecontroleerd.id, batch_id=batch_id,
                             wp_kandidaat=42, is_schatting=False,
                             confidence_score=0.9, confidence_label="hoog", strategie="auto"))
    db_session.add(JaarverslagMonitoring(
        company_id=fout_bedrijf.id, laatst_gecontroleerd_op=nu,
    ))
    db_session.add(PipelineRun(batch_id=batch_id, company_id=fout_bedrijf.id,
                               stap="jaarverslag_monitoring", status="error",
                               duur_ms=80, error="time-out bij ophalen pagina"))
    db_session.commit()

    response = client.get(f"/batches/{batch_id}/monitoring")

    assert response.status_code == 200
    data = response.json()
    assert data["batch_id"] == batch_id
    assert data["totaal"] == 3
    assert data["gecontroleerd"] == 2
    assert data["nieuwe_bevindingen"] == 1
    assert data["fouten"] == 1

    per_naam = {c["naam"]: c for c in data["companies"]}

    assert per_naam["Gecontroleerd B.V."]["laatst_gecontroleerd_op"] is not None
    assert per_naam["Gecontroleerd B.V."]["laatste_bron_url"] == "https://voorbeeld.test/jaarverslag-2026.pdf"
    assert per_naam["Gecontroleerd B.V."]["nieuwe_bevinding"] is True
    assert per_naam["Gecontroleerd B.V."]["wp_kandidaat"] == 42
    assert per_naam["Gecontroleerd B.V."]["fout"] is None

    assert per_naam["Nog Niet Gecontroleerd B.V."]["laatst_gecontroleerd_op"] is None
    assert per_naam["Nog Niet Gecontroleerd B.V."]["laatste_bron_url"] is None
    assert per_naam["Nog Niet Gecontroleerd B.V."]["nieuwe_bevinding"] is False

    assert per_naam["Foutbedrijf B.V."]["nieuwe_bevinding"] is False
    assert per_naam["Foutbedrijf B.V."]["fout"] == "time-out bij ophalen pagina"


def test_monitoring_status_onbekende_batch_geeft_404(client):
    response = client.get("/batches/onbekend-batch-id/monitoring")
    assert response.status_code == 404
