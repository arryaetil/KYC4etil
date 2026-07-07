"""Tests voor de is_monitoringlijst-vlag op Batch en de upload-ondersteuning ervoor."""
from io import BytesIO

from app.models import Batch


def _upload(client, naam: str, monitoringlijst: bool = False):
    params = f"naam={naam}&jaar=2026"
    if monitoringlijst:
        params += "&monitoringlijst=true"
    return client.post(
        f"/batches/upload?{params}",
        files={"file": ("bedrijven.csv", BytesIO(b"naam\nTestbedrijf B.V.\n"), "text/csv")},
    )


def test_upload_met_monitoringlijst_true_zet_de_vlag(client, db_session):
    response = _upload(client, "watchlist-test", monitoringlijst=True)

    assert response.status_code == 200
    batch_id = response.json()["batch_id"]
    batch = db_session.get(Batch, batch_id)
    assert batch.is_monitoringlijst is True


def test_upload_zonder_monitoringlijst_laat_vlag_op_false(client, db_session):
    response = _upload(client, "gewone-batch")

    assert response.status_code == 200
    batch = db_session.get(Batch, response.json()["batch_id"])
    assert batch.is_monitoringlijst is False


def test_nieuwe_monitoringlijst_ontmarkeert_de_vorige(client, db_session):
    eerste = _upload(client, "watchlist-v1", monitoringlijst=True)
    tweede = _upload(client, "watchlist-v2", monitoringlijst=True)

    eerste_batch = db_session.get(Batch, eerste.json()["batch_id"])
    tweede_batch = db_session.get(Batch, tweede.json()["batch_id"])

    assert eerste_batch.is_monitoringlijst is False
    assert tweede_batch.is_monitoringlijst is True
