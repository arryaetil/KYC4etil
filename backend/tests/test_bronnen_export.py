from io import BytesIO

from openpyxl import load_workbook

from app.models import Batch, BronKandidaat, Company, ResearchRun


def test_export_bevat_gekozen_bron_en_geen_registervelden(client, db_session):
    batch = Batch(naam="bronwerkbank", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Voorbeeld", vestigingsnummer="V1")
    db_session.add(company)
    db_session.flush()
    run = ResearchRun(company_id=company.id, batch_id=batch.id, doel="bron", status="completed")
    db_session.add(run)
    db_session.flush()
    db_session.add(BronKandidaat(
        research_run_id=run.id, company_id=company.id,
        url="https://voorbeeld.nl/jaarverslag.pdf",
        canonical_url="https://voorbeeld.nl/jaarverslag.pdf",
        brontype="jaarverslag", status="geaccepteerd", wp_gevonden=42,
        eenheid="werkzame_personen", review_reason_code="juiste_bron_bruikbaar_bewijs",
    ))
    db_session.commit()

    response = client.get(f"/batches/{batch.id}/export.xlsx")
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content), read_only=True)
    sheet = workbook.active
    rows = iter(sheet.iter_rows())
    headers = [cell.value for cell in next(rows)]
    values = [cell.value for cell in next(rows)]
    assert "Reviewredencode" in headers
    assert "WP goedgekeurd" not in headers
    assert values[headers.index("Bron-URL")] == "https://voorbeeld.nl/jaarverslag.pdf"
    assert values[headers.index("Gevonden waarde")] == 42
