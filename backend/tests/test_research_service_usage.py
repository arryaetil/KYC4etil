"""Kostentracking wordt na een researchrun weggeschreven op ResearchRun."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Batch, Company, ResearchRun
import app.models  # noqa: F401 — zorgt dat alle modellen geregistreerd zijn


@pytest.fixture
def geisoleerde_sessionmaker():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_run_research_run_vult_tokentracking(
    monkeypatch, geisoleerde_sessionmaker,
):
    from app.research import service

    monkeypatch.setattr(service, "SessionLocal", geisoleerde_sessionmaker)

    with geisoleerde_sessionmaker() as db:
        batch = Batch(naam="usage-test", jaar=2026, totaal=1)
        db.add(batch)
        db.flush()
        company = Company(
            batch_id=batch.id, naam="Voorbeeld Zorg",
            vestigingsnummer="USAGE-1",
        )
        db.add(company)
        db.flush()
        run = ResearchRun(
            company_id=company.id, batch_id=batch.id,
            doel="test", status="pending",
        )
        db.add(run)
        db.commit()
        run_id = run.id

    monkeypatch.setattr(
        service.get_settings(), "provider_mode", "mock",
    )

    kosten = {
        "currency": "USD",
        "tokens_in": 321,
        "tokens_out": 45,
        "providers": {
            "openai_tokens": {"calls": 1, "kosten_usd": 0.000075},
            "serper_search": {"calls": 2, "kosten_usd": 0.002},
        },
        "totaal_usd": 0.002075,
        "totaal_cents": 0,
    }
    monkeypatch.setattr(service, "get_usage_totals", lambda: (321, 45))
    monkeypatch.setattr(service, "get_cost_summary", lambda: kosten)

    await service.run_research_run(run_id)

    with geisoleerde_sessionmaker() as db:
        opgeslagen = db.get(ResearchRun, run_id)
        assert opgeslagen.status == "completed"
        assert opgeslagen.tokens_in == 321
        assert opgeslagen.tokens_out == 45
        assert opgeslagen.kosten_cents == 0
        assert opgeslagen.configuratie["kosten"] == kosten
