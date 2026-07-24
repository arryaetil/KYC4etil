"""Tests voor reproduceerbare bronvindingsmetrics."""
from scripts.evaluate_bronnenresearch import BenchmarkCase, Prediction, bereken_metrics


def test_bereken_metrics_scheidt_top1_top3_en_verkeerde_entiteit():
    cases = [
        BenchmarkCase(
            case_id="klein-1",
            naam="Kleine Organisatie",
            gevraagd_jaar=None,
            accepted_urls={"https://klein.example/team"},
            status="verified",
        ),
        BenchmarkCase(
            case_id="groot-1",
            naam="Grote Organisatie",
            gevraagd_jaar=2025,
            accepted_urls={"https://groot.example/jaarverslag-2025.pdf"},
            status="verified",
        ),
        BenchmarkCase(
            case_id="geen-1",
            naam="Geen Openbare Bron",
            gevraagd_jaar=2025,
            accepted_urls=set(),
            status="verified",
        ),
        BenchmarkCase(
            case_id="concept-1",
            naam="Nog te reviewen",
            gevraagd_jaar=2025,
            accepted_urls={"https://concept.example/bron"},
            status="pending_review",
        ),
    ]
    predictions = {
        "klein-1": [
            Prediction("https://klein.example/team", "exact_entity"),
        ],
        "groot-1": [
            Prediction("https://verkeerd.example/rapport.pdf", "mismatch"),
            Prediction("https://groot.example/jaarverslag-2025.pdf", "exact_entity"),
        ],
        "geen-1": [],
        "concept-1": [
            Prediction("https://concept.example/bron", "exact_entity"),
        ],
    }

    metrics = bereken_metrics(cases, predictions)

    assert metrics["aantal_cases"] == 3
    assert metrics["top_1_accuracy"] == 2 / 3
    assert metrics["top_3_recall"] == 1.0
    assert metrics["wrong_entity_at_1"] == 1 / 3
    assert metrics["no_result_accuracy"] == 1.0
