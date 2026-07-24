"""Autonome bronnenresearch als primaire batchworkflow."""
from app.models import Batch, BronKandidaat, Candidate, Company, ResearchRun


def _batch(db_session) -> tuple[Batch, Company, Company]:
    batch = Batch(naam="vergelijking", jaar=2026, totaal=2)
    db_session.add(batch)
    db_session.flush()
    eerste = Company(batch_id=batch.id, naam="Eerste B.V.", gemeente="Venlo")
    tweede = Company(batch_id=batch.id, naam="Tweede B.V.", gemeente="Heerlen")
    db_session.add_all([eerste, tweede])
    db_session.commit()
    return batch, eerste, tweede


def test_companylijst_toont_laatste_research_en_legacy_vergelijking(
    client, db_session,
):
    batch, company, _ = _batch(db_session)
    legacy = Candidate(
        batch_id=batch.id,
        company_id=company.id,
        wp_kandidaat=100,
        confidence_score=0.8,
        confidence_label="hoog",
    )
    run = ResearchRun(
        batch_id=batch.id,
        company_id=company.id,
        doel="test",
        status="completed",
        resultaat_status="review_nodig",
    )
    db_session.add_all([legacy, run])
    db_session.flush()
    db_session.add(BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url="https://eerste.example/team",
        canonical_url="https://eerste.example/team",
        titel="Ons team",
        brontype="officiele_website",
        wp_gevonden=110,
        eenheid="werkzame_personen",
        scope_class="vestiging",
        ranking_score=0.91,
        status="voorgesteld",
        rang=1,
    ))
    db_session.commit()

    response = client.get(f"/batches/{batch.id}/companies")

    assert response.status_code == 200
    item = next(row for row in response.json() if row["company_id"] == company.id)
    assert item["research_status"] == "completed"
    assert item["research_top_wp"] == 110
    assert item["research_top_score"] == 0.91
    assert item["legacy_wp"] == 100
    assert item["verschil_abs"] == 10
    assert item["vergelijking"] == "afwijkend"


def test_batchstatus_telt_research_reviewwerk(client, db_session):
    batch, eerste, tweede = _batch(db_session)
    runs = [
        ResearchRun(
            batch_id=batch.id,
            company_id=eerste.id,
            doel="test",
            status="completed",
            resultaat_status="review_nodig",
        ),
        ResearchRun(
            batch_id=batch.id,
            company_id=tweede.id,
            doel="test",
            status="error",
            resultaat_status="error",
        ),
    ]
    db_session.add_all(runs)
    db_session.flush()
    db_session.add(BronKandidaat(
        research_run_id=runs[0].id,
        company_id=eerste.id,
        url="https://eerste.example",
        canonical_url="https://eerste.example",
        brontype="officiele_website",
        status="geaccepteerd",
        rang=1,
    ))
    db_session.commit()

    response = client.get(f"/batches/{batch.id}")

    assert response.status_code == 200
    research = response.json()["research"]
    assert research == {
        "gestart": 2,
        "afgerond": 1,
        "review_nodig": 0,
        "geaccepteerd": 1,
        "niet_gevonden": 0,
        "fouten": 1,
    }
