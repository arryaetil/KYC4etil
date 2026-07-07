"""Tests voor periodieke jaarverslag-monitoring."""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import Batch, Company, JaarverslagMonitoring


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
