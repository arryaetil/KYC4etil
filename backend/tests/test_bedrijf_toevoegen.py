"""Aanvullen in plaats van dupliceren, bij upload én bij handmatig toevoegen."""
from io import BytesIO

from app.models import Batch, Company, User


def _user(db_session):
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(id="test-user-id", naam="Test User",
                            email="test@etil.nl", rol="admin", password_hash=""))
        db_session.commit()


def _lijst(client, db_session, csv: bytes) -> str:
    _user(db_session)
    response = client.post(
        "/batches/upload?naam=lijst&jaar=2026",
        files={"file": ("bedrijven.csv", BytesIO(csv), "text/csv")},
    )
    return response.json()["batch_id"]


def test_handmatig_toevoegen_maakt_een_organisatie_aan(client, db_session):
    batch_id = _lijst(client, db_session, b"naam\nBestaand B.V.\n")

    response = client.post(
        f"/batches/{batch_id}/companies",
        json={"naam": "Nieuwe Zorggroep", "gemeente": "Venlo",
              "kvk_nummer": "12345678"},
    )

    assert response.status_code == 200
    assert response.json()["bestond_al"] is False
    company = db_session.query(Company).filter_by(naam="Nieuwe Zorggroep").one()
    assert company.batch_id == batch_id
    assert company.gemeente == "Venlo"
    assert db_session.get(Batch, batch_id).totaal == 2


def test_twee_keer_toevoegen_levert_geen_dubbele_rij(client, db_session):
    """Anders wordt dezelfde vestiging twee keer onderzocht en twee keer beoordeeld."""
    batch_id = _lijst(client, db_session, b"naam\nBestaand B.V.\n")
    payload = {"naam": "Dubbele B.V.", "gemeente": "Roermond"}

    client.post(f"/batches/{batch_id}/companies", json=payload)
    tweede = client.post(f"/batches/{batch_id}/companies", json=payload)

    assert tweede.json()["bestond_al"] is True
    assert db_session.query(Company).filter_by(naam="Dubbele B.V.").count() == 1


def test_toevoegen_vult_een_leeg_veld_aan_maar_overschrijft_niets(client, db_session):
    """Wat er staat kan met de hand zijn gecorrigeerd; een nieuwe aanlevering
    is niet vanzelf beter. Wat ontbreekt aanvullen is winst zonder risico."""
    batch_id = _lijst(
        client, db_session,
        b"naam,vestigingsnummer,gemeente\nZorggroep,V001,Sittard-Geleen\n",
    )

    client.post(f"/batches/{batch_id}/companies", json={
        "naam": "Zorggroep", "vestigingsnummer": "V001",
        "gemeente": "Venlo", "website_url": "https://zorggroep.nl",
    })

    company = db_session.query(Company).filter_by(vestigingsnummer="V001").one()
    assert company.gemeente == "Sittard-Geleen"
    assert company.website_url == "https://zorggroep.nl"


def test_dezelfde_naam_in_een_andere_gemeente_is_een_andere_vestiging(client, db_session):
    """Zonder vestigingsnummer is naam alléén te weinig: "Jumbo Supermarkten"
    bestaat in tientallen gemeenten."""
    batch_id = _lijst(client, db_session, b"naam,gemeente\nJumbo,Venlo\n")

    client.post(f"/batches/{batch_id}/companies",
                json={"naam": "Jumbo", "gemeente": "Roermond"})

    assert db_session.query(Company).filter_by(naam="Jumbo").count() == 2


def test_toevoegen_aan_een_onbekende_lijst_geeft_404(client, db_session):
    _user(db_session)
    response = client.post("/batches/bestaat-niet/companies", json={"naam": "X B.V."})
    assert response.status_code == 404
