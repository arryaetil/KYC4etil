from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import SessionLocal
from app.main import app
from app.models import Batch, CallListItem, Candidate, Company, Enrichment, User, WPRecord


client = TestClient(app)


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{datetime.utcnow().timestamp()}@example.test"


def _create_user(email: str, password: str = "TestWachtwoord2026!") -> User:
    db = SessionLocal()
    try:
        user = User(naam="Tester", email=email, rol="reviewer",
                    password_hash=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _token(email: str, password: str = "TestWachtwoord2026!") -> str:
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_blijft_open():
    response = client.get("/health")
    assert response.status_code == 200


def test_bestaande_endpoint_vraagt_login():
    response = client.get("/batches")
    assert response.status_code == 401


def test_login_en_me():
    email = _unique_email("login")
    _create_user(email)
    token = _token(email)

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == email


def test_approve_vult_goedgekeurd_door():
    email = _unique_email("approve")
    user = _create_user(email)
    db = SessionLocal()
    try:
        batch = Batch(naam="auth-test", jaar=2026, totaal=1)
        db.add(batch)
        db.flush()
        company = Company(batch_id=batch.id, vestigingsnummer="auth-1", naam="Testbedrijf")
        db.add(company)
        db.flush()
        candidate = Candidate(company_id=company.id, batch_id=batch.id, wp_kandidaat=12,
                              confidence_score=0.9, confidence_label="hoog",
                              score_breakdown={}, strategie="auto")
        db.add(candidate)
        db.commit()
        candidate_id = candidate.id
    finally:
        db.close()

    token = _token(email)
    response = client.post(
        f"/candidates/{candidate_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    db = SessionLocal()
    try:
        record = db.query(WPRecord).filter(WPRecord.candidate_id == candidate_id).one()
        assert record.goedgekeurd_door == user.id
    finally:
        db.close()


def test_bellijst_koppelt_reviewactie_aan_user():
    email = _unique_email("bellijst")
    user = _create_user(email)
    db = SessionLocal()
    try:
        batch = Batch(naam="bellijst-test", jaar=2026, totaal=1)
        db.add(batch)
        db.flush()
        company = Company(batch_id=batch.id, vestigingsnummer="bel-1", naam="Belbedrijf")
        db.add(company)
        db.flush()
        db.add(Enrichment(company_id=company.id, telefoonnummer="043-1234567",
                          locatie_count_nl=1, locatie_count_lb=1, locatie_bron="mock",
                          raw_data={}))
        candidate = Candidate(company_id=company.id, batch_id=batch.id, wp_kandidaat=None,
                              confidence_score=0.2, confidence_label="laag",
                              score_breakdown={}, strategie="bellijst")
        db.add(candidate)
        db.commit()
        candidate_id = candidate.id
    finally:
        db.close()


def test_company_detail_toont_vorige_jaarvergelijking():
    email = _unique_email("detail")
    _create_user(email)
    db = SessionLocal()
    try:
        batch = Batch(naam="detail-test", jaar=2026, totaal=1)
        db.add(batch)
        db.flush()
        company = Company(batch_id=batch.id, vestigingsnummer="det-1", naam="Detailbedrijf")
        db.add(company)
        db.flush()
        db.add(WPRecord(
            company_id=company.id,
            wp_waarde=100,
            wp_jaar=2025,
            bron_type="website",
            status="reviewed",
        ))
        candidate = Candidate(company_id=company.id, batch_id=batch.id, wp_kandidaat=140,
                              confidence_score=0.6, confidence_label="middel",
                              score_breakdown={}, strategie="auto")
        db.add(candidate)
        db.commit()
        batch_id = batch.id
        company_id = company.id
    finally:
        db.close()

    token = _token(email)
    response = client.get(
        f"/batches/{batch_id}/companies/{company_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["vorig_jaar"]["wp_jaar"] == 2025
    assert data["vorig_jaar"]["wp_waarde"] == 100
    assert data["vorig_jaar"]["verschil_abs"] == 40
    assert data["vorig_jaar"]["verschil_pct"] == 0.4
    assert data["vorig_jaar"]["signaal"] == "hoog"
