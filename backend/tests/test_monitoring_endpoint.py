from io import BytesIO

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
