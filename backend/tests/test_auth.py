from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import SessionLocal
from app.main import app
from app.models import User

client = TestClient(app)


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).timestamp()}@example.test"


def _create_user(email: str, password: str = "TestWachtwoord2026!") -> None:
    db = SessionLocal()
    try:
        db.add(User(naam="Tester", email=email, rol="reviewer",
                    password_hash=hash_password(password)))
        db.commit()
    finally:
        db.close()


def test_health_blijft_open():
    assert client.get("/health").status_code == 200


def test_bronnenwerkbank_vraagt_login():
    assert client.get("/batches").status_code == 401


def test_login_en_me():
    email = _unique_email("login")
    _create_user(email)
    login = client.post(
        "/auth/login",
        data={"username": email, "password": "TestWachtwoord2026!"},
    )
    token = login.json()["access_token"]

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == email
