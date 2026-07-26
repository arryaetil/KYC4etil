"""Human-in-the-loop API voor bronkandidaten."""
from app.models import Batch, BronKandidaat, Company, ResearchRun, User


def _maak_company(db_session) -> Company:
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(
            id="test-user-id",
            naam="Test User",
            email="test@etil.nl",
            rol="admin",
            password_hash="",
        ))
    batch = Batch(naam="research-api", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(
        batch_id=batch.id,
        naam="Voorbeeld Zorg",
        vestigingsnummer="RESEARCH-API-1",
        website_url="https://voorbeeldzorg.nl",
    )
    db_session.add(company)
    db_session.commit()
    return company


def test_start_research_maakt_run_en_plant_achtergrondtaak(
    client, db_session, monkeypatch,
):
    company = _maak_company(db_session)
    aangeroepen: list[str] = []

    async def fake_run_research_run(run_id: str):
        aangeroepen.append(run_id)

    monkeypatch.setattr(
        "app.routers.research.run_research_run", fake_run_research_run,
    )

    response = client.post(
        f"/research/companies/{company.id}/run",
        json={"gevraagd_jaar": 2025},
    )

    assert response.status_code == 202
    data = response.json()
    run = db_session.get(ResearchRun, data["run_id"])
    assert run is not None
    assert run.gevraagd_jaar == 2025
    assert run.status == "pending"
    assert aangeroepen == [run.id]


def test_reviewer_kan_een_primaire_bron_per_run_accepteren(client, db_session):
    company = _maak_company(db_session)
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="bronreview",
        status="completed",
        resultaat_status="review_nodig",
    )
    db_session.add(run)
    db_session.flush()
    eerste = BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url="https://voorbeeldzorg.nl/team",
        canonical_url="https://voorbeeldzorg.nl/team",
        brontype="officiele_website",
        status="voorgesteld",
        rang=1,
    )
    tweede = BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url="https://nieuws.example/voorbeeld",
        canonical_url="https://nieuws.example/voorbeeld",
        brontype="media",
        status="voorgesteld",
        rang=2,
    )
    db_session.add_all([eerste, tweede])
    db_session.commit()

    response = client.post(
        f"/research/candidates/{eerste.id}/review",
        json={"beslissing": "accepteren", "reden": "officiële bron"},
    )
    assert response.status_code == 200

    response = client.post(
        f"/research/candidates/{tweede.id}/review",
        json={"beslissing": "accepteren", "reden": "actueler"},
    )
    assert response.status_code == 200

    db_session.refresh(eerste)
    db_session.refresh(tweede)
    assert eerste.status == "alternatief"
    assert tweede.status == "geaccepteerd"
    assert tweede.reviewed_by == "test-user-id"
    assert tweede.review_reason == "actueler"


def test_handmatige_bron_wordt_als_reviewerinput_bewaard(client, db_session):
    company = _maak_company(db_session)

    response = client.post(
        f"/research/companies/{company.id}/manual-source",
        json={
            "url": "https://voorbeeldzorg.nl/nieuws/ons-team",
            "titel": "Ons team",
            "reden": "door reviewer gevonden",
        },
    )

    assert response.status_code == 201
    kandidaat = db_session.get(BronKandidaat, response.json()["candidate_id"])
    assert kandidaat is not None
    assert kandidaat.brontype == "handmatig"
    assert kandidaat.status == "geaccepteerd"
    assert kandidaat.reviewed_by == "test-user-id"


def test_run_api_toont_onderzoeksdiagnostiek(client, db_session):
    company = _maak_company(db_session)
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="diagnostiek",
        status="completed",
        resultaat_status="niet_gevonden",
        configuratie={
            "diagnostiek": {
                "onderzochte_paginas": 12,
                "afgewezen_documenten": 8,
            },
        },
    )
    db_session.add(run)
    db_session.commit()

    response = client.get(f"/research/runs/{run.id}")

    assert response.status_code == 200
    assert response.json()["diagnostiek"]["onderzochte_paginas"] == 12


def test_api_markeert_een_bron_die_bij_meerdere_vestigingen_terugkomt(
    client, db_session,
):
    eerste = _maak_company(db_session)
    tweede = Company(
        batch_id=eerste.batch_id,
        naam="Voorbeeld Zorglocatie Twee",
        vestigingsnummer="RESEARCH-API-2",
    )
    db_session.add(tweede)
    db_session.flush()
    runs = [
        ResearchRun(
            company_id=company.id,
            batch_id=company.batch_id,
            doel="gedeelde bron",
            status="completed",
            resultaat_status="review_nodig",
        )
        for company in (eerste, tweede)
    ]
    db_session.add_all(runs)
    db_session.flush()
    for run, company in zip(runs, (eerste, tweede)):
        db_session.add(BronKandidaat(
            research_run_id=run.id,
            company_id=company.id,
            url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
            canonical_url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
            brontype="jaarverslag",
            status="voorgesteld",
            rang=1,
        ))
    db_session.commit()

    response = client.get(f"/research/companies/{eerste.id}/candidates")

    assert response.status_code == 200
    assert response.json()["items"][0]["gedeeld_met_vestigingen"] == 2
