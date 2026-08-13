"""Integratietests voor het herstellen van een onderbroken researchbatch."""
from app.models import Batch


def _batch(db_session, status: str) -> Batch:
    batch = Batch(
        naam="vastgelopen-batch", jaar=2026, status=status, totaal=5, verwerkt=2,
    )
    db_session.add(batch)
    db_session.commit()
    return batch


def test_reset_vastgelopen_zet_status_naar_pending(client, db_session):
    batch = _batch(db_session, "running")
    response = client.post(f"/batches/{batch.id}/reset-vastgelopen")
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_reset_vastgelopen_weigert_als_niet_running(client, db_session):
    batch = _batch(db_session, "completed")
    response = client.post(f"/batches/{batch.id}/reset-vastgelopen")
    assert response.status_code == 409


def test_reset_vastgelopen_batch_is_daarna_opvraagbaar(client, db_session):
    batch = _batch(db_session, "running")
    client.post(f"/batches/{batch.id}/reset-vastgelopen")
    response = client.get(f"/batches/{batch.id}")
    assert response.json()["status"] == "pending"
