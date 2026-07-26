import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Batch, Company, ResearchRun
import app.models  # noqa: F401


@pytest.mark.asyncio
async def test_researchrun_gebruikt_centrale_timeout(monkeypatch):
    from app.research import service

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", sessions)
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(research_company_timeout_seconds=0.01),
    )

    with sessions() as db:
        batch = Batch(naam="timeout", jaar=2026, status="running", totaal=1)
        db.add(batch)
        db.flush()
        company = Company(batch_id=batch.id, naam="Trage organisatie")
        db.add(company)
        db.flush()
        run = ResearchRun(
            company_id=company.id,
            batch_id=batch.id,
            doel="timeouttest",
            status="pending",
        )
        db.add(run)
        db.commit()
        run_id = run.id

    async def trage_run(_run_id):
        await asyncio.sleep(1)

    monkeypatch.setattr(service, "_run_research_run", trage_run)

    await service.run_research_run(run_id)

    with sessions() as db:
        run = db.get(ResearchRun, run_id)
        assert run.status == "error"
        assert run.resultaat_status == "error"
        assert run.fout == "onderzoek afgebroken na 0.01 seconden"
        assert run.completed_at is not None

    Base.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_batch_hervat_na_afgeronde_organisatie_en_stale_run(monkeypatch):
    from app.research import service

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", sessions)

    with sessions() as db:
        batch = Batch(naam="hervatten", jaar=2026, status="error", totaal=3)
        db.add(batch)
        db.flush()
        companies = [
            Company(batch_id=batch.id, naam=f"Organisatie {nummer}")
            for nummer in range(3)
        ]
        db.add_all(companies)
        db.flush()
        db.add(ResearchRun(
            company_id=companies[0].id, batch_id=batch.id,
            doel="test", status="completed",
        ))
        stale = ResearchRun(
            company_id=companies[1].id, batch_id=batch.id,
            doel="test", status="running",
        )
        db.add(stale)
        db.commit()
        batch_id = batch.id
        stale_id = stale.id

    uitgevoerde_runs = []

    async def rond_run_af(run_id):
        uitgevoerde_runs.append(run_id)
        with sessions() as db:
            run = db.get(ResearchRun, run_id)
            run.status = "completed"
            db.commit()

    monkeypatch.setattr(service, "run_research_run", rond_run_af)

    await service.run_research_batch(batch_id)

    with sessions() as db:
        batch = db.get(Batch, batch_id)
        stale = db.get(ResearchRun, stale_id)
        assert batch.status == "review"
        assert batch.verwerkt == 3
        assert stale.status == "error"
        assert stale.fout == "onderbroken proces; opnieuw ingepland"
        assert len(uitgevoerde_runs) == 2

    Base.metadata.drop_all(engine)
