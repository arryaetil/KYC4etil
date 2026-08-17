"""Tests voor periodieke jaarverslag-monitoring."""
import asyncio
import asyncio as _asyncio_voor_lock  # alias voorkomt naamsbotsing met bovenstaande `import asyncio`
from dataclasses import replace
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
from app.research.validation import SourceDocument


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


def test_documentjaar_herstelt_weggevallen_procentteken_voor_spatie():
    assert monitoring_module._documentjaar(
        "https://cdn.example/Jaarverslag202025-gecomprimeerd.pdf",
    ) == 2025


def test_check_company_jaarverslag_nieuw_gevonden():
    db = SessionLocal()
    try:
        company = _maak_company(db)

        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is True
        bron = db.query(BronKandidaat).filter_by(company_id=company.id).one()
        assert bron.wp_gevonden == 138
        assert bron.brontype == "jaarverslag"
        assert db.query(AgentResult).filter_by(company_id=company.id).count() == 0
        assert db.query(Candidate).filter_by(company_id=company.id).count() == 0

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


def test_check_company_jaarverslag_laat_legacy_candidate_ongemoeid():
    """Monitoring schrijft alleen naar het canonieke bronnenmodel."""
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
        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is True
        candidaten = db.query(Candidate).filter_by(company_id=company.id).all()
        assert len(candidaten) == 1
        assert candidaten[0].wp_kandidaat == 99
        bron = db.query(BronKandidaat).filter_by(company_id=company.id).one()
        assert bron.wp_gevonden == 138
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
        assert db.query(BronKandidaat).filter_by(company_id=company.id).count() == 1
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

    bron = db_session.query(BronKandidaat).filter_by(
        company_id=company.id,
    ).one()
    assert bron.wp_gevonden == 11000
    assert db_session.query(Candidate).filter_by(company_id=company.id).count() == 0
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
async def test_andere_url_voor_hetzelfde_verslagjaar_is_geen_nieuw_verslag(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Zelfde Jaar")
    db_session.add(JaarverslagMonitoring(
        company_id=company.id,
        laatste_bron_url="https://organisatie.test/verslag-2025-v1.pdf",
        laatste_verslagjaar=2025,
    ))
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=None,
        context=None,
        zekerheid="hoog",
        reden="dezelfde editie op een nieuwe URL",
        bron_url="https://organisatie.test/verslag-2025-definitief.pdf",
        bron_type="jaarverslag",
        raw={"verslagjaar": 2025},
    )

    class Agent:
        async def run(self, *args, **kwargs):
            return finding

    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, Agent(), None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is True
    run = db_session.query(PipelineRun).filter_by(
        company_id=company.id,
        stap="jaarverslag_monitoring",
    ).order_by(PipelineRun.created_at.desc()).first()
    assert run.status == "updated"


@pytest.mark.asyncio
async def test_hoger_verslagjaar_geeft_nieuw_signaal(db_session, monkeypatch):
    company = _maak_company(db_session, naam="Nieuw Jaar")
    db_session.add(JaarverslagMonitoring(
        company_id=company.id,
        laatste_bron_url="https://organisatie.test/verslag-2024.pdf",
        laatste_verslagjaar=2024,
    ))
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=None,
        context=None,
        zekerheid="hoog",
        reden="nieuwe editie",
        bron_url="https://organisatie.test/verslag-2025.pdf",
        bron_type="jaarverslag",
        raw={"verslagjaar": 2025},
    )

    class Agent:
        async def run(self, *args, **kwargs):
            return finding

    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, Agent(), None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is True
    status = db_session.query(JaarverslagMonitoring).filter_by(
        company_id=company.id,
    ).one()
    run = db_session.query(PipelineRun).filter_by(
        company_id=company.id,
        stap="jaarverslag_monitoring",
    ).order_by(PipelineRun.created_at.desc()).first()
    assert status.laatste_verslagjaar == 2025
    assert run.status == "new"


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
async def test_monitoring_gebruikt_nederland_en_bewaart_gevonden_website(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Koraal Groep")
    lookup = MagicMock()
    lookup.lookup = AsyncMock(return_value=SimpleNamespace(
        website="https://www.koraal.nl",
    ))
    agent = MagicMock()
    agent.run = AsyncMock(return_value=None)
    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (lookup, None, agent, None),
    )

    await check_company_jaarverslag(db_session, company, 2026)

    lookup.lookup.assert_awaited_once_with("Koraal Groep", "Nederland")
    db_session.refresh(company)
    assert company.website_url == "https://www.koraal.nl"


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
    legacy_candidate = db_session.query(Candidate).filter_by(
        company_id=company.id,
    ).one()
    assert legacy_candidate.wp_kandidaat == 999


@pytest.mark.asyncio
async def test_ongeldige_baseline_blokkeert_gevonden_oudere_bron_niet(
    db_session, monkeypatch,
):
    company = _maak_company(db_session, naam="Organisatiebreed")
    db_session.add(JaarverslagMonitoring(
        company_id=company.id,
        laatste_bron_url=(
            "https://organisatie.test/jaarverslag-deelrapport-2025.pdf"
        ),
    ))
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=None,
        context=None,
        zekerheid="laag",
        reden="meest recente geldige organisatiebrede bron",
        bron_url="https://organisatie.test/jaarverslag-2024.pdf",
        bron_type="jaarverslag",
    )

    class Agent:
        async def run(self, *args, **kwargs):
            return finding

        async def validate_source(self, *args, **kwargs):
            return False

    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, Agent(), None),
    )

    assert await check_company_jaarverslag(
        db_session,
        company,
        2026,
    ) is True

    status = db_session.query(JaarverslagMonitoring).filter_by(
        company_id=company.id,
    ).one()
    assert status.laatste_bron_url.endswith("jaarverslag-2024.pdf")
    run = db_session.query(PipelineRun).filter_by(
        company_id=company.id,
        stap="jaarverslag_monitoring",
    ).order_by(PipelineRun.created_at.desc()).first()
    assert run.status == "new"


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

    assert await check_company_jaarverslag(db_session, company, 2026) is False
    candidate = db_session.query(Candidate).filter_by(
        company_id=company.id,
    ).one()
    assert candidate.wp_kandidaat == 321


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
            for company in (
                db.query(Company)
                .filter_by(batch_id=batch.id)
                .order_by(Company.created_at, Company.id)
                .all()
            )
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


# --- onderscheid tussen de drie skip-uitkomsten ---

def test_monitoringstatussen_zijn_onderscheidend():
    """"skipped" dekte drie verschillende uitkomsten: niets gevonden, een ouder
    verslag genegeerd, en de bron stond al goed. In pipeline_runs was daardoor
    niet te zien of een ontbrekende bron echt niet bestaat of dat het zoeken
    faalt — precies de vraag bij een watchlist met 123 lege bronnen."""
    from app.pipeline.monitoring import (STATUS_GEEN_BRON_GEVONDEN,
                                         STATUS_ONGEWIJZIGD,
                                         STATUS_OUDER_VERSLAG)

    statussen = {STATUS_GEEN_BRON_GEVONDEN, STATUS_ONGEWIJZIGD, STATUS_OUDER_VERSLAG}
    assert len(statussen) == 3
    # 'new' en 'error' hebben een eigen betekenis in de dashboard-aggregatie
    # (routers/monitoring.py) en mogen niet worden hergebruikt.
    assert not statussen & {"new", "error", "updated"}


def test_monitoringcontrole_legt_kosten_vast():
    """Monitoring riep start_usage_tracking() nooit aan, waardoor tokens en
    kosten in pipeline_runs leeg bleven en een ronde niet te beprijzen was."""
    from unittest.mock import MagicMock
    from app.models import PipelineRun
    from app.pipeline import monitoring
    from app.research.usage import record_provider_call, start_usage_tracking

    db = MagicMock()
    start_usage_tracking()
    record_provider_call("google_places_text_search", kosten_micro_usd=32_000)

    run = monitoring._log(db, "b", "c", "jaarverslag_monitoring",
                          monitoring.STATUS_ONGEWIJZIGD, 0.0)

    assert isinstance(run, PipelineRun)
    assert run.kosten_cents == 3


# --- oudere verslagen blijven beoordeelbaar ---

@pytest.mark.asyncio
async def test_monitoring_bewaart_ouder_verslag_als_beoordeelbare_bron(
    db_session, monkeypatch,
):
    """Van de 26 organisaties op verslagjaar 2024 en de 13 op 2023 had er 0 een
    bronkaart: `valideer_bron` wees het afwijkende verslagjaar hard af, waarna
    `_sla_moderne_bron_op` terugkeerde vóór het opslaan. De reviewer zag de URL
    wel op de monitoringkaart, maar had niets te beoordelen."""
    company = _maak_company(db_session, naam="Achterloper")
    company.website_url = "https://achterloper.test"
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=340,
        context="In 2023 waren er 340 medewerkers in dienst.",
        zekerheid="hoog",
        reden="nieuwste beschikbare jaarverslag",
        bron_url="https://achterloper.test/jaarverslag-2023.pdf",
        bron_type="jaarverslag",
        bron_pagina=12,
    )

    class Agent:
        async def find_latest_source(self, *args, **kwargs):
            return finding

    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, Agent(), None),
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is True

    bron = db_session.query(BronKandidaat).filter_by(company_id=company.id).one()
    assert bron.verslagjaar == 2023
    assert bron.wp_gevonden == 340
    assert bron.bron_pagina == 12
    # Dezelfde sleutel die de batchflow gebruikt, zodat de reviewer één begrip
    # ziet; de bronkaart maakt daar "Verslag 2023, gevraagd is 2025" van.
    assert "afwijkend_verslagjaar" in bron.waarschuwingen
    run = db_session.query(ResearchRun).filter_by(company_id=company.id).one()
    assert run.gevraagd_jaar == 2025
    assert run.resultaat_status == "review_nodig"


@pytest.mark.asyncio
async def test_vondst_zonder_jaartal_verdringt_gedateerde_baseline_niet(
    db_session, monkeypatch,
):
    """Een jaarloze overzichtspagina liet het bekende verslagjaar verdwijnen.

    De ouder-dan-check kijkt alleen naar een aantoonbaar lager jaartal; bij een
    URL zonder jaartal liep de controle daar langs en zette `laatste_verslagjaar`
    op None. Een organisatie mét het verslag over 2025 zakte zo stil terug naar
    "verslag zonder jaartal", inclusief verlies van de goede URL. De vondst moet
    wél als bronkandidaat bij de reviewer terechtkomen."""
    company = _maak_company(db_session, naam="Jaarloos")
    company.website_url = "https://jaarloos.test"
    actuele_url = "https://jaarloos.test/jaarverslag-2025.pdf"
    db_session.add(JaarverslagMonitoring(
        company_id=company.id,
        laatste_bron_url=actuele_url,
        laatste_verslagjaar=2025,
    ))
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=None,
        context=None,
        zekerheid="laag",
        reden="overzichtspagina met jaarverslagen",
        bron_url="https://jaarloos.test/publicaties/jaarverslagen/",
        bron_type="jaarverslag",
    )

    class Agent:
        async def find_latest_source(self, *args, **kwargs):
            return finding

        async def validate_source(self, *args, **kwargs):
            return True

    monkeypatch.setattr(
        monitoring_module,
        "get_providers",
        lambda: (None, None, Agent(), None),
    )

    await check_company_jaarverslag(db_session, company, 2026)

    status = db_session.query(JaarverslagMonitoring).filter_by(
        company_id=company.id,
    ).one()
    assert status.laatste_bron_url == actuele_url
    assert status.laatste_verslagjaar == 2025
    kandidaten = db_session.query(BronKandidaat).filter_by(
        company_id=company.id,
    ).all()
    assert [bron.url for bron in kandidaten] == [finding.bron_url]


def test_ouder_verslag_van_een_andere_organisatie_blijft_afgewezen():
    """De verslagjaar-uitzondering mag de identiteitscheck niet meenemen.

    Een naam-match koppelde eerder een Zorgboog-jaarverantwoording aan
    Stichting Pergamijn, inclusief 2.400 WP. Zo'n bron heeft twee
    afwijsmotieven; alleen het verslagjaar mag worden kwijtgescholden."""
    from app.research.validation import SourceDocument

    validatie = monitoring_module._valideer_voor_monitoring(
        SourceDocument(
            naam="Stichting Pergamijn",
            company_website_url="https://www.pergamijn.org",
            url="https://www.zorgboog.nl/Jaarverantwoording-Zorgboog-2023.pdf",
            titel="Jaarverantwoording-Zorgboog-2023.pdf",
            brontype="jaarverslag",
            documenttype="jaarverslag",
            gevraagd_jaar=2025,
            verslagjaar=2023,
            wp_gevonden=2400,
            eenheid="werkzame_personen",
            bewijsfragment="2.400 medewerkers",
        ),
    )

    assert validatie.is_afgewezen is True
    assert "verkeerde organisatie" in validatie.afwijsredenen


def test_verslagjaar_nieuwer_dan_gevraagd_blijft_afgewezen():
    """Alleen ouder wordt bewaard. Een verslagjaar boven het gevraagde jaar komt
    in de praktijk alleen voor als een publicatiedatum uit de URL is gelezen
    (DSV: `.../filings/3363/2026/RNS/...`); dat als verslagjaar op een bronkaart
    zetten zou een feit beweren dat we niet hebben."""
    from app.research.validation import SourceDocument

    validatie = monitoring_module._valideer_voor_monitoring(
        SourceDocument(
            naam="DSV",
            company_website_url="https://www.dsv.test",
            url="https://www.dsv.test/filings/3363/2026/RNS/3363_rns_2026-02-04.pdf",
            titel="3363_rns_2026-02-04.pdf",
            brontype="jaarverslag",
            documenttype="jaarverslag",
            gevraagd_jaar=2025,
            verslagjaar=2026,
        ),
    )

    assert validatie.is_afgewezen is True
    assert validatie.afwijsredenen == ["verkeerd verslagjaar"]


# --- DigiMV natief in de monitoring ---

_UIT_DE_URL = object()


def _digimv_document(
    *,
    verslagjaar: int | None = _UIT_DE_URL,
    boekjaar: int = 2024,
    wp_gevonden: int | None = 1204,
    naam: str = "Zorgstichting Sint Anna",
    titel: str = "bestuursverslag: Jaardocument.pdf",
    bewijsfragment: str | None = "Het aantal medewerkers bedroeg 1.204.",
) -> SourceDocument:
    """Een DigiMV-document zoals `_zoek_digimv_document` het teruggeeft.

    Let op de titel: een archiefbestand heet `Jaardocument.pdf` en staat op
    `digimv13.desan.nl`, dus noemt noch de organisatie noch het jaar. Het
    boekjaar zit alleen in de `year=`-parameter van de archief-URL; standaard
    staat het verslagjaar daarop, zoals na die functie. `verslagjaar=None` geeft
    de ruwe uitvoer van `live_tools.inspect`, vóór die verrijking."""
    if verslagjaar is _UIT_DE_URL:
        verslagjaar = boekjaar
    return SourceDocument(
        naam=naam,
        company_website_url="https://sintanna.test",
        url=(
            "https://digimv13.desan.nl/api/ArchiveSearch/GetDocument"
            f"?documentId=98765&year={boekjaar}&fileNameOption=&fileName="
        ),
        titel=titel,
        tekst="",
        brontype="digimv",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=verslagjaar,
        wp_gevonden=wp_gevonden,
        eenheid="werkzame_personen" if wp_gevonden is not None else None,
        bewijsfragment=bewijsfragment,
        scope_class="concern",
        research_route="digimv",
        raw_data={"providers": ["digimv_direct"], "queries": ["DigiMV direct"]},
    )


@pytest.mark.asyncio
async def test_monitoring_gebruikt_digimv_als_de_agent_niets_vindt(
    db_session, monkeypatch,
):
    """Monitoring vroeg DigiMV nooit iets — de sterkste verklaring voor een groot
    deel van de 108 watchlist-organisaties zonder bron, want hun
    jaarverantwoording staat niet op de eigen website maar in dat archief."""
    company = _maak_company(db_session, naam="Zorgstichting Sint Anna")
    company.website_url = "https://sintanna.test"
    db_session.commit()

    class Agent:
        async def find_latest_source(self, *args, **kwargs):
            return None

    monkeypatch.setattr(
        monitoring_module, "get_providers",
        lambda: (None, None, Agent(), None),
    )
    monkeypatch.setattr(
        monitoring_module, "get_settings",
        lambda: SimpleNamespace(provider_mode="live"),
    )

    async def fake_digimv(company_arg, jaar, website_url):
        assert jaar == 2026
        assert website_url == "https://sintanna.test"
        return _digimv_document()

    monkeypatch.setattr(monitoring_module, "_zoek_digimv_document", fake_digimv)

    assert await check_company_jaarverslag(db_session, company, 2026) is True

    bron = db_session.query(BronKandidaat).filter_by(company_id=company.id).one()
    # Het brontype en de concern-scope van het onderzochte document blijven
    # staan; het wordt niet opnieuw als website-jaarverslag opgebouwd.
    assert bron.brontype == "digimv"
    assert bron.scope_class == "concern"
    assert bron.wp_gevonden == 1204
    # Het boekjaar komt uit de archief-URL, want de bestandsnaam noemt er geen.
    assert bron.verslagjaar == 2024
    assert "afwijkend_verslagjaar" in bron.waarschuwingen
    status = db_session.query(JaarverslagMonitoring).filter_by(
        company_id=company.id,
    ).one()
    assert status.laatste_verslagjaar == 2024
    run = db_session.query(ResearchRun).filter_by(company_id=company.id).one()
    paden = {item["route"]: item for item in run.onderzoekspaden}
    assert paden["digimv"]["status"] == "afgerond"
    assert paden["digimv"]["aantal_bronnen"] == 1
    assert paden["document"]["aantal_bronnen"] == 0


@pytest.mark.asyncio
async def test_monitoring_vraagt_digimv_niet_bij_een_actueel_verslag(
    db_session, monkeypatch,
):
    """Draait de gewone route al binnen, dan kost een archiefaanroep alleen tijd
    en tokens. Doeljaar bij watchlistjaar 2026 is verslagjaar 2025."""
    company = _maak_company(db_session, naam="Actueel Zorgcentrum")
    company.website_url = "https://actueel.test"
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=88,
        context="88 medewerkers in 2025",
        zekerheid="hoog",
        reden="jaarverslag over het doeljaar",
        bron_url="https://actueel.test/jaarverslag-2025.pdf",
        bron_type="jaarverslag",
    )

    class Agent:
        async def find_latest_source(self, *args, **kwargs):
            return finding

    monkeypatch.setattr(
        monitoring_module, "get_providers",
        lambda: (None, None, Agent(), None),
    )

    async def digimv_mag_niet_draaien(*_args, **_kwargs):
        raise AssertionError("DigiMV is bevraagd terwijl het verslag actueel is")

    monkeypatch.setattr(
        monitoring_module, "_zoek_digimv_document", digimv_mag_niet_draaien,
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is True

    run = db_session.query(ResearchRun).filter_by(company_id=company.id).one()
    paden = {item["route"]: item for item in run.onderzoekspaden}
    assert paden["digimv"]["status"] == "overgeslagen"
    assert paden["digimv"]["statusreden"] == monitoring_module.DIGIMV_NIET_NODIG
    assert paden["document"]["aantal_bronnen"] == 1


@pytest.mark.asyncio
async def test_digimv_verdringt_een_nieuwer_verslag_van_de_agent_niet(
    db_session, monkeypatch,
):
    """De archiefroute is een aanvulling, geen vervanging: een nieuwer verslag
    van de gewone route blijft de bron."""
    company = _maak_company(db_session, naam="Zorgstichting Sint Anna")
    company.website_url = "https://sintanna.test"
    db_session.commit()
    finding = AgentFinding(
        wp_gevonden=90,
        context="90 medewerkers",
        zekerheid="middel",
        reden="nieuwste verslag op de eigen site",
        bron_url="https://sintanna.test/jaarverslag-2024.pdf",
        bron_type="jaarverslag",
    )

    class Agent:
        async def find_latest_source(self, *args, **kwargs):
            return finding

    monkeypatch.setattr(
        monitoring_module, "get_providers",
        lambda: (None, None, Agent(), None),
    )
    monkeypatch.setattr(
        monitoring_module, "get_settings",
        lambda: SimpleNamespace(provider_mode="live"),
    )

    async def fake_digimv(*_args, **_kwargs):
        return _digimv_document(boekjaar=2023)

    monkeypatch.setattr(monitoring_module, "_zoek_digimv_document", fake_digimv)

    assert await check_company_jaarverslag(db_session, company, 2026) is True

    bron = db_session.query(BronKandidaat).filter_by(company_id=company.id).one()
    assert bron.url == finding.bron_url
    run = db_session.query(ResearchRun).filter_by(company_id=company.id).one()
    paden = {item["route"]: item for item in run.onderzoekspaden}
    assert paden["digimv"]["status"] == "afgerond"
    assert paden["digimv"]["aantal_bronnen"] == 0
    assert paden["document"]["aantal_bronnen"] == 1


@pytest.mark.asyncio
async def test_digimv_wordt_in_mockmodus_niet_bevraagd(db_session, monkeypatch):
    """Er is geen mockprovider voor het archief; `zoek_digimv_documenten` praat
    rechtstreeks met digimv13.desan.nl. De testsuite mag daar nooit langs."""
    company = _maak_company(db_session, naam="Mockorganisatie")

    class Agent:
        async def find_latest_source(self, *args, **kwargs):
            return None

    monkeypatch.setattr(
        monitoring_module, "get_providers",
        lambda: (None, None, Agent(), None),
    )

    async def digimv_mag_niet_draaien(*_args, **_kwargs):
        raise AssertionError("DigiMV is bevraagd in mock-modus")

    monkeypatch.setattr(
        monitoring_module, "_zoek_digimv_document", digimv_mag_niet_draaien,
    )

    assert await check_company_jaarverslag(db_session, company, 2026) is False


@pytest.mark.asyncio
async def test_digimv_document_wint_op_wp_bewijs_en_erft_het_boekjaar(
    monkeypatch,
):
    """Van de archiefdocumenten hoort het document met WP-bewijs voor te gaan.

    DigiMV levert per organisatie meerdere stukken; de accountantsverklaring
    bevat per definitie geen personeelscijfer (zie `digimv.py`). De ranking van
    de batchflow maakt die keuze al, dus die wordt hier hergebruikt."""
    company = SimpleNamespace(
        naam="Zorgstichting Sint Anna",
        gemeente="Venlo",
        kvk_nummer=None,
        vestigingsnummer="000012345678",
    )
    zonder_wp = _digimv_document(
        verslagjaar=None, wp_gevonden=None, bewijsfragment=None,
        titel="accountantsverklaring: Verklaring.pdf",
    )
    met_wp = _digimv_document(verslagjaar=None)

    async def fake_zoek(context, max_documenten=3):
        assert context.gevraagd_jaar == 2025
        assert context.gemeente == "Venlo"
        return [
            SimpleNamespace(queries=["DigiMV direct: zonder wp"]),
            SimpleNamespace(queries=["DigiMV direct: met wp"]),
        ]

    monkeypatch.setattr(monitoring_module, "zoek_digimv_documenten", fake_zoek)

    async def fake_inspect(self, context, query, result):
        return zonder_wp if "zonder" in query.query else met_wp

    monkeypatch.setattr(
        monitoring_module.LiveResearchTools, "inspect", fake_inspect,
    )

    document = await monitoring_module._zoek_digimv_document(
        company, 2026, "https://sintanna.test",
    )

    assert document is not None
    assert document.wp_gevonden == 1204
    # `inspect` gaf verslagjaar=None terug; het boekjaar komt uit de URL.
    assert document.verslagjaar == 2024


@pytest.mark.asyncio
async def test_digimv_bron_wordt_niet_op_de_naamheuristiek_afgewezen():
    """Een archiefbestand heet `Jaardocument.pdf` op digimv13.desan.nl, dus de
    naamheuristiek vindt de organisatienaam nergens en riep "verkeerde
    organisatie". DigiMV identificeert scherper (exact KvK of unieke exacte
    kernnaam, fail-closed bij naamgenoten), dus die afwijzing mag hier niet
    staan. Wel als `possible_match`: DigiMV kent de rechtspersoon, niet deze
    vestiging."""
    document = _digimv_document(
        bewijsfragment="Het aantal medewerkers bedroeg 1.204.",
    )

    validatie = monitoring_module._valideer_voor_monitoring(document)

    assert validatie.is_afgewezen is False
    assert validatie.identity_class == "possible_match"
    assert validatie.validaties["digimv_archiefidentificatie"]["heuristiek"] == (
        "mismatch"
    )


@pytest.mark.asyncio
async def test_niet_digimv_bron_blijft_op_de_naamheuristiek_afgewezen():
    """De uitzondering geldt alleen voor het archief zelf. Een willekeurige
    PDF van een ander domein blijft afgewezen — dat is de Zorgboog-bescherming."""
    document = replace(
        _digimv_document(),
        url="https://www.zorgboog.nl/Jaarverantwoording-Zorgboog-2023.pdf",
        brontype="jaarverslag",
        research_route="document",
    )

    validatie = monitoring_module._valideer_voor_monitoring(document)

    assert validatie.is_afgewezen is True
    assert "verkeerde organisatie" in validatie.afwijsredenen


def test_run_monitoring_watchlist_slaat_actuele_organisaties_over(monkeypatch):
    """De echte kostenbesparing zit hier, niet in de router: een organisatie
    waarvan het verslag over het doeljaar al binnen is, wordt niet opnieuw
    doorzocht. Watchlistjaar 2026 betekent doeljaar 2025."""
    from app.models import JaarverslagMonitoring
    from app.pipeline.monitoring import run_monitoring_watchlist_background

    db = SessionLocal()
    try:
        batch = Batch(naam="watchlist-skip-test", jaar=2026, totaal=3,
                      is_monitoringlijst=True)
        db.add(batch)
        db.flush()
        per_naam = {}
        for naam in ("Actueel", "Ouder", "Niets"):
            company = Company(batch_id=batch.id, naam=naam)
            db.add(company)
            db.flush()
            per_naam[naam] = company.id
        db.add_all([
            JaarverslagMonitoring(
                company_id=per_naam["Actueel"],
                laatste_bron_url="https://x.test/jaarverslag-2025.pdf",
                laatste_verslagjaar=2025,
            ),
            JaarverslagMonitoring(
                company_id=per_naam["Ouder"],
                laatste_bron_url="https://x.test/jaarverslag-2023.pdf",
                laatste_verslagjaar=2023,
            ),
        ])
        db.commit()

        doorgegeven = []

        async def fake_check_batch_jaarverslagen(
            batch_id, jaar, company_ids, max_concurrent=8,
        ):
            doorgegeven.extend(company_ids)

        monkeypatch.setattr(
            "app.pipeline.monitoring.check_batch_jaarverslagen",
            fake_check_batch_jaarverslagen,
        )

        run_monitoring_watchlist_background()
        assert per_naam["Actueel"] not in doorgegeven
        assert set(doorgegeven) == {per_naam["Ouder"], per_naam["Niets"]}

        doorgegeven.clear()
        run_monitoring_watchlist_background(hercontroleer_actuele=True)
        assert per_naam["Actueel"] in doorgegeven
        assert len(doorgegeven) == 3
    finally:
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()
