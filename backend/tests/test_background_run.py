from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import SessionLocal
from app.main import app
from app.models import Batch, User
from app.routers import batches as batches_router


client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    email = f"background-{datetime.utcnow().timestamp()}@example.test"
    password = "TestWachtwoord2026!"
    db = SessionLocal()
    try:
        db.add(User(naam="Background Tester", email=email, rol="reviewer",
                    password_hash=hash_password(password)))
        db.commit()
    finally:
        db.close()

    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_run_batch_start_standaard_autonome_research(monkeypatch):
    db = SessionLocal()
    try:
        batch = Batch(naam="background-test", jaar=2026, totaal=3, verwerkt=2)
        db.add(batch)
        db.commit()
        batch_id = batch.id
    finally:
        db.close()

    scheduled = []

    def fake_run_research_batch_background(batch_id_arg: str) -> None:
        scheduled.append(batch_id_arg)

    monkeypatch.setattr(
        batches_router,
        "run_research_batch_background",
        fake_run_research_batch_background,
    )

    response = client.post(f"/batches/{batch_id}/run", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch_id,
        "status": "running",
        "verwerkt": 0,
        "totaal": 3,
        "workflow": "autonome_bronnenresearch",
    }
    assert scheduled == [batch_id]

    poll = client.get(f"/batches/{batch_id}", headers=_auth_headers())
    assert poll.status_code == 200
    assert poll.json()["status"] == "running"


def test_legacy_pipeline_blijft_expiet_beschikbaar(monkeypatch):
    db = SessionLocal()
    try:
        batch = Batch(naam="legacy-test", jaar=2026, totaal=1)
        db.add(batch)
        db.commit()
        batch_id = batch.id
    finally:
        db.close()

    scheduled = []
    monkeypatch.setattr(
        batches_router,
        "run_batch_background",
        lambda batch_id_arg: scheduled.append(batch_id_arg),
    )

    response = client.post(
        f"/batches/{batch_id}/run-legacy",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["workflow"] == "legacy_pipeline"
    assert scheduled == [batch_id]
