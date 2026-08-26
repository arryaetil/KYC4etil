"""Weggooien is terug te draaien, en er blijft een spoor van wie wat deed."""
from io import BytesIO

from app.models import Batch, Company, Handeling, User


def _upload(client, db_session, naam="prullenbaklijst"):
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(id="test-user-id", naam="Test User",
                            email="test@etil.nl", rol="admin", password_hash=""))
        db_session.commit()
    response = client.post(
        f"/batches/upload?naam={naam}&jaar=2026",
        files={"file": ("bedrijven.csv", BytesIO(b"naam\nVoorbeeld B.V.\n"), "text/csv")},
    )
    return response.json()["batch_id"]


def test_verwijderen_gooit_weg_maar_wist_niet(client, db_session):
    """In een werkbank zit het werk in de beoordelingen; die mogen niet in één
    klik verdwijnen zonder weg terug."""
    batch_id = _upload(client, db_session)

    response = client.delete(f"/batches/{batch_id}")

    assert response.json() == {"deleted": batch_id, "definitief": False}
    batch = db_session.get(Batch, batch_id)
    assert batch is not None
    assert batch.verwijderd_op is not None
    # De organisaties staan er nog; herstellen brengt alles terug.
    assert db_session.query(Company).filter_by(batch_id=batch_id).count() == 1


def test_een_weggegooide_lijst_staat_niet_meer_in_het_overzicht(client, db_session):
    batch_id = _upload(client, db_session, "verdwijnlijst")
    client.delete(f"/batches/{batch_id}")

    zichtbaar = [b["id"] for b in client.get("/batches").json()]
    in_bak = [b["id"] for b in client.get("/batches?prullenbak=true").json()]

    assert batch_id not in zichtbaar
    assert batch_id in in_bak


def test_herstellen_zet_de_lijst_terug(client, db_session):
    batch_id = _upload(client, db_session, "terughaallijst")
    client.delete(f"/batches/{batch_id}")

    assert client.post(f"/batches/{batch_id}/herstel").status_code == 200

    assert batch_id in [b["id"] for b in client.get("/batches").json()]
    assert db_session.get(Batch, batch_id).verwijderd_op is None


def test_definitief_verwijderen_wist_alles(client, db_session):
    batch_id = _upload(client, db_session, "echtweglijst")

    response = client.delete(f"/batches/{batch_id}?definitief=true")

    assert response.json()["definitief"] is True
    assert db_session.get(Batch, batch_id) is None
    assert db_session.query(Company).filter_by(batch_id=batch_id).count() == 0


def test_er_blijft_een_spoor_van_wie_wat_deed(client, db_session):
    """Wie heeft die lijst geüpload, wie heeft hem weggegooid — daar was geen
    spoor van, en dat merk je pas als iemand het vraagt."""
    batch_id = _upload(client, db_session, "spoorlijst")
    client.delete(f"/batches/{batch_id}")

    soorten = [h.soort for h in db_session.query(Handeling)]
    assert "lijst_geupload" in soorten
    assert "lijst_verwijderd" in soorten
    regel = db_session.query(Handeling).filter_by(soort="lijst_verwijderd").one()
    assert regel.door_naam == "Test User"
    assert "spoorlijst" in regel.omschrijving


def test_de_handelingen_zijn_voor_een_beheerder_te_lezen(client, db_session):
    _upload(client, db_session, "leeslijst")

    items = client.get("/auth/handelingen").json()["items"]

    assert items
    assert items[0]["door"] == "Test User"
    assert "leeslijst" in items[0]["omschrijving"]
