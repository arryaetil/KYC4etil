import io

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import SessionLocal
from app.main import app
from app.models import Batch, Company, User
from app.pipeline.runner import verwerk_company
from app.providers.base import AgentFinding, LocationInfo


client = TestClient(app)


def _headers() -> dict[str, str]:
    email = "csv-fallback@example.test"
    password = "TestWachtwoord2026!"
    db = SessionLocal()
    try:
        if db.query(User).filter_by(email=email).one_or_none() is None:
            db.add(User(naam="CSV Tester", email=email, rol="reviewer",
                        password_hash=hash_password(password)))
            db.commit()
    finally:
        db.close()
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_upload_bewaart_website_en_telefoonnummer():
    csv_data = "naam,website_url,telefoonnummer\nTestbedrijf,https://example.test,043-1234567\n"
    response = client.post(
        "/batches/upload?naam=csv-fallback&jaar=2026",
        files={"file": ("bedrijven.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        headers=_headers(),
    )

    assert response.status_code == 200
    db = SessionLocal()
    try:
        company = db.query(Company).filter_by(naam="Testbedrijf").order_by(Company.created_at.desc()).first()
        assert company.website_url == "https://example.test"
        assert company.telefoonnummer == "043-1234567"
    finally:
        db.close()


class _NoPlacesLookup:
    async def lookup(self, naam, gemeente):
        return None

    async def locations(self, naam, kvk_nummer):
        return LocationInfo(count_nl=None, count_lb=None, bron="csv")


class _WebsiteAgent:
    async def run(self, naam, adres, website_url, gemeente=None):
        assert website_url == "https://example.test"
        return AgentFinding(
            wp_gevonden=8,
            context="Er werken 8 medewerkers.",
            zekerheid="middel",
            reden="csv website fallback",
            bron_url=website_url,
            bron_type="website",
            is_limburg_specifiek=True,
            peilmoment="2026",
        )


class _JaarverslagAgent:
    async def run(self, naam, jaar):
        return None


@pytest.mark.asyncio
async def test_pipeline_gebruikt_csv_website_zonder_google(monkeypatch):
    from app.providers import get_providers
    import app.pipeline.runner as runner

    monkeypatch.setattr(runner, "get_providers", lambda: (_NoPlacesLookup(), _WebsiteAgent(), _JaarverslagAgent()))

    db = SessionLocal()
    try:
        batch = Batch(naam="csv-live-fallback", jaar=2026, totaal=1)
        db.add(batch)
        db.flush()
        company = Company(batch_id=batch.id, naam="Live zonder Google",
                          website_url="https://example.test", telefoonnummer="043-7654321")
        db.add(company)
        db.commit()

        candidate = await verwerk_company(db, company, batch)

        assert candidate.wp_kandidaat == 8
        assert company.enrichment.website_url == "https://example.test"
        assert company.enrichment.telefoonnummer == "043-7654321"
        assert company.enrichment.lookup_failed is False
    finally:
        db.close()
