import csv
import json
from pathlib import Path

import pytest

from app.pipeline.evidence import (DirectnessClass, IdentityClass, ScopeClass,
                                   assess_finding_evidence)
from app.providers.base import AgentFinding
from scripts.evaluate_testset import evaluate_row


def test_assess_finding_evidence_mapt_bestaande_agentfinding_conservatief():
    finding = AgentFinding(
        wp_gevonden=12,
        context="Ons team bestaat uit 12 medewerkers.",
        zekerheid="hoog",
        reden="test",
        bron_url="https://voorbeeld.test/team",
        bron_type="website",
        is_limburg_specifiek=True,
        peilmoment="2026",
    )

    evidence = assess_finding_evidence(finding)

    assert evidence.identity == IdentityClass.UNKNOWN
    assert evidence.scope == ScopeClass.VESTIGING
    assert evidence.directness == DirectnessClass.DIRECTLY_STATED
    assert evidence.official_source is True
    assert evidence.freshness_year == 2026


@pytest.mark.asyncio
async def test_evaluate_row_mock_mode_geeft_json_ready_resultaat():
    row = {
        "vestigingsnummer": "V010",
        "naam": "Hallux Podotherapie",
        "gemeente": "Roermond",
        "adres": "Bredeweg 12",
        "sbi_code": "8691",
        "cb_er": "",
        "kvk_nummer": "12345610",
        "wp_werkelijk": "3",
        "bron_verwacht": "website",
    }

    result = await evaluate_row(row, provider_mode="mock", jaar=2025)

    assert result["naam"] == "Hallux Podotherapie"
    assert result["candidate_wp"] == 3
    assert result["error_type"] == "exact_correct"
    assert result["website_finding"]["evidence"]["scope"] == "vestiging"
    # Verifieer dat het resultaat zonder custom encoder als JSONL kan worden weggeschreven.
    json.dumps(result)


@pytest.mark.asyncio
async def test_evaluate_testset_eerste_rij_mock_mode():
    testset_pad = Path(__file__).resolve().parents[1] / "data" / "testset.csv"
    with open(testset_pad, newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f))

    result = await evaluate_row(row, provider_mode="mock", jaar=2025)

    assert result["vestigingsnummer"] == "V001"
    assert result["annual_report_finding"] is not None
    assert result["nodes"]["resolve_website"]["duration_ms"] >= 0
