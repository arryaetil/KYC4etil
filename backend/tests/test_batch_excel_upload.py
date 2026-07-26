import io

from openpyxl import Workbook

from app.models import Company, User


def _zorggroep_excel() -> io.BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "De zorggroep"
    sheet.append(["vestnr", "naam", "totwp"])
    sheet.append(["111067624", "Camillus", 309])
    sheet.append(["111068648", "De Zorggroep - Westhoven", 1459])
    sheet.append([None, None, None])
    sheet.append([None, None, "=SUM(C2:C4)"])
    bestand = io.BytesIO()
    workbook.save(bestand)
    bestand.seek(0)
    return bestand


def test_excel_upload_accepteert_zorggroepformaat(client, db_session):
    db_session.add(User(
        id="test-user-id",
        naam="Test User",
        email="test@etil.nl",
        rol="admin",
        password_hash="",
    ))
    db_session.commit()

    response = client.post(
        "/batches/upload?naam=zorggroep&jaar=2026",
        files={
            "file": (
                "Copy of Zorggroep.xlsx",
                _zorggroep_excel(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["aantal_companies"] == 2
    companies = db_session.query(Company).order_by(Company.naam).all()
    assert [(company.vestigingsnummer, company.naam) for company in companies] == [
        ("111067624", "Camillus"),
        ("111068648", "De Zorggroep - Westhoven"),
    ]
