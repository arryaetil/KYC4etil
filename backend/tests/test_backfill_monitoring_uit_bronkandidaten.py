"""Tests voor het eenmalige backfill-script van monitoringbronnen.

De kern van dit script is wat het níet doet: koppelen op naam. Gemeten op
productie levert een naam-match bij "Stichting Pergamijn" een kandidaat op met
2.400 WP die naar een Zorgboog-jaarverantwoording op een ander domein wijst.
"""
from app.database import SessionLocal
from app.models import (
    Batch, BronKandidaat, Company, JaarverslagMonitoring, ResearchRun,
)
from app.research.urls import canonicaliseer_url
from scripts.backfill_monitoring_uit_bronkandidaten import _zoek_voorstellen


def _kandidaat(db, company_id, url, *, verslagjaar, status="voorgesteld",
               brontype="jaarverslag", wp=None):
    run = ResearchRun(
        company_id=company_id,
        batch_id=db.get(Company, company_id).batch_id,
        doel="test", status="completed",
    )
    db.add(run)
    db.flush()
    db.add(BronKandidaat(
        research_run_id=run.id, company_id=company_id, url=url,
        canonical_url=canonicaliseer_url(url), titel="Jaarverslag",
        brontype=brontype, documenttype="jaarverslag",
        verslagjaar=verslagjaar, wp_gevonden=wp, status=status, rang=1,
    ))


def test_koppelt_alleen_op_bevestigd_websitedomein():
    """Domein bepaalt de identiteit; naamgelijkenis mag dat nooit doen.

    De 'Zorgboog'-kandidaat staat op naam van dezelfde organisatie maar op een
    ander domein. Zonder de domeineis zou die als monitoringbron worden
    vastgelegd, inclusief zijn WP-getal — een cross-company mismatch.
    """
    db = SessionLocal()
    try:
        watchlist = Batch(naam="wl", jaar=2026, is_monitoringlijst=True)
        onderzoek = Batch(naam="batchrun", jaar=2026)
        db.add_all([watchlist, onderzoek])
        db.flush()

        doel = Company(batch_id=watchlist.id, naam="Stichting Pergamijn",
                       website_url="https://www.pergamijn.org")
        elders = Company(batch_id=onderzoek.id, naam="Stichting Pergamijn",
                         website_url="https://www.pergamijn.org")
        db.add_all([doel, elders])
        db.flush()

        _kandidaat(db, elders.id,
                   "https://www.pergamijn.org/wp-content/uploads/jaarverslag-2025.pdf",
                   verslagjaar=2025)
        _kandidaat(db, elders.id,
                   "https://www.zorgboog.nl/wp-content/uploads/Jaarverantwoording-Zorgboog-2023.pdf",
                   verslagjaar=2025, wp=2400)
        db.commit()

        voorstellen = _zoek_voorstellen(db, watchlist)

        assert len(voorstellen) == 1
        assert voorstellen[0].company.id == doel.id
        assert "pergamijn.org" in voorstellen[0].kandidaat.url
        assert "zorgboog" not in voorstellen[0].kandidaat.url
    finally:
        db.query(BronKandidaat).delete()
        db.query(ResearchRun).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_slaat_organisaties_met_een_bron_en_afgewezen_kandidaten_over():
    db = SessionLocal()
    try:
        watchlist = Batch(naam="wl2", jaar=2026, is_monitoringlijst=True)
        onderzoek = Batch(naam="batchrun2", jaar=2026)
        db.add_all([watchlist, onderzoek])
        db.flush()

        heeft_al = Company(batch_id=watchlist.id, naam="Heeft Al",
                           website_url="https://heeftal.test")
        afgewezen = Company(batch_id=watchlist.id, naam="Afgewezen Bron",
                            website_url="https://afgewezen.test")
        db.add_all([heeft_al, afgewezen])
        db.flush()
        db.add(JaarverslagMonitoring(
            company_id=heeft_al.id,
            laatste_bron_url="https://heeftal.test/jaarverslag-2024.pdf",
            laatste_verslagjaar=2024,
        ))

        for company, url, status in (
            (heeft_al, "https://heeftal.test/jaarverslag-2025.pdf", "voorgesteld"),
            (afgewezen, "https://afgewezen.test/jaarverslag-2025.pdf", "afgewezen"),
        ):
            elders = Company(batch_id=onderzoek.id, naam=company.naam,
                             website_url=company.website_url)
            db.add(elders)
            db.flush()
            _kandidaat(db, elders.id, url, verslagjaar=2025, status=status)
        db.commit()

        assert _zoek_voorstellen(db, watchlist) == []
    finally:
        db.query(BronKandidaat).delete()
        db.query(ResearchRun).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_kiest_het_hoogste_verslagjaar_op_het_domein():
    db = SessionLocal()
    try:
        watchlist = Batch(naam="wl3", jaar=2026, is_monitoringlijst=True)
        onderzoek = Batch(naam="batchrun3", jaar=2026)
        db.add_all([watchlist, onderzoek])
        db.flush()
        doel = Company(batch_id=watchlist.id, naam="Gilde",
                       website_url="https://www.gilde.test")
        elders = Company(batch_id=onderzoek.id, naam="Gilde",
                         website_url="https://www.gilde.test")
        db.add_all([doel, elders])
        db.flush()
        _kandidaat(db, elders.id, "https://www.gilde.test/jv-2019.pdf",
                   verslagjaar=2019)
        _kandidaat(db, elders.id, "https://www.gilde.test/jv-2024.pdf",
                   verslagjaar=2024)
        _kandidaat(db, elders.id, "https://www.gilde.test/overzicht",
                   verslagjaar=None)
        db.commit()

        voorstellen = _zoek_voorstellen(db, watchlist)

        assert len(voorstellen) == 1
        assert voorstellen[0].kandidaat.verslagjaar == 2024
    finally:
        db.query(BronKandidaat).delete()
        db.query(ResearchRun).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()
