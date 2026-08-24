"""Tests voor de is_monitoringlijst-vlag op Batch en de upload-ondersteuning ervoor."""
from io import BytesIO

from app.models import Batch, User


def _zorg_voor_test_user(db_session):
    """Uploads koppelen geupload_door (FK naar users.id) aan de ingelogde
    testgebruiker; die rij bestaat niet automatisch in de testdatabase."""
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(id="test-user-id", naam="Test User", email="test@etil.nl",
                            rol="admin", password_hash=""))
        db_session.commit()


def _upload(client, naam: str, monitoringlijst: bool = False):
    params = f"naam={naam}&jaar=2026"
    if monitoringlijst:
        params += "&monitoringlijst=true"
    return client.post(
        f"/batches/upload?{params}",
        files={"file": ("bedrijven.csv", BytesIO(b"naam\nTestbedrijf B.V.\n"), "text/csv")},
    )


def test_upload_met_monitoringlijst_true_zet_de_vlag(client, db_session):
    _zorg_voor_test_user(db_session)
    response = _upload(client, "watchlist-test", monitoringlijst=True)

    assert response.status_code == 200
    batch_id = response.json()["batch_id"]
    batch = db_session.get(Batch, batch_id)
    assert batch.is_monitoringlijst is True


def test_upload_zonder_monitoringlijst_laat_vlag_op_false(client, db_session):
    _zorg_voor_test_user(db_session)
    response = _upload(client, "gewone-batch")

    assert response.status_code == 200
    batch = db_session.get(Batch, response.json()["batch_id"])
    assert batch.is_monitoringlijst is False


def test_tweede_monitoringlijst_vult_de_lopende_aan(client, db_session):
    """Een watchlist loopt door; een nieuw bestand vervangt hem niet.

    De vorige versie ontmarkeerde de oude lijst, waardoor die stil zijn vlag
    kwijtraakte en alle controlegeschiedenis uit beeld verdween. Aanvullen is
    wat je wilt: nieuwe organisaties erbij, bestaande met rust gelaten.
    """
    _zorg_voor_test_user(db_session)
    eerste = _upload(client, "watchlist-v1", monitoringlijst=True)
    tweede = client.post(
        "/batches/upload?naam=watchlist-v2&jaar=2026&monitoringlijst=true",
        files={"file": ("bedrijven.csv", BytesIO(
            b"naam,gemeente\nTestbedrijf B.V.,\nTweede Organisatie,Venlo\n"
        ), "text/csv")},
    )

    assert tweede.json()["batch_id"] == eerste.json()["batch_id"]
    assert tweede.json()["samengevoegd"] is True
    assert tweede.json()["toegevoegd"] == 1
    assert tweede.json()["ongewijzigd"] == 1

    watchlists = db_session.query(Batch).filter_by(is_monitoringlijst=True).all()
    assert len(watchlists) == 1
    assert watchlists[0].totaal == 2


def test_monitoringlijst_batch_verschijnt_niet_in_hoofdoverzicht(client, db_session):
    _zorg_voor_test_user(db_session)
    _upload(client, "gewone-batch")
    _upload(client, "watchlist-test", monitoringlijst=True)

    namen = [b["naam"] for b in client.get("/batches").json()]

    assert "gewone-batch" in namen
    assert "watchlist-test" not in namen


def test_legacy_monitorlijst_naam_verschijnt_niet_in_hoofdoverzicht(client, db_session):
    db_session.add(Batch(naam="Jaarverslagen monitorlijst", jaar=2026, totaal=1,
                         is_monitoringlijst=False))
    db_session.add(Batch(naam="gewone-batch", jaar=2026, totaal=1,
                         is_monitoringlijst=False))
    db_session.commit()

    namen = [b["naam"] for b in client.get("/batches").json()]

    assert "gewone-batch" in namen
    assert "Jaarverslagen monitorlijst" not in namen
