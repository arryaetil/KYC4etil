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


from app.pipeline.identity_scope import (
    domain_matches_company,
    heuristic_identity_class,
    heuristic_scope_class,
)


def test_domain_matches_company_zelfde_domein():
    assert domain_matches_company(
        "https://www.salonhandmade.nl/jaarverslag.pdf", "https://salonhandmade.nl"
    ) is True


def test_domain_matches_company_ander_domein():
    assert domain_matches_company(
        "https://www.heijmans.nl/jaarverslag-2025.pdf", "https://www.salonhandmade.nl"
    ) is False


def test_domain_matches_company_onbekend_zonder_website_url():
    assert domain_matches_company("https://www.heijmans.nl/x.pdf", None) is None


def test_heuristic_identity_exact_entity_bij_domeinmatch():
    result = heuristic_identity_class(
        "Salon Handmade", "Boek bij een van onze 3 medewerkers.",
        "https://www.salonhandmade.nl/afspraak", "https://www.salonhandmade.nl",
    )
    assert result == "exact_entity"


def test_heuristic_identity_mismatch_bij_cross_company_context():
    # Regressie: Salon Handmade (Weert) kreeg ooit een Heijmans-jaarverslag
    # met 6.158 medewerkers als bron — pure cross-company mismatch.
    result = heuristic_identity_class(
        "Salon Handmade",
        "Heijmans is een beursgenoteerd bouwbedrijf met 6.158 medewerkers in Nederland.",
        "https://www.heijmans.nl/jaarverslag-2025.pdf",
        "https://www.salonhandmade.nl",
    )
    assert result == "mismatch"


def test_heuristic_identity_same_brand_or_group_bij_gedeeltelijke_naammatch():
    # Jumbo Supermarkten filiaal: bron noemt "Jumbo" wel, maar is een landelijk/
    # concernbreed jaarverslag, geen exacte 1-op-1 vestigingsbron.
    result = heuristic_identity_class(
        "Jumbo Supermarkten B.V. - Filiaal",
        "Jumbo behaalde in 2025 een omzet van 11 miljard euro.",
        "https://www.jumbo.com/over-jumbo/jaarverslag-2025.pdf",
        None,
    )
    assert result == "same_brand_or_group"


def test_heuristic_scope_vestiging_voor_limburg_specifieke_website():
    assert heuristic_scope_class(True, "website") == "vestiging"


def test_heuristic_scope_limburg_voor_limburg_specifiek_jaarverslag():
    assert heuristic_scope_class(True, "jaarverslag") == "limburg"


def test_heuristic_scope_nederland_bij_niet_limburg_specifiek():
    assert heuristic_scope_class(False, "jaarverslag") == "nederland"


def test_heuristic_scope_unknown_zonder_signaal():
    assert heuristic_scope_class(None, "jaarverslag") == "unknown"


@pytest.mark.asyncio
async def test_mock_classifier_geeft_heuristiek_door():
    from app.providers.mock import MockIdentityScopeClassifier

    finding = AgentFinding(
        wp_gevonden=3, context="Boek bij een van onze 3 medewerkers.",
        zekerheid="hoog", reden="mock", bron_url="https://www.salonhandmade.nl/afspraak",
        bron_type="website", is_limburg_specifiek=True,
    )
    identity, scope = await MockIdentityScopeClassifier().classify(
        "Salon Handmade", "Langstraat 8", "Weert", "https://www.salonhandmade.nl", finding,
    )
    assert identity == "exact_entity"
    assert scope == "vestiging"


@pytest.mark.asyncio
async def test_mock_classifier_geeft_unknown_zonder_finding():
    from app.providers.mock import MockIdentityScopeClassifier

    identity, scope = await MockIdentityScopeClassifier().classify(
        "Salon Handmade", None, "Weert", None, None,
    )
    assert identity == "unknown"
    assert scope == "unknown"


def test_get_providers_retourneert_vier_providers(monkeypatch):
    from app.config import get_settings
    from app.providers import get_providers

    get_settings.cache_clear()
    monkeypatch.setenv("PROVIDER_MODE", "mock")
    result = get_providers()
    assert len(result) == 4
    get_settings.cache_clear()


from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_live_classifier_slaat_llm_over_bij_domeinmatch():
    from app.providers.live import LiveIdentityScopeClassifier

    finding = AgentFinding(
        wp_gevonden=3, context="3 medewerkers op onze vestiging.", zekerheid="hoog",
        reden="live", bron_url="https://www.salonhandmade.nl/afspraak", bron_type="website",
    )
    with patch("app.providers.identity._llm_classify_scope", new=AsyncMock(return_value="vestiging")) as scope_mock:
        identity, scope = await LiveIdentityScopeClassifier().classify(
            "Salon Handmade", "Langstraat 8", "Weert",
            "https://www.salonhandmade.nl", finding,
        )
    assert identity == "exact_entity"
    assert scope == "vestiging"
    scope_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_live_classifier_roept_llm_aan_bij_onbekend_domein():
    from app.providers.live import LiveIdentityScopeClassifier

    finding = AgentFinding(
        wp_gevonden=6158, context="Heijmans telt 6.158 medewerkers.", zekerheid="hoog",
        reden="live", bron_url="https://www.heijmans.nl/jaarverslag.pdf", bron_type="jaarverslag",
    )
    with patch(
        "app.providers.identity._llm_classify_identity_and_scope",
        new=AsyncMock(return_value=("mismatch", "unknown")),
    ) as combined_mock:
        identity, scope = await LiveIdentityScopeClassifier().classify(
            "Salon Handmade", "Langstraat 8", "Weert",
            "https://www.salonhandmade.nl", finding,
        )
    assert identity == "mismatch"
    assert scope == "unknown"
    combined_mock.assert_awaited_once()


def test_company_detail_toont_identity_en_scope_classificatie(client, db_session):
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

    response = client.get(f"/batches/{batch.id}/companies/{company.id}")
    assert response.status_code == 200
    result = response.json()["agent_results"][0]
    assert result["identity_class"] == "exact_entity"
    assert result["scope_class"] == "vestiging"
