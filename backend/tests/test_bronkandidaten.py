"""Datamodeltests voor autonome bronnenresearch."""
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Batch, BronKandidaat, Company, ResearchRun


def _maak_company(db_session) -> Company:
    batch = Batch(naam="bronnenresearch-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(
        batch_id=batch.id,
        naam="Voorbeeld Zorg",
        vestigingsnummer="BRON-001",
        website_url="https://voorbeeldzorg.nl",
    )
    db_session.add(company)
    db_session.commit()
    return company


def test_researchrun_met_meerdere_uniforme_bronkandidaten(db_session):
    company = _maak_company(db_session)
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="actuele WP-bronnen vinden",
        gevraagd_jaar=2025,
        status="running",
        resultaat_status="review_nodig",
        configuratie={"media_venster_maanden": 18},
    )
    db_session.add(run)
    db_session.flush()

    website = BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url="https://voorbeeldzorg.nl/over-ons?utm_source=test",
        canonical_url="https://voorbeeldzorg.nl/over-ons",
        titel="Over ons",
        brontype="officiele_website",
        documenttype="teampagina",
        publicatiedatum=date(2026, 5, 14),
        informatie_peilmoment="2026-05",
        wp_gevonden=47,
        eenheid="werkzame_personen",
        bewijsfragment="Ons team bestaat uit 47 medewerkers.",
        identity_class="exact_entity",
        scope_class="concern",
        autoriteit_score=0.95,
        actualiteit_score=0.90,
        identiteit_score=1.0,
        relevantie_score=0.93,
        ranking_score=0.94,
        validaties={"officieel_domein": True},
        waarschuwingen=[],
        status="voorgesteld",
        rang=1,
    )
    media = BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url="https://nieuws.example/voorbeeld-zorg-groeit",
        canonical_url="https://nieuws.example/voorbeeld-zorg-groeit",
        titel="Voorbeeld Zorg groeit",
        brontype="media",
        documenttype="nieuwsartikel",
        publicatiedatum=date(2026, 6, 2),
        informatie_peilmoment="2026-06",
        wp_gevonden=50,
        eenheid="werkzame_personen",
        bewijsfragment="De organisatie telt inmiddels circa 50 medewerkers.",
        identity_class="exact_entity",
        scope_class="concern",
        ranking_score=0.72,
        validaties={"recente_media": True},
        waarschuwingen=["benadering"],
        status="voorgesteld",
        rang=2,
    )
    db_session.add_all([website, media])
    db_session.commit()

    opgeslagen = (
        db_session.query(BronKandidaat)
        .filter_by(research_run_id=run.id)
        .order_by(BronKandidaat.rang)
        .all()
    )
    assert len(opgeslagen) == 2
    assert opgeslagen[0].validaties == {"officieel_domein": True}
    assert opgeslagen[1].waarschuwingen == ["benadering"]
    assert opgeslagen[0].publicatiedatum == date(2026, 5, 14)
    assert opgeslagen[0].informatie_peilmoment == "2026-05"


def test_canonical_url_is_uniek_binnen_een_researchrun(db_session):
    company = _maak_company(db_session)
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="deduplicatie testen",
        status="running",
    )
    db_session.add(run)
    db_session.flush()
    db_session.add_all([
        BronKandidaat(
            research_run_id=run.id,
            company_id=company.id,
            url="https://voorbeeldzorg.nl/team?utm_source=a",
            canonical_url="https://voorbeeldzorg.nl/team",
            brontype="officiele_website",
            status="voorgesteld",
        ),
        BronKandidaat(
            research_run_id=run.id,
            company_id=company.id,
            url="https://voorbeeldzorg.nl/team?utm_source=b",
            canonical_url="https://voorbeeldzorg.nl/team",
            brontype="officiele_website",
            status="voorgesteld",
        ),
    ])

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
