import csv
import importlib.util
import sys
from collections import Counter
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"
SCRIPT = BACKEND / "scripts" / "evaluate_research_testset.py"


def _rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8-sig") as bestand:
        return list(csv.DictReader(bestand))


def _evaluator():
    spec = importlib.util.spec_from_file_location("evaluate_research_testset", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_testset_has_intended_size_and_distribution():
    cases = _rows("research_testset_v1.csv")

    assert len(cases) == 50
    assert Counter(case["cohort"] for case in cases) == {
        "legacy_mixed": 20,
        "education": 7,
        "formal_documents": 8,
        "care_branches": 15,
    }
    assert len({case["case_id"] for case in cases}) == 50
    assert {case["verification_status"] for case in cases} == {"pending_review"}


def test_sources_are_unique_valid_and_linked_to_a_case():
    cases = _rows("research_testset_v1.csv")
    sources = _rows("research_testset_sources_v1.csv")
    case_ids = {case["case_id"] for case in cases}

    assert len(sources) == 66
    assert len({source["source_id"] for source in sources}) == len(sources)
    assert {source["case_id"] for source in sources} <= case_ids
    assert all(source["url"].startswith(("https://", "http://")) for source in sources)
    assert {source["verification_status"] for source in sources} == {"pending_review"}


def test_evaluator_uses_only_verified_truth():
    evaluator = _evaluator()
    cases = [
        evaluator.Case("hit", 12, "workzame_personen", "vestiging", "exact_value", "verified"),
        evaluator.Case("none", None, "", "", "no_public_result", "verified"),
        evaluator.Case("ignored", 99, "fte", "concern", "exact_value", "pending_review"),
    ]
    sources = [
        evaluator.GoldSource("hit", evaluator.canonicaliseer_url("https://example.nl/team/"), True, "verified"),
        evaluator.GoldSource("ignored", evaluator.canonicaliseer_url("https://example.nl/old"), True, "pending_review"),
    ]
    predictions = {
        "hit": {
            "query_count": 2,
            "cost_cents": 0.4,
            "duration_ms": 1000,
            "sources": [{
                "url": "https://www.example.nl/team?utm_source=test",
                "wp": 12,
                "unit": "workzame_personen",
                "scope": "vestiging",
                "rejected": False,
            }, {
                "url": "https://example.nl/concern",
                "rejected": True,
                "rejection_reasons": ["scope_mismatch"],
            }],
        },
        "none": {"query_count": 0, "cost_cents": 0, "duration_ms": 10, "sources": []},
    }

    metrics = evaluator.bereken_metrics(cases, sources, predictions)

    assert metrics["readiness"] == {
        "total_cases": 3,
        "verified_cases": 2,
        "total_sources": 2,
        "verified_sources": 1,
    }
    assert all(value == 1.0 for value in metrics["quality"].values())
    assert metrics["efficiency"]["average_query_count"] == 1
