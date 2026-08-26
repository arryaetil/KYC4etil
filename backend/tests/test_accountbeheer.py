"""Wachtwoord wijzigen en gebruikers beheren."""
from app.auth import hash_password, verify_password
from app.models import User


def _gebruiker(db_session, id: str, rol: str, wachtwoord: str = "startwachtwoord") -> User:
    # De conftest zet één vaste ingelogde gebruiker klaar; die moet dezelfde
    # hash dragen als de rij in de database, anders test je twee objecten.
    from tests.conftest import _TEST_USER

    if id == _TEST_USER.id:
        _TEST_USER.rol = rol
        _TEST_USER.password_hash = hash_password(wachtwoord)
    bestaand = db_session.get(User, id)
    if bestaand:
        bestaand.rol = rol
        bestaand.password_hash = hash_password(wachtwoord)
        db_session.commit()
        return bestaand
    gebruiker = User(
        id=id, naam=id.title(), email=f"{id}@etil.nl", rol=rol,
        password_hash=hash_password(wachtwoord),
    )
    db_session.add(gebruiker)
    db_session.commit()
    return gebruiker


def test_eigen_wachtwoord_wijzigen(client, db_session):
    from tests.conftest import _TEST_USER

    _gebruiker(db_session, "test-user-id", "admin")

    response = client.post("/auth/wachtwoord", json={
        "huidig": "startwachtwoord", "nieuw": "een lang nieuw wachtwoord",
    })

    assert response.status_code == 200
    assert verify_password("een lang nieuw wachtwoord", _TEST_USER.password_hash)


def test_zonder_het_huidige_wachtwoord_lukt_het_niet(client, db_session):
    """Anders neemt iedereen die even achter een open laptop kruipt het over."""
    _gebruiker(db_session, "test-user-id", "admin")

    response = client.post("/auth/wachtwoord", json={
        "huidig": "iets anders", "nieuw": "een lang nieuw wachtwoord",
    })

    assert response.status_code == 403


def test_een_te_kort_wachtwoord_wordt_geweigerd(client, db_session):
    _gebruiker(db_session, "test-user-id", "admin")
    response = client.post("/auth/wachtwoord", json={
        "huidig": "startwachtwoord", "nieuw": "kort",
    })
    assert response.status_code == 422


def test_beheerder_maakt_een_gebruiker_aan(client, db_session):
    """Tot nu toe kon dat alleen met een script en een deploy."""
    _gebruiker(db_session, "test-user-id", "admin")

    response = client.post("/auth/users", json={
        "naam": "Anita", "email": "Anita@Etil.nl", "rol": "reviewer",
        "wachtwoord": "een lang wachtwoord",
    })

    assert response.status_code == 200
    assert response.json()["email"] == "anita@etil.nl"
    nieuw = db_session.query(User).filter(User.email == "anita@etil.nl").one()
    assert verify_password("een lang wachtwoord", nieuw.password_hash)


def test_hetzelfde_adres_kan_niet_twee_keer(client, db_session):
    _gebruiker(db_session, "test-user-id", "admin")
    payload = {"naam": "Anita", "email": "anita@etil.nl", "rol": "reviewer",
               "wachtwoord": "een lang wachtwoord"}

    assert client.post("/auth/users", json=payload).status_code == 200
    assert client.post("/auth/users", json=payload).status_code == 409


def test_een_reviewer_mag_geen_gebruikers_beheren(client, db_session):
    """De rol stond al in het token maar werd nergens gecontroleerd."""
    from tests.conftest import _TEST_USER

    _gebruiker(db_session, "test-user-id", "reviewer")
    try:
        assert client.get("/auth/users").status_code == 403
        assert client.post("/auth/users", json={
            "naam": "X", "email": "x@etil.nl", "rol": "reviewer",
            "wachtwoord": "een lang wachtwoord",
        }).status_code == 403
    finally:
        _TEST_USER.rol = "admin"


def test_de_laatste_beheerder_blijft_bestaan(client, db_session):
    """Anders kan niemand er nog bij en is het alleen met een script te herstellen."""
    admin = _gebruiker(db_session, "test-user-id", "admin")
    tweede = _gebruiker(db_session, "tweede-admin", "admin")

    # Zichzelf verwijderen mag sowieso niet.
    assert client.delete(f"/auth/users/{admin.id}").status_code == 422
    # De ander mag, want er blijft er dan één over.
    assert client.delete(f"/auth/users/{tweede.id}").status_code == 200


def test_toegang_intrekken_laat_het_werk_van_die_gebruiker_staan(client, db_session):
    """Een echte DELETE liep stuk zodra de gebruiker ergens in het werk stond.

    In productie was een toegewezen bellijstregel al genoeg: Postgres weigerde,
    en de interface meldde "Failed to fetch". Een lijst die zij heeft geüpload
    doet hetzelfde, en dat is het geval dat iedereen heeft.
    """
    from app.models import Batch

    _gebruiker(db_session, "test-user-id", "admin")
    collega = _gebruiker(db_session, "collega", "reviewer")
    db_session.add(Batch(naam="Lijst van de collega", jaar=2025,
                         geupload_door=collega.id))
    db_session.commit()

    response = client.delete(f"/auth/users/{collega.id}")

    assert response.status_code == 200
    db_session.expire_all()
    ingetrokken = db_session.get(User, "collega")
    assert ingetrokken is not None
    assert ingetrokken.verwijderd_op is not None
    # De lijst wijst nog steeds naar haar; anders is niet meer na te gaan wie
    # hem heeft geupload.
    batch = db_session.query(Batch).filter_by(naam="Lijst van de collega").one()
    assert batch.geupload_door == collega.id


def test_een_ingetrokken_account_kan_niet_meer_inloggen(client, db_session):
    from app.auth import authenticate_user

    _gebruiker(db_session, "test-user-id", "admin")
    collega = _gebruiker(db_session, "collega", "reviewer")

    assert authenticate_user(db_session, collega.email, "startwachtwoord") is not None
    client.delete(f"/auth/users/{collega.id}")
    db_session.expire_all()
    assert authenticate_user(db_session, collega.email, "startwachtwoord") is None


def test_een_lopende_sessie_van_een_ingetrokken_account_stopt(client, db_session):
    """Intrekken moet meteen gelden, niet pas als het token vanzelf verloopt."""
    import pytest
    from fastapi import HTTPException

    from app.auth import create_access_token, get_current_user

    _gebruiker(db_session, "test-user-id", "admin")
    collega = _gebruiker(db_session, "collega", "reviewer")
    token = create_access_token(collega)

    assert get_current_user(token, db_session).id == collega.id
    client.delete(f"/auth/users/{collega.id}")
    db_session.expire_all()
    with pytest.raises(HTTPException) as fout:
        get_current_user(token, db_session)
    assert fout.value.status_code == 401


def test_een_ingetrokken_account_staat_niet_meer_in_de_lijst(client, db_session):
    _gebruiker(db_session, "test-user-id", "admin")
    collega = _gebruiker(db_session, "collega", "reviewer")

    client.delete(f"/auth/users/{collega.id}")

    emails = [item["email"] for item in client.get("/auth/users").json()["items"]]
    assert "collega@etil.nl" not in emails


def test_een_ingetrokken_adres_kan_opnieuw_worden_uitgegeven(client, db_session):
    """Anders is een e-mailadres na een intrekking voorgoed onbruikbaar."""
    _gebruiker(db_session, "test-user-id", "admin")
    collega = _gebruiker(db_session, "collega", "reviewer")
    client.delete(f"/auth/users/{collega.id}")

    response = client.post("/auth/users", json={
        "naam": "Collega", "email": "collega@etil.nl", "rol": "reviewer",
        "wachtwoord": "een lang nieuw wachtwoord",
    })

    assert response.status_code == 200
    db_session.expire_all()
    hersteld = db_session.get(User, collega.id)
    assert hersteld.verwijderd_op is None
    assert verify_password("een lang nieuw wachtwoord", hersteld.password_hash)
