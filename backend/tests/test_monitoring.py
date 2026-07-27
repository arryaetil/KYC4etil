"""Tests voor periodieke jaarverslag-monitoring."""
import asyncio
import asyncio as _asyncio_voor_lock  # alias voorkomt naamsbotsing met bovenstaande `import asyncio`
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database import SessionLocal
from app.models import (
    AgentResult, Batch, BronKandidaat, Candidate, Company,
    JaarverslagMonitoring, PipelineRun, ResearchRun,
)
from app.pipeline import monitoring as monitoring_module
from app.pipeline.monitoring import check_company_jaarverslag
from app.providers.base import AgentFinding


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _maak_company(db, naam: str = "Okechamp B.V.") -> Company:
    batch = Batch(naam="monitoring-test", jaar=2026, totaal=1)
    db.add(batch)
    db.flush()
    company = Company(batch_id=batch.id, naam=naam, vestigingsnummer="111067624")
    db.add(company)
    db.commit()
    return company


def test_jaarverslag_monitoring_rij_aanmaken_en_opvragen():
    db = SessionLocal()
    try:
        company = _maak_company(db)
        status = JaarverslagMonitoring(
            company_id=company.id,
            laatste_bron_url="https://www.okechamp.nl/jaarverslag-2025.pdf",
            laatst_gecontroleerd_op=_now(),
        )
        db.add(status)
        db.commit()

        opgehaald = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one()
        assert opgehaald.laatste_bron_url == "https://www.okechamp.nl/jaarverslag-2025.pdf"
        assert opgehaald.laatst_gecontroleerd_op is not None
    finally:
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_documentjaar_neemt_verslagjaar_en_niet_publicatiedatum():
    assert monitoring_module._documentjaar(
        "https://example.test/20250604_U2025_Jaarverslag_2024.pdf",
    ) == 2024


def test_check_company_jaarverslag_nieuw_gevonden():
    db = SessionLocal()
    try:
        company = _maak_company(db)

        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is True
        ar = db.query(AgentResult).filter_by(company_id=company.id).one()
        assert ar.wp_gevonden == 138
        assert ar.bron_type == "jaarverslag"

        candidate = db.query(Candidate).filter_by(company_id=company.id).one()
        assert candidate.wp_kandidaat == 138

        status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one()
        assert status.laatste_bron_url == "https://www.okechamp.nl/jaarverslag-2025.pdf"
        assert status.laatst_gecontroleerd_op is not None
        run = db.query(PipelineRun).filter_by(company_id=company.id).order_by(
            PipelineRun.created_at.desc(),
        ).first()
        assert run.status == "new"
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_company_jaarverslag_werkt_bestaande_candidate_bij():
    """Een company kan al een candidate hebben (bijv. van een eerdere, volledige
    pipeline-run) — een nieuw gevonden jaarverslag moet die bijwerken, niet dupliceren
    (Candidate heeft een UniqueConstraint op company_id+batch_id)."""
    db = SessionLocal()
    try:
        company = _maak_company(db)
        oude_candidate = Candidate(
            company_id=company.id, batch_id=company.batch_id,
            wp_kandidaat=99, is_schatting=False, confidence_score=0.5,
            confidence_label="middel", status="pending",
        )
        db.add(oude_candidate)
        db.commit()
        oude_candidate_id = oude_candidate.id

        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is True
        candidaten = db.query(Candidate).filter_by(company_id=company.id).all()
        assert len(candidaten) == 1  # bijgewerkt, niet gedupliceerd
        assert candidaten[0].id == oude_candidate_id  # zelfde rij
        assert candidaten[0].wp_kandidaat == 138  # nieuwe waarde uit het jaarverslag
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_company_jaarverslag_geen_wijziging_tweede_keer():
    db = SessionLocal()
    try:
        company = _maak_company(db)

        eerste = asyncio.run(check_company_jaarverslag(db, company, 2026))
        tweede = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert eerste is True
        assert tweede is False
        assert db.query(AgentResult).filter_by(company_id=company.id).count() == 1
        assert db.query(Candidate).filter_by(company_id=company.id).count() == 1
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_company_jaarverslag_slaat_url_op_zonder_wp_gevonden(monkeypatch):
    """Vindt de agent alleen een bron_url maar geen WP-getal (bijv. jaarverslag
    gevonden maar geen medewerkersaantal erin geëxtraheerd), dan moet de URL toch
    als baseline opgeslagen worden — zonder dat er een AgentResult/Candidate ontstaat."""
    db = SessionLocal()
    try:
        company = _maak_company(db, naam="Onbekend Bedrijf")

        finding = AgentFinding(
            wp_gevonden=None, context=None, zekerheid="laag",
            reden="Jaarverslag gevonden, geen WP-getal geëxtraheerd",
            bron_url="https://example.test/jaarverslag.pdf", bron_type="jaarverslag",
        )
        mock_jaarverslag = MagicMock()
        mock_jaarverslag.run = AsyncMock(return_value=finding)
        monkeypatch.setattr(monitoring_module, "get_providers",
                            lambda: (None, None, mock_jaarverslag, None))

        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is True
        status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one()
        assert status.laatste_bron_url == "https://example.test/jaarverslag.pdf"
        assert db.query(AgentResult).filter_by(company_id=company.id).count() == 0
        assert db.query(Candidate).filter_by(company_id=company.id).count() == 0
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_company_jaarverslag_zonder_bron_url_wordt_overgeslagen(monkeypatch):
    """Vindt de agent helemaal niets (geen finding, of een finding zonder bron_url),
    dan blijft de baseline leeg en gebeurt er verder niets."""
    db = SessionLocal()
    try:
        company = _maak_company(db, naam="Onbekend Bedrijf")

        mock_jaarverslag = MagicMock()
        mock_jaarverslag.run = AsyncMock(return_value=None)
        monkeypatch.setattr(monitoring_module, "get_providers",
                            lambda: (None, None, mock_jaarverslag, None))

        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is False
        status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one()
        assert status.laatste_bron_url is None
    finally:
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_company_jaarverslag_zelfde_url_zonder_wp_geen_wijziging_tweede_keer(monkeypatch):
    """Blijft de agent dezelfde bron_url zonder WP-getal teruggeven, dan telt de
    tweede keer niet meer als wijziging."""
    db = SessionLocal()
    try:
        company = _maak_company(db, naam="Onbekend Bedrijf")

        finding = AgentFinding(
            wp_gevonden=None, context=None, zekerheid="laag", reden="t",
            bron_url="https://example.test/jaarverslag.pdf", bron_type="jaarverslag",
        )
        mock_jaarverslag = MagicMock()
        mock_jaarverslag.run = AsyncMock(return_value=finding)
        monkeypatch.setattr(monitoring_module, "get_providers",
                            lambda: (None, None, mock_jaarverslag, None))

        eerste = asyncio.run(check_company_jaarverslag(db, company, 2026))
        tweede = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert eerste is True
        assert tweede is False
    finally:
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
async def test_monitoring_verwerkt_nieuw_wp_bij_dezelfde_bron_url(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Nieuwe Extractie")
    bron_url = "https://extractie.test/jaarverslag-2025.pdf"
    db_session.add(JaarverslagMonitoring(
        company_id=company.id,
        laatste_bron_url=bron_url,
    ))
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=11000,
        context=(
            "Nieuwe Extractie biedt aan bijna 11.000 medewerkers een baan."
        ),
        zekerheid="middel",
        reden="deterministische fallback",
        bron_url=bron_url,
        bron_type="jaarverslag",
        is_limburg_specifiek=True,
    )
    agent = MagicMock()
    agent.run = AsyncMock(return_value=finding)
    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, agent, None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is True

    candidate = db_session.query(Candidate).filter_by(
        company_id=company.id,
    ).one()
    bron = db_session.query(BronKandidaat).filter_by(
        company_id=company.id,
    ).one()
    assert candidate.wp_kandidaat == 11000
    assert bron.wp_gevonden == 11000
    run = db_session.query(PipelineRun).filter_by(
        company_id=company.id,
        stap="jaarverslag_monitoring",
    ).order_by(PipelineRun.created_at.desc()).first()
    assert run.status == "updated"


@pytest.mark.asyncio
async def test_monitoring_slaat_nieuwe_bron_ook_modern_op(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Modern Bedrijf")
    finding = AgentFinding(
        wp_gevonden=42,
        context="Modern Bedrijf heeft 42 medewerkers.",
        zekerheid="hoog",
        reden="jaarverslag",
        bron_url="https://modern.example/jaarverslag-2025.pdf",
        bron_type="jaarverslag",
        is_limburg_specifiek=True,
        bron_pagina=17,
    )
    agent = MagicMock()
    agent.run = AsyncMock(return_value=finding)
    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, agent, None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is True

    run = db_session.query(ResearchRun).filter_by(company_id=company.id).one()
    bron = db_session.query(BronKandidaat).filter_by(company_id=company.id).one()
    assert run.doel == "periodieke jaarverslagmonitoring"
    assert run.gevraagd_jaar == 2025
    assert run.resultaat_status == "review_nodig"
    assert bron.wp_gevonden == 42
    assert bron.bron_pagina == 17
    assert bron.status == "voorgesteld"


@pytest.mark.asyncio
async def test_monitoring_ziet_trackingvariant_niet_als_nieuwe_bron(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Canonical Bedrijf")
    db_session.add(JaarverslagMonitoring(
        company_id=company.id,
        laatste_bron_url=(
            "https://www.canonical.example/jaarverslag.pdf?utm_source=mail"
        ),
    ))
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=None,
        context=None,
        zekerheid="laag",
        reden="baseline",
        bron_url="http://canonical.example/jaarverslag.pdf",
        bron_type="jaarverslag",
    )
    agent = MagicMock()
    agent.run = AsyncMock(return_value=finding)
    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, agent, None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is False
    assert (
        db_session.query(ResearchRun).filter_by(company_id=company.id).count()
        == 0
    )


@pytest.mark.asyncio
async def test_monitoring_gebruikt_adres_als_gemeente_ontbreekt(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Generieke Zorggroep")
    company.gemeente = None
    company.adres = "Markt 1, 5911 HD Venlo"
    db_session.commit()
    lookup = MagicMock()
    lookup.lookup = AsyncMock(return_value=None)
    agent = MagicMock()
    agent.run = AsyncMock(return_value=None)
    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (lookup, None, agent, None),
    )

    await check_company_jaarverslag(db_session, company, 2026)

    lookup.lookup.assert_awaited_once_with(
        "Generieke Zorggroep",
        "Markt 1, 5911 HD Venlo",
    )


@pytest.mark.asyncio
async def test_monitoring_vervangt_recent_verslag_niet_door_ouder(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Recent Bedrijf")
    recente_url = "https://recent.example/jaarverslag-2024.pdf"
    db_session.add(JaarverslagMonitoring(
        company_id=company.id,
        laatste_bron_url=recente_url,
    ))
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=10,
        context="10 medewerkers",
        zekerheid="hoog",
        reden="ouder verslag",
        bron_url="https://recent.example/jaarverslag-2022.pdf",
        bron_type="jaarverslag",
    )
    agent = MagicMock()
    agent.run = AsyncMock(return_value=finding)
    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, agent, None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is False

    status = db_session.query(JaarverslagMonitoring).filter_by(
        company_id=company.id,
    ).one()
    assert status.laatste_bron_url == recente_url


@pytest.mark.asyncio
async def test_monitoring_ruimt_ongeldige_legacy_baseline_op(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Verkeerde Legacybron")
    afgewezen_url = "https://ander-bedrijf.test/jaarverslag-2023.pdf"
    db_session.add(JaarverslagMonitoring(
        company_id=company.id,
        laatste_bron_url=afgewezen_url,
    ))
    agent_result = AgentResult(
        company_id=company.id,
        batch_id=company.batch_id,
        agent_type="jaarverslag",
        wp_gevonden=999,
        bron_url=afgewezen_url,
        bron_type="jaarverslag",
    )
    db_session.add(agent_result)
    db_session.flush()
    db_session.add(Candidate(
        company_id=company.id,
        batch_id=company.batch_id,
        wp_kandidaat=999,
        gekozen_agent_result=agent_result.id,
        confidence_score=0.9,
        confidence_label="hoog",
        status="pending",
    ))
    db_session.commit()

    class Agent:
        async def run(self, *args, **kwargs):
            return None

        async def validate_source(self, *args, **kwargs):
            return False

    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, Agent(), None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is True

    status = db_session.query(JaarverslagMonitoring).filter_by(
        company_id=company.id,
    ).one()
    assert status.laatste_bron_url is None
    candidate = db_session.query(Candidate).filter_by(
        company_id=company.id,
    ).one()
    assert candidate.wp_kandidaat is None
    assert candidate.gekozen_agent_result is None
    assert candidate.confidence_label is None
    assert "ingetrokken" in candidate.reviewer_signaal.lower()


@pytest.mark.asyncio
async def test_monitoring_herstelt_nieuwste_gevalideerde_moderne_bron(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Historie Bedrijf")
    db_session.add(JaarverslagMonitoring(
        company_id=company.id,
        laatste_bron_url="https://historie.test/jaarverslag-2024.pdf",
    ))
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="periodieke jaarverslagmonitoring",
        gevraagd_jaar=2025,
        status="completed",
        resultaat_status="review_nodig",
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url="https://historie.test/jaarverslag-2025.pdf",
        canonical_url="https://historie.test/jaarverslag-2025.pdf",
        brontype="jaarverslag",
        verslagjaar=2025,
        status="voorgesteld",
        rang=1,
    ))
    oudere_run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="periodieke jaarverslagmonitoring",
        gevraagd_jaar=2025,
        status="completed",
        resultaat_status="review_nodig",
    )
    db_session.add(oudere_run)
    db_session.flush()
    db_session.add(BronKandidaat(
        research_run_id=oudere_run.id,
        company_id=company.id,
        url=(
            "https://historie.test/"
            "20250604_U2025_Jaarverslag_2024.pdf"
        ),
        canonical_url=(
            "https://historie.test/"
            "20250604_U2025_Jaarverslag_2024.pdf"
        ),
        brontype="jaarverslag",
        # Simuleer de oude bug: DB zegt 2025 terwijl de URL 2024 zegt.
        verslagjaar=2025,
        status="voorgesteld",
        rang=1,
    ))
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=40,
        context="40 medewerkers",
        zekerheid="hoog",
        reden="ouder",
        bron_url="https://historie.test/jaarverslag-2024.pdf",
        bron_type="jaarverslag",
    )
    agent = MagicMock()
    agent.run = AsyncMock(return_value=finding)
    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, agent, None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is False

    status = db_session.query(JaarverslagMonitoring).filter_by(
        company_id=company.id,
    ).one()
    assert status.laatste_bron_url.endswith("jaarverslag-2025.pdf")


@pytest.mark.asyncio
async def test_monitoring_ruimt_wees_wp_zonder_statusbron_op(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Wees WP")
    bron_url = "https://verkeerd.test/jaarverslag-2023.pdf"
    agent_result = AgentResult(
        company_id=company.id,
        batch_id=company.batch_id,
        agent_type="jaarverslag",
        wp_gevonden=321,
        bron_url=bron_url,
        bron_type="jaarverslag",
    )
    db_session.add(agent_result)
    db_session.flush()
    db_session.add(Candidate(
        company_id=company.id,
        batch_id=company.batch_id,
        wp_kandidaat=321,
        gekozen_agent_result=agent_result.id,
        confidence_score=0.9,
        confidence_label="hoog",
        status="pending",
    ))
    db_session.commit()

    class Agent:
        async def run(self, *args, **kwargs):
            return None

        async def validate_source(self, *args, **kwargs):
            return False

    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, Agent(), None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is True
    candidate = db_session.query(Candidate).filter_by(
        company_id=company.id,
    ).one()
    assert candidate.wp_kandidaat is None
    assert candidate.gekozen_agent_result is None


@pytest.mark.asyncio
async def test_monitoring_begrenst_een_trage_organisatie(
    monkeypatch,
):
    db = SessionLocal()
    batch = Batch(naam="timeout-monitoring", jaar=2026, totaal=1)
    db.add(batch)
    db.flush()
    company = Company(batch_id=batch.id, naam="Trage monitor")
    db.add(company)
    db.commit()
    batch_id, company_id = batch.id, company.id
    db.close()

    async def trage_check(*_args):
        await asyncio.sleep(1)

    monkeypatch.setattr(
        monitoring_module,
        "check_company_jaarverslag",
        trage_check,
    )
    monkeypatch.setattr(
        monitoring_module,
        "get_settings",
        lambda: SimpleNamespace(research_company_timeout_seconds=0.01),
    )

    await monitoring_module._check_company_met_eigen_sessie(
        batch_id,
        company_id,
        2026,
        asyncio.Semaphore(1),
    )

    db = SessionLocal()
    try:
        fout = db.query(PipelineRun).filter_by(company_id=company_id).one()
        assert fout.status == "error"
        assert fout.error == "jaarverslagcontrole afgebroken na 0.01 seconden"
    finally:
        db.query(PipelineRun).filter_by(company_id=company_id).delete()
        db.query(Company).filter_by(id=company_id).delete()
        db.query(Batch).filter_by(id=batch_id).delete()
        db.commit()
        db.close()


def test_check_batch_jaarverslagen_beperkt_gelijktijdigheid(monkeypatch):
    """Verifieert dat check_batch_jaarverslagen ten hoogste max_concurrent
    organisaties tegelijk verwerkt bij een lijst die groter is dan die limiet."""
    from app.pipeline.monitoring import check_batch_jaarverslagen

    db = SessionLocal()
    try:
        batch = Batch(naam="concurrency-test", jaar=2026, totaal=20)
        db.add(batch)
        db.flush()
        company_ids = []
        for i in range(20):
            company = Company(batch_id=batch.id, naam=f"Bedrijf {i}")
            db.add(company)
            db.flush()
            company_ids.append(company.id)
        db.commit()
        batch_id = batch.id

        actief = 0
        max_actief = 0
        lock = _asyncio_voor_lock.Lock()

        async def fake_check_company_jaarverslag(db_arg, company_arg, jaar_arg):
            nonlocal actief, max_actief
            async with lock:
                actief += 1
                max_actief = max(max_actief, actief)
            await _asyncio_voor_lock.sleep(0.02)
            async with lock:
                actief -= 1
            return False

        monkeypatch.setattr(
            "app.pipeline.monitoring.check_company_jaarverslag",
            fake_check_company_jaarverslag,
        )

        asyncio.run(check_batch_jaarverslagen(batch_id, 2026, company_ids, max_concurrent=8))

        assert max_actief == 8
    finally:
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_batch_jaarverslagen_logt_fout_per_organisatie(monkeypatch):
    """Eén falende organisatie mag de rest van de batch niet blokkeren, en moet
    een eigen PipelineRun-foutregel krijgen."""
    from app.models import PipelineRun
    from app.pipeline.monitoring import check_batch_jaarverslagen

    db = SessionLocal()
    try:
        batch = Batch(naam="foutafhandeling-test", jaar=2026, totaal=2)
        db.add(batch)
        db.flush()
        faalt = Company(batch_id=batch.id, naam="Faalt B.V.")
        slaagt = Company(batch_id=batch.id, naam="Slaagt B.V.")
        db.add(faalt)
        db.add(slaagt)
        db.commit()
        batch_id = batch.id

        async def fake_check_company_jaarverslag(db_arg, company_arg, jaar_arg):
            if company_arg.naam == "Faalt B.V.":
                raise RuntimeError("gesimuleerde netwerkfout")
            return False

        monkeypatch.setattr(
            "app.pipeline.monitoring.check_company_jaarverslag",
            fake_check_company_jaarverslag,
        )

        asyncio.run(check_batch_jaarverslagen(batch_id, 2026, [faalt.id, slaagt.id]))

        fout = db.query(PipelineRun).filter_by(company_id=faalt.id, status="error").one()
        assert "gesimuleerde netwerkfout" in fout.error
        assert db.query(PipelineRun).filter_by(company_id=slaagt.id, status="error").count() == 0
    finally:
        db.query(PipelineRun).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_run_monitoring_watchlist_background_zonder_watchlist_is_stille_noop():
    """Geen batch met is_monitoringlijst=True -> geen fout, gewoon niets doen."""
    from app.pipeline.monitoring import run_monitoring_watchlist_background

    db = SessionLocal()
    try:
        db.query(Batch).filter_by(is_monitoringlijst=True).update({"is_monitoringlijst": False})
        db.commit()

        run_monitoring_watchlist_background()  # mag geen exception opgooien
    finally:
        db.close()


def test_run_monitoring_watchlist_background_respecteert_limit(monkeypatch):
    """limit beperkt hoeveel organisaties er gecontroleerd worden — bedoeld om
    tijdens testen niet steeds de volledige (kostbare) live-watchlist te draaien."""
    from app.pipeline.monitoring import run_monitoring_watchlist_background

    db = SessionLocal()
    try:
        batch = Batch(naam="watchlist-limit-test", jaar=2026, totaal=3,
                     is_monitoringlijst=True)
        db.add(batch)
        db.flush()
        namen = ["Org A", "Org B", "Org C"]
        for naam in namen:
            db.add(Company(batch_id=batch.id, naam=naam))
        db.commit()

        doorgegeven_ids = []

        async def fake_check_batch_jaarverslagen(batch_id, jaar, company_ids, max_concurrent=8):
            doorgegeven_ids.extend(company_ids)

        monkeypatch.setattr(
            "app.pipeline.monitoring.check_batch_jaarverslagen",
            fake_check_batch_jaarverslagen,
        )

        run_monitoring_watchlist_background(limit=2)

        assert len(doorgegeven_ids) == 2
    finally:
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_run_monitoring_watchlist_background_respecteert_offset(monkeypatch):
    from app.pipeline.monitoring import run_monitoring_watchlist_background

    db = SessionLocal()
    try:
        batch = Batch(
            naam="watchlist-offset-test",
            jaar=2026,
            totaal=4,
            is_monitoringlijst=True,
        )
        db.add(batch)
        db.flush()
        for naam in ["Org A", "Org B", "Org C", "Org D"]:
            db.add(Company(batch_id=batch.id, naam=naam))
        db.commit()
        alle_ids = [
            company.id
            for company in db.query(Company).filter_by(batch_id=batch.id).all()
        ]
        doorgegeven_ids = []

        async def fake_check_batch(
            batch_id, jaar, company_ids, max_concurrent=8,
        ):
            doorgegeven_ids.extend(company_ids)

        monkeypatch.setattr(
            "app.pipeline.monitoring.check_batch_jaarverslagen",
            fake_check_batch,
        )

        run_monitoring_watchlist_background(limit=2, offset=1)

        assert doorgegeven_ids == alle_ids[1:3]
    finally:
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()
