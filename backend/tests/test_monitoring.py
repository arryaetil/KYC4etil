"""Tests voor periodieke jaarverslag-monitoring."""
import asyncio
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
