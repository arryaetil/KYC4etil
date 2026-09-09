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


# `test_afgewerkt_migratie_geeft_bestaande_rijen_false_default` stond hier.
# Die test riep de private migratiehelper rechtstreeks aan met een handgemaakt
# oud schema, en legde zo één kolom vast in plaats van de regel erachter. De
# regel — een nieuwe kolom krijgt de standaardwaarde uit het model in plaats
# van NULL — staat nu in `test_migraties.py`, samen met de rest van wat er
# gebeurt als de database achterloopt op de modellen.


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


def test_backfill_geupload_door_kent_admin_toe_aan_oude_batches(db_session):
    from scripts.backfill_geupload_door import backfill_geupload_door

    db_session.add(User(id="admin-id", naam="Admin", email="admin@etil.nl",
                        rol="admin", password_hash=""))
    oude_batch = Batch(naam="oude-batch", jaar=2026, totaal=0)
    db_session.add(oude_batch)
    db_session.commit()

    aantal = backfill_geupload_door(db_session, admin_email="admin@etil.nl")

    db_session.refresh(oude_batch)
    assert aantal == 1
    assert oude_batch.geupload_door == "admin-id"

    # Idempotent: een tweede aanroep vindt niets meer om bij te werken.
    aantal_tweede_keer = backfill_geupload_door(db_session, admin_email="admin@etil.nl")
    assert aantal_tweede_keer == 0
