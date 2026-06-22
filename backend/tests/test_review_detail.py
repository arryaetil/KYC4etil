"""Integratietests voor company-detail: vorig_jaar vergelijking en signaaldrempel."""
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import SessionLocal
from app.main import app
from app.models import Batch, Candidate, Company, User, WPRecord

client = TestClient(app)


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{datetime.utcnow().timestamp()}@example.test"


def _create_user(email: str) -> None:
    db = SessionLocal()
    try:
        db.add(User(naam="Tester", email=email, rol="reviewer",
                    password_hash=hash_password("Test2026!")))
        db.commit()
    finally:
        db.close()


def _token(email: str) -> str:
    r = client.post("/auth/login", data={"username": email, "password": "Test2026!"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _create_scenario(huidig_wp: int | None, vorig_wp: int | None,
                     huidig_jaar: int = 2026, vorig_jaar: int = 2025) -> tuple[str, str]:
    """Maakt batch + company + candidate + optioneel WPRecord vorig jaar."""
    db = SessionLocal()
    try:
        batch = Batch(naam="test-batch", jaar=huidig_jaar, status="done",
                      totaal=1, verwerkt=1)
        db.add(batch)
        db.flush()
        comp = Company(batch_id=batch.id, naam="TestBedrijf",
                       vestigingsnummer=f"LB-{datetime.utcnow().microsecond}")
        db.add(comp)
        db.flush()
        if huidig_wp is not None:
            db.add(Candidate(
                company_id=comp.id, batch_id=batch.id,
                wp_kandidaat=huidig_wp, is_schatting=False,
                confidence_score=0.90, confidence_label="hoog",
                strategie="auto", status="pending",
            ))
        if vorig_wp is not None:
            db.add(WPRecord(
                company_id=comp.id, wp_waarde=vorig_wp, wp_jaar=vorig_jaar,
                bron_type="reviewed", status="reviewed",
            ))
        db.commit()
        return batch.id, comp.id
    finally:
        db.close()


def _get_detail(batch_id: str, comp_id: str, token: str) -> dict:
    r = client.get(f"/batches/{batch_id}/companies/{comp_id}",
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    return r.json()


# --- vorig_jaar aanwezigheid ---

def test_vorig_jaar_afwezig_zonder_historisch_record():
    email = _unique_email("vj-geen")
    _create_user(email)
    token = _token(email)
    batch_id, comp_id = _create_scenario(huidig_wp=100, vorig_wp=None)
    assert _get_detail(batch_id, comp_id, token)["vorig_jaar"] is None


# --- signaaldrempel: hoog bij >25% stijging ---

def test_vorig_jaar_signaal_hoog_bij_stijging_groter_dan_25_pct():
    email = _unique_email("vj-hoog-stijging")
    _create_user(email)
    token = _token(email)
    batch_id, comp_id = _create_scenario(huidig_wp=150, vorig_wp=100)  # +50%
    vj = _get_detail(batch_id, comp_id, token)["vorig_jaar"]
    assert vj is not None
    assert vj["verschil_abs"] == 50
    assert round(vj["verschil_pct"], 4) == 0.5
    assert vj["signaal"] == "hoog"


# --- signaaldrempel: normaal bij ≤25% ---

def test_vorig_jaar_signaal_normaal_bij_afwijking_maximaal_25_pct():
    email = _unique_email("vj-normaal")
    _create_user(email)
    token = _token(email)
    batch_id, comp_id = _create_scenario(huidig_wp=120, vorig_wp=100)  # +20%
    vj = _get_detail(batch_id, comp_id, token)["vorig_jaar"]
    assert vj["signaal"] == "normaal"


# --- signaaldrempel: hoog bij >25% daling ---

def test_vorig_jaar_signaal_hoog_bij_daling_groter_dan_25_pct():
    email = _unique_email("vj-hoog-daling")
    _create_user(email)
    token = _token(email)
    batch_id, comp_id = _create_scenario(huidig_wp=60, vorig_wp=100)  # -40%
    vj = _get_detail(batch_id, comp_id, token)["vorig_jaar"]
    assert vj["verschil_abs"] == -40
    assert vj["signaal"] == "hoog"


# --- grenswaarde: exact 25% is normaal ---

def test_vorig_jaar_signaal_normaal_bij_exact_25_pct():
    email = _unique_email("vj-exact-25")
    _create_user(email)
    token = _token(email)
    batch_id, comp_id = _create_scenario(huidig_wp=125, vorig_wp=100)  # exact 25%
    vj = _get_detail(batch_id, comp_id, token)["vorig_jaar"]
    assert vj["signaal"] == "normaal"  # > 0.25, niet >=


# --- geen candidate betekent verschil_abs=None ---

def test_vorig_jaar_zonder_candidate_geeft_geen_verschil():
    email = _unique_email("vj-geen-cand")
    _create_user(email)
    token = _token(email)
    batch_id, comp_id = _create_scenario(huidig_wp=None, vorig_wp=100)
    vj = _get_detail(batch_id, comp_id, token)["vorig_jaar"]
    assert vj["verschil_abs"] is None
    assert vj["signaal"] == "normaal"
