"""Tests voor periodieke jaarverslag-monitoring."""
import asyncio
import asyncio as _asyncio_voor_lock  # alias voorkomt naamsbotsing met bovenstaande `import asyncio`
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import AgentResult, Batch, Candidate, Company, JaarverslagMonitoring
from app.pipeline.monitoring import check_company_jaarverslag


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _maak_company(db, naam: str = "Okechamp B.V.") -> Company:
    batch = Batch(naam="monitoring-test", jaar=2026, totaal=1)
    db.add(batch)
    db.flush()
    company = Company(batch_id=batch.id, naam=naam, vestigingsnummer="111067624")
    db.add(company)
    db.commit()
    return company


def test_jaarverslag_monitoring_rij_aanmaken_en_opvragen():
    db = SessionLocal()
    try:
        company = _maak_company(db)
        status = JaarverslagMonitoring(
            company_id=company.id,
            laatste_bron_url="https://www.okechamp.nl/jaarverslag-2025.pdf",
            laatst_gecontroleerd_op=_now(),
        )
        db.add(status)
        db.commit()

        opgehaald = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one()
        assert opgehaald.laatste_bron_url == "https://www.okechamp.nl/jaarverslag-2025.pdf"
        assert opgehaald.laatst_gecontroleerd_op is not None
    finally:
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_company_jaarverslag_nieuw_gevonden():
    db = SessionLocal()
    try:
        company = _maak_company(db)

        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is True
        ar = db.query(AgentResult).filter_by(company_id=company.id).one()
        assert ar.wp_gevonden == 138
        assert ar.bron_type == "jaarverslag"

        candidate = db.query(Candidate).filter_by(company_id=company.id).one()
        assert candidate.wp_kandidaat == 138

        status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one()
        assert status.laatste_bron_url == "https://www.okechamp.nl/jaarverslag-2025.pdf"
        assert status.laatst_gecontroleerd_op is not None
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_company_jaarverslag_werkt_bestaande_candidate_bij():
    """Een company kan al een candidate hebben (bijv. van een eerdere, volledige
    pipeline-run) — een nieuw gevonden jaarverslag moet die bijwerken, niet dupliceren
    (Candidate heeft een UniqueConstraint op company_id+batch_id)."""
    db = SessionLocal()
    try:
        company = _maak_company(db)
        oude_candidate = Candidate(
            company_id=company.id, batch_id=company.batch_id,
            wp_kandidaat=99, is_schatting=False, confidence_score=0.5,
            confidence_label="middel", status="pending",
        )
        db.add(oude_candidate)
        db.commit()
        oude_candidate_id = oude_candidate.id

        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is True
        candidaten = db.query(Candidate).filter_by(company_id=company.id).all()
        assert len(candidaten) == 1  # bijgewerkt, niet gedupliceerd
        assert candidaten[0].id == oude_candidate_id  # zelfde rij
        assert candidaten[0].wp_kandidaat == 138  # nieuwe waarde uit het jaarverslag
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_company_jaarverslag_geen_wijziging_tweede_keer():
    db = SessionLocal()
    try:
        company = _maak_company(db)

        eerste = asyncio.run(check_company_jaarverslag(db, company, 2026))
        tweede = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert eerste is True
        assert tweede is False
        assert db.query(AgentResult).filter_by(company_id=company.id).count() == 1
        assert db.query(Candidate).filter_by(company_id=company.id).count() == 1
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_batch_jaarverslagen_beperkt_gelijktijdigheid(monkeypatch):
    """Verifieert dat check_batch_jaarverslagen ten hoogste max_concurrent
    organisaties tegelijk verwerkt bij een lijst die groter is dan die limiet."""
    from app.pipeline.monitoring import check_batch_jaarverslagen

    db = SessionLocal()
    try:
        batch = Batch(naam="concurrency-test", jaar=2026, totaal=20)
        db.add(batch)
        db.flush()
        company_ids = []
        for i in range(20):
            company = Company(batch_id=batch.id, naam=f"Bedrijf {i}")
            db.add(company)
            db.flush()
            company_ids.append(company.id)
        db.commit()
        batch_id = batch.id

        actief = 0
        max_actief = 0
        lock = _asyncio_voor_lock.Lock()

        async def fake_check_company_jaarverslag(db_arg, company_arg, jaar_arg):
            nonlocal actief, max_actief
            async with lock:
                actief += 1
                max_actief = max(max_actief, actief)
            await _asyncio_voor_lock.sleep(0.02)
            async with lock:
                actief -= 1
            return False

        monkeypatch.setattr(
            "app.pipeline.monitoring.check_company_jaarverslag",
            fake_check_company_jaarverslag,
        )

        asyncio.run(check_batch_jaarverslagen(batch_id, 2026, company_ids, max_concurrent=8))

        assert max_actief == 8
    finally:
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_batch_jaarverslagen_logt_fout_per_organisatie(monkeypatch):
    """Eén falende organisatie mag de rest van de batch niet blokkeren, en moet
    een eigen PipelineRun-foutregel krijgen."""
    from app.models import PipelineRun
    from app.pipeline.monitoring import check_batch_jaarverslagen

    db = SessionLocal()
    try:
        batch = Batch(naam="foutafhandeling-test", jaar=2026, totaal=2)
        db.add(batch)
        db.flush()
        faalt = Company(batch_id=batch.id, naam="Faalt B.V.")
        slaagt = Company(batch_id=batch.id, naam="Slaagt B.V.")
        db.add(faalt)
        db.add(slaagt)
        db.commit()
        batch_id = batch.id

        async def fake_check_company_jaarverslag(db_arg, company_arg, jaar_arg):
            if company_arg.naam == "Faalt B.V.":
                raise RuntimeError("gesimuleerde netwerkfout")
            return False

        monkeypatch.setattr(
            "app.pipeline.monitoring.check_company_jaarverslag",
            fake_check_company_jaarverslag,
        )

        asyncio.run(check_batch_jaarverslagen(batch_id, 2026, [faalt.id, slaagt.id]))

        fout = db.query(PipelineRun).filter_by(company_id=faalt.id, status="error").one()
        assert "gesimuleerde netwerkfout" in fout.error
        assert db.query(PipelineRun).filter_by(company_id=slaagt.id, status="error").count() == 0
    finally:
        db.query(PipelineRun).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_run_monitoring_watchlist_background_zonder_watchlist_is_stille_noop():
    """Geen batch met is_monitoringlijst=True -> geen fout, gewoon niets doen."""
    from app.pipeline.monitoring import run_monitoring_watchlist_background

    db = SessionLocal()
    try:
        db.query(Batch).filter_by(is_monitoringlijst=True).update({"is_monitoringlijst": False})
        db.commit()

        run_monitoring_watchlist_background()  # mag geen exception opgooien
    finally:
        db.close()
