"""Mappen: de ordeningslaag boven de onderzoekslijsten.

Het gevoeligste gedrag is verwijderen. Onderzoeksresultaten zijn duur om
opnieuw op te bouwen, dus een map mag haar lijsten nooit stilzwijgend
meenemen.
"""
import pytest

from app.models import Batch, Map, User


@pytest.fixture(autouse=True)
def _testgebruiker(db_session):
    """`aangemaakt_door` is een echte foreign key; de auth-override levert
    alleen een los User-object, geen rij in de database."""
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(
            id="test-user-id", naam="Test User", email="test@etil.nl",
            rol="admin", password_hash="",
        ))
        db_session.commit()


def _maak_map(client, naam="Provincie Limburg"):
    response = client.post("/mappen", json={"naam": naam})
    assert response.status_code == 201, response.text
    return response.json()


def test_map_aanmaken_en_teruglezen(client):
    gemaakt = _maak_map(client)
    assert gemaakt["naam"] == "Provincie Limburg"
    assert gemaakt["aantal_lijsten"] == 0

    lijst = client.get("/mappen").json()
    assert [item["naam"] for item in lijst["mappen"]] == ["Provincie Limburg"]


def test_map_zonder_naam_wordt_geweigerd(client):
    assert client.post("/mappen", json={"naam": "   "}).status_code == 422
    assert client.post("/mappen", json={"naam": ""}).status_code == 422


def test_dubbele_naam_wordt_geweigerd(client):
    _maak_map(client, "Zorg 2026")
    # Hoofdletterongevoelig: twee mappen die alleen in schrijfwijze verschillen
    # zijn voor de reviewer niet uit elkaar te houden.
    response = client.post("/mappen", json={"naam": "zorg 2026"})
    assert response.status_code == 409
    assert "bestaat al" in response.json()["detail"]


def test_map_hernoemen(client):
    gemaakt = _maak_map(client, "Tijdelijk")
    response = client.patch(f"/mappen/{gemaakt['id']}", json={"naam": "Definitief"})
    assert response.status_code == 200
    assert response.json()["naam"] == "Definitief"


def test_hernoemen_naar_bestaande_naam_wordt_geweigerd(client):
    _maak_map(client, "Eerste")
    tweede = _maak_map(client, "Tweede")
    response = client.patch(f"/mappen/{tweede['id']}", json={"naam": "Eerste"})
    assert response.status_code == 409


def test_lege_map_verwijderen_mag_direct(client):
    gemaakt = _maak_map(client, "Leeg")
    assert client.delete(f"/mappen/{gemaakt['id']}").status_code == 200
    assert client.get("/mappen").json()["mappen"] == []


def test_gevulde_map_verwijderen_wordt_geweigerd(client, db_session):
    gemaakt = _maak_map(client, "Met lijsten")
    db_session.add(Batch(naam="Testset", jaar=2026, totaal=20, map_id=gemaakt["id"]))
    db_session.commit()

    response = client.delete(f"/mappen/{gemaakt['id']}")
    assert response.status_code == 409
    # Het aantal hoort in de melding, zodat de interface kan vertellen waar
    # het om gaat in plaats van een kale foutmelding te tonen.
    assert "1 lijst" in response.json()["detail"]
    assert db_session.get(Map, gemaakt["id"]) is not None


def test_gevulde_map_verwijderen_laat_de_lijsten_bestaan(client, db_session):
    gemaakt = _maak_map(client, "Opruimen")
    batch = Batch(naam="Testset", jaar=2026, totaal=20, map_id=gemaakt["id"])
    db_session.add(batch)
    db_session.commit()
    batch_id = batch.id

    response = client.delete(f"/mappen/{gemaakt['id']}?ontkoppel_lijsten=true")
    assert response.status_code == 200
    assert response.json()["lijsten_ontkoppeld"] == 1

    db_session.expire_all()
    bewaard = db_session.get(Batch, batch_id)
    assert bewaard is not None, "een lijst mag nooit meeverdwijnen met de map"
    assert bewaard.map_id is None


def test_lijsten_filteren_op_map(client, db_session):
    een = _maak_map(client, "Map A")
    twee = _maak_map(client, "Map B")
    db_session.add_all([
        Batch(naam="In A", jaar=2026, totaal=1, map_id=een["id"]),
        Batch(naam="In B", jaar=2026, totaal=1, map_id=twee["id"]),
        Batch(naam="Losse lijst", jaar=2026, totaal=1),
    ])
    db_session.commit()

    in_a = client.get(f"/batches?map_id={een['id']}").json()
    assert [b["naam"] for b in in_a] == ["In A"]

    los = client.get("/batches?losse_lijsten=true").json()
    assert [b["naam"] for b in los] == ["Losse lijst"]

    # Zonder filter blijft het gedrag ongewijzigd voor bestaande aanroepers.
    alles = client.get("/batches").json()
    assert {b["naam"] for b in alles} == {"In A", "In B", "Losse lijst"}


def test_losse_lijsten_worden_geteld(client, db_session):
    db_session.add(Batch(naam="Zonder map", jaar=2026, totaal=1))
    db_session.commit()
    assert client.get("/mappen").json()["losse_lijsten"] == 1


def test_monitoringlijst_telt_niet_mee_in_een_map(client, db_session):
    """De monitoringlijst heeft een eigen module en hoort niet in een map."""
    gemaakt = _maak_map(client, "Zorg")
    db_session.add(Batch(
        naam="Jaarverslag-monitoringlijst", jaar=2026, totaal=205,
        is_monitoringlijst=True, map_id=gemaakt["id"],
    ))
    db_session.commit()

    assert client.get("/mappen").json()["mappen"][0]["aantal_lijsten"] == 0
    # En hij mag het verwijderen van de map dus ook niet blokkeren.
    assert client.delete(f"/mappen/{gemaakt['id']}").status_code == 200


def test_onbekende_map_geeft_404(client):
    assert client.patch("/mappen/bestaat-niet", json={"naam": "X"}).status_code == 404
    assert client.delete("/mappen/bestaat-niet").status_code == 404


def test_archiveren_haalt_de_map_uit_het_overzicht(client, db_session):
    """Archiveren is opruimen zonder weggooien: de lijsten blijven staan."""
    gemaakt = _maak_map(client, "Zorg 2025")
    batch = Batch(naam="Testset", jaar=2026, totaal=20, map_id=gemaakt["id"])
    db_session.add(batch)
    db_session.commit()
    batch_id = batch.id

    response = client.post(f"/mappen/{gemaakt['id']}/archiveren")
    assert response.status_code == 200
    assert response.json()["gearchiveerd_op"] is not None

    overzicht = client.get("/mappen").json()
    assert overzicht["mappen"] == []
    # Het aantal komt wel mee, zodat de interface kan tonen dát er iets in
    # het archief zit zonder ernaartoe te hoeven.
    assert overzicht["aantal_gearchiveerd"] == 1

    db_session.expire_all()
    bewaard = db_session.get(Batch, batch_id)
    assert bewaard is not None
    assert bewaard.map_id == gemaakt["id"], "de lijst hoort in de map te blijven"


def test_archief_is_apart_op_te_vragen(client):
    gemaakt = _maak_map(client, "Oud")
    client.post(f"/mappen/{gemaakt['id']}/archiveren")

    archief = client.get("/mappen?gearchiveerd=true").json()
    assert [item["naam"] for item in archief["mappen"]] == ["Oud"]


def test_herstellen_geeft_de_map_precies_terug(client, db_session):
    gemaakt = _maak_map(client, "Terug")
    db_session.add(Batch(naam="Testset", jaar=2026, totaal=20, map_id=gemaakt["id"]))
    db_session.commit()
    client.post(f"/mappen/{gemaakt['id']}/archiveren")

    hersteld = client.post(f"/mappen/{gemaakt['id']}/herstellen").json()
    assert hersteld["gearchiveerd_op"] is None
    assert hersteld["aantal_lijsten"] == 1

    overzicht = client.get("/mappen").json()
    assert [item["naam"] for item in overzicht["mappen"]] == ["Terug"]
    assert overzicht["aantal_gearchiveerd"] == 0


def test_tweemaal_archiveren_verzet_het_moment_niet(client):
    """Anders zou een dubbelklik de archiefdatum stilletjes bijwerken."""
    gemaakt = _maak_map(client, "Stabiel")
    eerste = client.post(f"/mappen/{gemaakt['id']}/archiveren").json()
    tweede = client.post(f"/mappen/{gemaakt['id']}/archiveren").json()
    assert eerste["gearchiveerd_op"] == tweede["gearchiveerd_op"]


def test_naam_botst_ook_met_een_gearchiveerde_map(client):
    """Anders levert herstellen ineens twee mappen met dezelfde naam op."""
    gemaakt = _maak_map(client, "Zorg 2026")
    client.post(f"/mappen/{gemaakt['id']}/archiveren")

    response = client.post("/mappen", json={"naam": "zorg 2026"})
    assert response.status_code == 409
    # De melding moet vertellen wáár die map dan staat, want in het overzicht
    # is ze niet te vinden.
    assert "gearchiveerde" in response.json()["detail"]


def test_archiveren_van_onbekende_map_geeft_404(client):
    assert client.post("/mappen/bestaat-niet/archiveren").status_code == 404
    assert client.post("/mappen/bestaat-niet/herstellen").status_code == 404
