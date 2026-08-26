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
