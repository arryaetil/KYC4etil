"""Tests voor identity_class en scope_class classificatievelden."""
import pytest

from app.models import AgentResult, Batch, Company
from app.providers.base import AgentFinding


def test_agent_result_slaat_classificatie_velden_op(db_session):
    batch = Batch(naam="test-batch", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.flush()
    ar = AgentResult(
        company_id=company.id, batch_id=batch.id, agent_type="website",
        wp_gevonden=5, bron_type="website",
        identity_class="exact_entity", scope_class="vestiging",
    )
    db_session.add(ar)
    db_session.commit()

    opgehaald = db_session.get(AgentResult, ar.id)
    assert opgehaald.identity_class == "exact_entity"
    assert opgehaald.scope_class == "vestiging"


def test_agent_finding_classificatie_velden_zijn_optioneel():
    finding = AgentFinding(
        wp_gevonden=5, context="ctx", zekerheid="hoog", reden="t",
        bron_url="https://x", bron_type="website",
    )
    assert finding.identity_class is None
    assert finding.scope_class is None
