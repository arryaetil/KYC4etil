"""Tests voor automatische WP-uitsplitsing-extractie door de jaarverslag-agent."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import AgentResult, Batch, Candidate, Company, User
from app.providers.base import AgentFinding, LocationInfo


def test_agent_finding_uitsplitsing_velden_zijn_optioneel():
    finding = AgentFinding(
        wp_gevonden=100, context="ctx", zekerheid="hoog", reden="t",
        bron_url="https://x", bron_type="jaarverslag",
    )
    assert finding.eigen_personeel is None
    assert finding.uitzend is None
    assert finding.detachering is None
    assert finding.wsw is None
    assert finding.man is None
    assert finding.vrouw is None
    assert finding.voltijd is None
    assert finding.deeltijd is None
    assert finding.pct_op_locatie is None


def test_agent_result_slaat_uitsplitsing_velden_op(db_session):
    batch = Batch(naam="test-batch", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.flush()

    ar = AgentResult(
        company_id=company.id, batch_id=batch.id, agent_type="jaarverslag",
        wp_gevonden=100, bron_type="jaarverslag",
        eigen_personeel=60, uitzend=20, detachering=15, wsw=5,
        man=70, vrouw=30, voltijd=80, deeltijd=20, pct_op_locatie=0.9,
    )
    db_session.add(ar)
    db_session.commit()

    opgehaald = db_session.get(AgentResult, ar.id)
    assert opgehaald.eigen_personeel == 60
    assert opgehaald.uitzend == 20
    assert opgehaald.detachering == 15
    assert opgehaald.wsw == 5
    assert opgehaald.man == 70
    assert opgehaald.vrouw == 30
    assert opgehaald.voltijd == 80
    assert opgehaald.deeltijd == 20
    assert opgehaald.pct_op_locatie == 0.9


@pytest.mark.asyncio
async def test_mock_jaarverslag_agent_geeft_uitsplitsing_door():
    from app.providers.mock import MockJaarverslagAgent

    finding = await MockJaarverslagAgent().run("Mondriaan", 2025)

    assert finding is not None
    assert finding.man == 1650
    assert finding.vrouw == 631
    assert finding.voltijd == 1780
    assert finding.deeltijd == 501


@pytest.mark.asyncio
async def test_mock_jaarverslag_agent_zonder_uitsplitsing_geeft_none():
    from app.providers.mock import MockJaarverslagAgent

    finding = await MockJaarverslagAgent().run("Jumbo Supermarkten B.V. - Filiaal", 2025)

    assert finding is not None
    assert finding.man is None
    assert finding.vrouw is None
    assert finding.eigen_personeel is None
    assert finding.pct_op_locatie is None


@pytest.mark.asyncio
async def test_verwerk_company_slaat_uitsplitsing_op_van_jaarverslag_agent():
    from app.pipeline.runner import verwerk_company

    db = MagicMock()
    db.flush = MagicMock()
    db.add = MagicMock()

    batch = MagicMock()
    batch.id = "batch-1"
    batch.jaar = 2025

    company = MagicMock()
    company.id = "comp-1"
    company.naam = "TestBedrijf"
    company.adres = None
    company.gemeente = "Maastricht"
    company.kvk_nummer = None
    company.website_url = None
    company.telefoonnummer = None

    j_finding = AgentFinding(
        wp_gevonden=100, context="ctx", zekerheid="hoog", reden="t",
        bron_url="https://example.test/jaarverslag.pdf", bron_type="jaarverslag",
        eigen_personeel=70, uitzend=20, detachering=10, wsw=0,
        man=60, vrouw=40, voltijd=80, deeltijd=20, pct_op_locatie=0.9,
    )

    mock_lookup = MagicMock()
    mock_lookup.lookup = AsyncMock(return_value=None)
    mock_lookup.locations = AsyncMock(return_value=LocationInfo(count_nl=None, count_lb=None, bron="mock"))
    mock_lookup.scrape_email = AsyncMock(return_value=None)

    mock_website = MagicMock()
    mock_website.run = AsyncMock(return_value=None)
    mock_website.extra_bronnen = AsyncMock(return_value=[])

    mock_jaarverslag = MagicMock()
    mock_jaarverslag.run = AsyncMock(return_value=j_finding)

    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(return_value=("unknown", "unknown"))

    with patch("app.pipeline.runner.get_providers",
               return_value=(mock_lookup, mock_website, mock_jaarverslag, mock_classifier)):
        await verwerk_company(db, company, batch)

    jaarverslag_ar = next(
        call.args[0] for call in db.add.call_args_list
        if isinstance(call.args[0], AgentResult) and call.args[0].agent_type == "jaarverslag"
    )
    assert jaarverslag_ar.eigen_personeel == 70
    assert jaarverslag_ar.uitzend == 20
    assert jaarverslag_ar.detachering == 10
    assert jaarverslag_ar.wsw == 0
    assert jaarverslag_ar.man == 60
    assert jaarverslag_ar.vrouw == 40
    assert jaarverslag_ar.voltijd == 80
    assert jaarverslag_ar.deeltijd == 20
    assert jaarverslag_ar.pct_op_locatie == 0.9


@pytest.mark.asyncio
async def test_check_company_jaarverslag_slaat_uitsplitsing_op(db_session, monkeypatch):
    from app.pipeline import monitoring as monitoring_module

    batch = Batch(naam="test-batch-monitoring", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.commit()

    finding = AgentFinding(
        wp_gevonden=100, context="ctx", zekerheid="hoog", reden="t",
        bron_url="https://example.test/jaarverslag.pdf", bron_type="jaarverslag",
        eigen_personeel=70, uitzend=20, detachering=10, wsw=0,
        man=60, vrouw=40, voltijd=80, deeltijd=20, pct_op_locatie=0.9,
    )

    mock_jaarverslag = MagicMock()
    mock_jaarverslag.run = AsyncMock(return_value=finding)
    monkeypatch.setattr(monitoring_module, "get_providers",
                        lambda: (None, None, mock_jaarverslag, None))

    resultaat = await monitoring_module.check_company_jaarverslag(db_session, company, 2026)

    assert resultaat is True
    ar = db_session.query(AgentResult).filter_by(company_id=company.id).one()
    assert ar.eigen_personeel == 70
    assert ar.uitzend == 20
    assert ar.detachering == 10
    assert ar.wsw == 0
    assert ar.man == 60
    assert ar.vrouw == 40
    assert ar.voltijd == 80
    assert ar.deeltijd == 20
    assert ar.pct_op_locatie == 0.9


@pytest.mark.asyncio
async def test_check_company_jaarverslag_crasht_niet_als_reconciliatie_afwijst(db_session, monkeypatch):
    """Als reconciliatie de gevonden bron afwijst (bv. cross-company-mismatch),
    moet check_company_jaarverslag dit gracieus afhandelen i.p.v. te crashen op
    bereken_confidence(None, ...) — dit trof eerder de wekelijkse monitoring-scheduler."""
    from app.pipeline import monitoring as monitoring_module

    batch = Batch(naam="test-batch-monitoring-afgewezen", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.commit()

    # Context bevat het WP-getal niet -> _candidate_hard_gate wijst deze af,
    # reconcilieer() geeft dus finding=None terug.
    finding = AgentFinding(
        wp_gevonden=100, context="geen letterlijke vermelding van het getal", zekerheid="hoog",
        reden="t", bron_url="https://example.test/jaarverslag.pdf", bron_type="jaarverslag",
    )

    mock_jaarverslag = MagicMock()
    mock_jaarverslag.run = AsyncMock(return_value=finding)
    monkeypatch.setattr(monitoring_module, "get_providers",
                        lambda: (None, None, mock_jaarverslag, None))

    resultaat = await monitoring_module.check_company_jaarverslag(db_session, company, 2026)

    assert resultaat is True  # bron_url is wel gewijzigd/gedetecteerd
    # Geen candidate aangemaakt met het afgewezen getal
    from app.models import Candidate
    assert db_session.query(Candidate).filter_by(company_id=company.id).one_or_none() is None


def test_valideer_wp_uitsplitsing_zonder_agent_result_geeft_leeg():
    from app.pipeline.wp_uitsplitsing import valideer_wp_uitsplitsing

    assert valideer_wp_uitsplitsing(None, 100) == {}


def test_valideer_wp_uitsplitsing_neemt_kloppende_groepen_over():
    from app.pipeline.wp_uitsplitsing import valideer_wp_uitsplitsing

    ar = AgentResult(
        company_id="c", batch_id="b", agent_type="jaarverslag", bron_type="jaarverslag",
        man=60, vrouw=40, voltijd=80, deeltijd=20,
        eigen_personeel=70, uitzend=20, detachering=10, wsw=0,
        pct_op_locatie=0.9,
    )

    resultaat = valideer_wp_uitsplitsing(ar, 100)

    assert resultaat == {
        "man": 60, "vrouw": 40, "voltijd": 80, "deeltijd": 20,
        "eigen_personeel": 70, "uitzend": 20, "detachering": 10, "wsw": 0,
        "pct_op_locatie": 0.9,
    }


def test_valideer_wp_uitsplitsing_negeert_niet_kloppende_groep():
    from app.pipeline.wp_uitsplitsing import valideer_wp_uitsplitsing

    ar = AgentResult(
        company_id="c", batch_id="b", agent_type="jaarverslag", bron_type="jaarverslag",
        man=70, vrouw=60,
        voltijd=80, deeltijd=20,
    )

    resultaat = valideer_wp_uitsplitsing(ar, 100)

    assert "man" not in resultaat
    assert "vrouw" not in resultaat
    assert resultaat["voltijd"] == 80
    assert resultaat["deeltijd"] == 20


def test_valideer_wp_uitsplitsing_negeert_onvolledige_groep():
    from app.pipeline.wp_uitsplitsing import valideer_wp_uitsplitsing

    ar = AgentResult(
        company_id="c", batch_id="b", agent_type="jaarverslag", bron_type="jaarverslag",
        man=60,
    )

    resultaat = valideer_wp_uitsplitsing(ar, 100)

    assert "man" not in resultaat


def test_approve_neemt_kloppende_uitsplitsing_over_in_wprecord(client, db_session):
    from app.models import Candidate, WPRecord

    db_session.add(User(id="test-user-id", naam="Test User", email="test-user@example.test", rol="admin"))
    batch = Batch(naam="approve-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.flush()
    ar = AgentResult(
        company_id=company.id, batch_id=batch.id, agent_type="jaarverslag",
        wp_gevonden=100, bron_type="jaarverslag", bron_url="https://x",
        man=60, vrouw=40, voltijd=80, deeltijd=20,
        eigen_personeel=70, uitzend=20, detachering=10, wsw=0, pct_op_locatie=0.9,
    )
    db_session.add(ar)
    db_session.flush()
    cand = Candidate(company_id=company.id, batch_id=batch.id, wp_kandidaat=100,
                     is_schatting=False, gekozen_agent_result=ar.id,
                     confidence_score=0.9, confidence_label="hoog", strategie="auto")
    db_session.add(cand)
    db_session.commit()

    response = client.post(f"/candidates/{cand.id}/approve")

    assert response.status_code == 200
    rec = db_session.get(WPRecord, response.json()["wp_record_id"])
    assert rec.man == 60
    assert rec.vrouw == 40
    assert rec.voltijd == 80
    assert rec.deeltijd == 20
    assert rec.eigen_personeel == 70
    assert rec.uitzend == 20
    assert rec.detachering == 10
    assert rec.wsw == 0
    assert rec.pct_op_locatie == 0.9


def test_approve_negeert_niet_kloppende_uitsplitsing_in_wprecord(client, db_session):
    from app.models import Candidate, WPRecord

    db_session.add(User(id="test-user-id", naam="Test User", email="test-user-2@example.test", rol="admin"))
    batch = Batch(naam="approve-test-2", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf 2")
    db_session.add(company)
    db_session.flush()
    ar = AgentResult(
        company_id=company.id, batch_id=batch.id, agent_type="jaarverslag",
        wp_gevonden=100, bron_type="jaarverslag", bron_url="https://x",
        man=70, vrouw=60,
    )
    db_session.add(ar)
    db_session.flush()
    cand = Candidate(company_id=company.id, batch_id=batch.id, wp_kandidaat=100,
                     is_schatting=False, gekozen_agent_result=ar.id,
                     confidence_score=0.9, confidence_label="hoog", strategie="auto")
    db_session.add(cand)
    db_session.commit()

    response = client.post(f"/candidates/{cand.id}/approve")

    assert response.status_code == 200
    rec = db_session.get(WPRecord, response.json()["wp_record_id"])
    assert rec.wp_waarde == 100
    assert rec.man is None
    assert rec.vrouw is None


def test_company_detail_toont_agent_uitsplitsing(client, db_session):
    batch = Batch(naam="detail-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.flush()
    db_session.add(AgentResult(
        company_id=company.id, batch_id=batch.id, agent_type="jaarverslag",
        wp_gevonden=100, bron_type="jaarverslag",
        man=60, vrouw=40, voltijd=80, deeltijd=20,
        eigen_personeel=70, uitzend=20, detachering=10, wsw=0, pct_op_locatie=0.9,
    ))
    db_session.commit()

    response = client.get(f"/batches/{batch.id}/companies/{company.id}")

    assert response.status_code == 200
    ar = response.json()["agent_results"][0]
    assert ar["man"] == 60
    assert ar["vrouw"] == 40
    assert ar["voltijd"] == 80
    assert ar["deeltijd"] == 20
    assert ar["eigen_personeel"] == 70
    assert ar["uitzend"] == 20
    assert ar["detachering"] == 10
    assert ar["wsw"] == 0
    assert ar["pct_op_locatie"] == 0.9


def test_companies_lijst_toont_ruwe_wp_zonder_kandidaat(client, db_session):
    """Als er geen officiële kandidaat is (bv. afgewezen door een hard gate), moet
    de batch-lijst toch het ruw gevonden getal tonen i.p.v. niets — het label/de
    kleur blijft het vertrouwenssignaal, dit is puur ter info voor de reviewer."""
    batch = Batch(naam="ruwe-wp-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.flush()
    db_session.add(AgentResult(
        company_id=company.id, batch_id=batch.id, agent_type="jaarverslag",
        wp_gevonden=44485, bron_type="jaarverslag",
    ))
    db_session.add(Candidate(
        company_id=company.id, batch_id=batch.id,
        wp_kandidaat=None, confidence_score=0.0, confidence_label="laag",
        reconciliatie_reden="afgewezen: niet-Limburg-specifiek zonder vestigingscount",
    ))
    db_session.commit()

    response = client.get(f"/batches/{batch.id}/companies")

    assert response.status_code == 200
    item = response.json()[0]
    assert item["wp_kandidaat"] is None
    assert item["wp_gevonden_ruw"] == 44485


def test_companies_lijst_toont_geen_ruwe_wp_als_kandidaat_al_bekend(client, db_session):
    batch = Batch(naam="ruwe-wp-test-2", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.flush()
    db_session.add(AgentResult(
        company_id=company.id, batch_id=batch.id, agent_type="website",
        wp_gevonden=21, bron_type="website",
    ))
    db_session.add(Candidate(
        company_id=company.id, batch_id=batch.id,
        wp_kandidaat=21, confidence_score=0.9, confidence_label="hoog",
        reconciliatie_reden="enige bron: website",
    ))
    db_session.commit()

    response = client.get(f"/batches/{batch.id}/companies")

    assert response.status_code == 200
    item = response.json()[0]
    assert item["wp_kandidaat"] == 21
    assert item["wp_gevonden_ruw"] is None


def test_companies_lijst_toont_vestigingsnummer_cber_kvk_en_sector(client, db_session):
    batch = Batch(naam="zoekvelden-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(
        batch_id=batch.id, naam="Testbedrijf", vestigingsnummer="V099",
        cb_er="CB099", kvk_nummer="99887766", sbi_omschrijving="Detailhandel",
    )
    db_session.add(company)
    db_session.commit()

    response = client.get(f"/batches/{batch.id}/companies")

    assert response.status_code == 200
    item = response.json()[0]
    assert item["vestigingsnummer"] == "V099"
    assert item["cb_er"] == "CB099"
    assert item["kvk_nummer"] == "99887766"
    assert item["sbi_omschrijving"] == "Detailhandel"


def test_company_update_route_is_niet_dubbel_geregistreerd():
    from app.main import app

    matches = [
        route for route in app.routes
        if getattr(route, "path", None) == "/batches/{batch_id}/companies/{company_id}"
        and "PATCH" in getattr(route, "methods", set())
    ]

    assert len(matches) == 1


def test_company_afgewerkt_toggle_via_patch(client, db_session):
    batch = Batch(naam="afgewerkt-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.commit()

    response = client.get(f"/batches/{batch.id}/companies")
    assert response.json()[0]["afgewerkt"] is False

    patch_response = client.patch(
        f"/batches/{batch.id}/companies/{company.id}",
        json={"afgewerkt": True},
    )
    assert patch_response.status_code == 200

    response = client.get(f"/batches/{batch.id}/companies")
    assert response.json()[0]["afgewerkt"] is True


def test_company_afgewerkt_blijft_ongewijzigd_zonder_dat_veld(client, db_session):
    batch = Batch(naam="afgewerkt-test-2", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf", afgewerkt=True)
    db_session.add(company)
    db_session.commit()

    patch_response = client.patch(
        f"/batches/{batch.id}/companies/{company.id}",
        json={"naam": "Testbedrijf BV"},
    )
    assert patch_response.status_code == 200

    response = client.get(f"/batches/{batch.id}/companies")
    assert response.json()[0]["afgewerkt"] is True
    assert response.json()[0]["naam"] == "Testbedrijf BV"


def test_afgewerkt_migratie_geeft_bestaande_rijen_false_default():
    """Verifieer dat wanneer de afgewerkt-kolom wordt toegevoegd aan een
    bestaande companies-tabel, bestaande rijen de waarde False krijgen
    (via DEFAULT FALSE in de ALTER TABLE) i.p.v. NULL.
    Dit test de fix voor het issue waar een migrations-helper geen DEFAULT
    clause toevoegde."""
    from sqlalchemy import create_engine, event, inspect, text
    from sqlite3 import Connection as SQLite3Connection

    # Maak een apart testdatabase zonder afgewerkt kolom (simuleer oud schema)
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

    @event.listens_for(test_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        if isinstance(dbapi_conn, SQLite3Connection):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Maak batches en companies tabellen zonder afgewerkt kolom
    with test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE batches (
                id TEXT PRIMARY KEY,
                naam TEXT,
                jaar INTEGER,
                status TEXT DEFAULT 'pending',
                totaal INTEGER,
                verwerkt INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                completed_at TIMESTAMP,
                is_monitoringlijst BOOLEAN DEFAULT FALSE
            )
        """))
        conn.execute(text("""
            CREATE TABLE companies (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                vestigingsnummer TEXT,
                naam TEXT NOT NULL,
                cb_er TEXT,
                adres TEXT,
                gemeente TEXT,
                sbi_code TEXT,
                sbi_omschrijving TEXT,
                kvk_nummer TEXT,
                website_url TEXT,
                telefoonnummer TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY(batch_id) REFERENCES batches(id)
            )
        """))

        # Voeg testdata in: bestaande batch en bedrijf
        conn.execute(text("""
            INSERT INTO batches (id, naam, jaar, created_at)
            VALUES ('batch-1', 'test-batch', 2026, CURRENT_TIMESTAMP)
        """))
        conn.execute(text("""
            INSERT INTO companies (id, batch_id, naam, created_at)
            VALUES
                ('comp-1', 'batch-1', 'Bedrijf 1', CURRENT_TIMESTAMP),
                ('comp-2', 'batch-1', 'Bedrijf 2', CURRENT_TIMESTAMP)
        """))

    # Verifieer dat afgewerkt kolom nog niet bestaat
    inspector = inspect(test_engine)
    existing_companies = {col["name"] for col in inspector.get_columns("companies")}
    assert "afgewerkt" not in existing_companies

    # Voer de migratie uit
    from app.database import _add_column_if_missing
    with test_engine.begin() as conn:
        _add_column_if_missing(conn, "companies", existing_companies, "afgewerkt", "BOOLEAN DEFAULT FALSE")

    # Controleer dat de kolom nu bestaat
    inspector = inspect(test_engine)
    existing_companies = {col["name"] for col in inspector.get_columns("companies")}
    assert "afgewerkt" in existing_companies

    # Controleer dat bestaande rijen afgewerkt=0 (False in SQLite) hebben
    with test_engine.begin() as conn:
        result = conn.execute(text("SELECT id, afgewerkt FROM companies ORDER BY id"))
        rows = result.fetchall()

    assert len(rows) == 2
    # SQLite returneerde 0 voor False en 1 voor True
    for row_id, afgewerkt_waarde in rows:
        assert afgewerkt_waarde == 0, (
            f"Bestaande rij {row_id} moet afgewerkt=0 (False) hebben door DEFAULT FALSE, "
            f"maar heeft {afgewerkt_waarde} (NULL zou None zijn)"
        )


def test_upload_batch_slaat_ingelogde_gebruiker_op(client, db_session):
    db_session.add(User(id="test-user-id", naam="Test User", email="test@etil.nl",
                        rol="admin", password_hash=""))
    db_session.commit()

    csv_data = "naam\nTestbedrijf\n"
    response = client.post(
        "/batches/upload?naam=upload-tracking-test&jaar=2026",
        files={"file": ("bedrijven.csv", csv_data.encode(), "text/csv")},
    )
    assert response.status_code == 200
    batch_id = response.json()["batch_id"]

    batch = db_session.get(Batch, batch_id)
    assert batch.geupload_door == "test-user-id"


def test_list_batches_toont_geupload_door_naam(client, db_session):
    db_session.add(User(id="test-user-id", naam="Test User", email="test@etil.nl",
                        rol="admin", password_hash=""))
    db_session.commit()

    csv_data = "naam\nTestbedrijf\n"
    upload_response = client.post(
        "/batches/upload?naam=upload-tracking-test-2&jaar=2026",
        files={"file": ("bedrijven.csv", csv_data.encode(), "text/csv")},
    )
    assert upload_response.status_code == 200

    response = client.get("/batches")
    assert response.status_code == 200
    item = next(b for b in response.json() if b["naam"] == "upload-tracking-test-2")
    assert item["geupload_door_naam"] == "Test User"


def test_list_batches_toont_none_zonder_bekende_uploader(client, db_session):
    batch = Batch(naam="batch-zonder-uploader", jaar=2026, totaal=0)
    db_session.add(batch)
    db_session.commit()

    response = client.get("/batches")
    assert response.status_code == 200
    item = next(b for b in response.json() if b["naam"] == "batch-zonder-uploader")
    assert item["geupload_door_naam"] is None
