from pathlib import Path

from app.models import Batch, Company, JaarverslagMonitoring, JaarverslagUpload, VastgoedRecord
from scripts.seed_monitoringlijst import lees_monitoringlijst, seed_monitoringlijst


def test_lees_monitoringlijst_met_url_kolom(tmp_path: Path):
    pad = tmp_path / "monitoring.csv"
    pad.write_text(
        "naam,cb_er,jaarverslag_url\n"
        "Testbedrijf,001,http://example.test/jaarverslag.pdf\n",
        encoding="utf-8",
    )

    rijen = lees_monitoringlijst(pad)

    assert rijen == [{
        "naam": "Testbedrijf",
        "cb_er": "001",
        "jaarverslag_url": "http://example.test/jaarverslag.pdf",
    }]


def test_seed_monitoringlijst_vervangt_actieve_watchlist_en_zet_url_baseline(db_session):
    oude_batch = Batch(naam="oude watchlist", jaar=2025, totaal=1, is_monitoringlijst=True)
    db_session.add(oude_batch)
    db_session.flush()
    oude_company = Company(batch_id=oude_batch.id, naam="Oud bedrijf")
    db_session.add(oude_company)
    db_session.flush()
    db_session.add(JaarverslagMonitoring(
        company_id=oude_company.id,
        laatste_bron_url="https://oude.example/jaarverslag.pdf",
    ))
    db_session.commit()

    resultaat = seed_monitoringlijst(db_session, [
        {
            "naam": "Nieuw bedrijf",
            "cb_er": "000001",
            "jaarverslag_url": "https://nieuw.example/jaarverslag.pdf",
        },
        {"naam": "Zonder URL", "cb_er": None, "jaarverslag_url": None},
    ], jaar=2026)

    assert resultaat["totaal"] == 2
    assert resultaat["urls_gevuld"] == 1
    assert db_session.query(Batch).filter_by(is_monitoringlijst=True).count() == 1
    assert db_session.query(Company).filter_by(naam="Oud bedrijf").count() == 0

    batch = db_session.get(Batch, resultaat["batch_id"])
    assert batch.naam == "Jaarverslag-monitoringlijst"
    assert batch.totaal == 2

    nieuw = db_session.query(Company).filter_by(naam="Nieuw bedrijf").one()
    status = db_session.query(JaarverslagMonitoring).filter_by(company_id=nieuw.id).one()
    assert status.laatste_bron_url == "https://nieuw.example/jaarverslag.pdf"


def test_seed_monitoringlijst_ruimt_ook_vastgoed_en_jaarverslag_uploads_op(db_session):
    oude_batch = Batch(naam="oude watchlist", jaar=2025, totaal=1, is_monitoringlijst=True)
    db_session.add(oude_batch)
    db_session.flush()
    oude_company = Company(batch_id=oude_batch.id, naam="Oud bedrijf")
    db_session.add(oude_company)
    db_session.flush()
    db_session.add(VastgoedRecord(company_id=oude_company.id, bron="handmatig"))
    db_session.add(JaarverslagUpload(
        company_id=oude_company.id,
        bestandsnaam="oud.pdf",
        pdf_tekst="oud",
        jaar=2024,
    ))
    db_session.commit()

    resultaat = seed_monitoringlijst(db_session, [
        {"naam": "Nieuw bedrijf", "cb_er": "000001", "jaarverslag_url": None},
    ], jaar=2026)

    assert resultaat["totaal"] == 1
    assert db_session.query(VastgoedRecord).filter_by(company_id=oude_company.id).count() == 0
    assert db_session.query(JaarverslagUpload).filter_by(company_id=oude_company.id).count() == 0
