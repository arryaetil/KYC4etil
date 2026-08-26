"""Een vrije opmerking van een reviewer, naast de vaste keuzelijsten."""
from app.models import Batch, Company, Opmerking, User


def _company(db_session) -> Company:
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(id="test-user-id", naam="Test User",
                            email="test@etil.nl", rol="admin", password_hash=""))
    batch = Batch(naam="opmerkingen", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Voorbeeld Zorg")
    db_session.add(company)
    db_session.commit()
    return company


def test_een_opmerking_wordt_vastgelegd_met_schrijver(client, db_session):
    company = _company(db_session)

    response = client.post(
        f"/research/companies/{company.id}/opmerkingen",
        json={"tekst": "Deze vestiging is vorig jaar gefuseerd met Zorggroep Noord."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tekst"].startswith("Deze vestiging is vorig jaar gefuseerd")
    assert data["geschreven_door"] == "Test User"
    assert data["created_at"].endswith("Z")


def test_opmerkingen_komen_nieuwste_eerst(client, db_session):
    company = _company(db_session)
    for tekst in ("eerste", "tweede", "derde"):
        client.post(
            f"/research/companies/{company.id}/opmerkingen", json={"tekst": tekst},
        )

    items = client.get(f"/research/companies/{company.id}/opmerkingen").json()["items"]

    assert [item["tekst"] for item in items] == ["derde", "tweede", "eerste"]


def test_een_lege_opmerking_wordt_geweigerd(client, db_session):
    company = _company(db_session)
    response = client.post(
        f"/research/companies/{company.id}/opmerkingen", json={"tekst": " "},
    )
    assert response.status_code == 422


def test_opmerking_bij_een_onbekende_organisatie_geeft_404(client, db_session):
    _company(db_session)
    response = client.post(
        "/research/companies/bestaat-niet/opmerkingen", json={"tekst": "iets"},
    )
    assert response.status_code == 404


def test_je_verwijdert_alleen_je_eigen_opmerking(client, db_session):
    """Die van een collega is bewijs van wat zij zag."""
    company = _company(db_session)
    eigen = client.post(
        f"/research/companies/{company.id}/opmerkingen", json={"tekst": "van mij"},
    ).json()
    db_session.add(User(id="collega", naam="Anita", email="anita@etil.nl",
                        rol="reviewer", password_hash=""))
    db_session.flush()
    db_session.add(Opmerking(
        id="van-anita", company_id=company.id, geschreven_door="collega",
        tekst="van Anita",
    ))
    db_session.commit()

    assert client.delete(f"/research/opmerkingen/{eigen['id']}").status_code == 200
    assert client.delete("/research/opmerkingen/van-anita").status_code == 403
    assert db_session.get(Opmerking, "van-anita") is not None
