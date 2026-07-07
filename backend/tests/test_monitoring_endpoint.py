from io import BytesIO

from app.models import Batch, Company, JaarverslagMonitoring, PipelineRun
from app.routers import batches as batches_router
from tests.conftest import _Session


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


def test_monitoring_summary_toont_laatste_monitoringbatch(client):
    db = _Session()
    try:
        batch = Batch(naam="Jaarverslag monitoring - test", jaar=2026, totaal=2)
        db.add(batch)
        db.flush()
        company_ok = Company(batch_id=batch.id, naam="Okechamp B.V.")
        company_skip = Company(batch_id=batch.id, naam="Geen verslag B.V.")
        db.add_all([company_ok, company_skip])
        db.flush()
        db.add_all([
            JaarverslagMonitoring(company_id=company_ok.id, laatste_bron_url="https://example.test/jaarverslag.pdf"),
            JaarverslagMonitoring(company_id=company_skip.id),
            PipelineRun(batch_id=batch.id, company_id=company_ok.id,
                        stap="jaarverslag_monitoring", status="ok", duur_ms=10),
            PipelineRun(batch_id=batch.id, company_id=company_skip.id,
                        stap="jaarverslag_monitoring", status="skipped", duur_ms=10),
        ])
        db.commit()
        batch_id = batch.id
    finally:
        db.close()

    response = client.get("/batches/monitoring/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["batch"]["id"] == batch_id
    assert data["checked"] == 2
    assert data["total"] == 2
    assert data["findings"] == 1
    assert data["skipped"] == 1
    assert data["errors"] == 0
    assert data["schedule"] == {"enabled": False, "label": "Niet ingepland"}
