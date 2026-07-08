"""Tests voor automatische WP-uitsplitsing-extractie door de jaarverslag-agent."""
import pytest

from app.models import AgentResult, Batch, Company
from app.providers.base import AgentFinding


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
