"""Evalueer een researchrun tegen de handmatig geverifieerde testset v1.

Alleen cases en bronnen met ``verification_status=verified`` tellen mee.
Daardoor kunnen kandidaatbronnen veilig in dezelfde set staan zonder dat ze
automatisch als grondwaarheid worden behandeld.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class Case:
    case_id: str
    expected_wp: float | None
    expected_unit: str
    expected_scope: str
    expected_outcome: str
    verification_status: str


@dataclass(frozen=True)
class GoldSource:
    case_id: str
    url: str
    expected_usable: bool
    verification_status: str


def canonicaliseer_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ])
    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower().removeprefix("www."),
        parts.path.rstrip("/") or "/",
        query,
        "",
    ))


def _getal(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def laad_cases(path: Path) -> list[Case]:
    with path.open(newline="", encoding="utf-8-sig") as bestand:
        return [
            Case(
                case_id=row["case_id"],
                expected_wp=_getal(row.get("expected_wp")),
                expected_unit=row.get("expected_unit", ""),
                expected_scope=row.get("expected_scope", ""),
                expected_outcome=row.get("expected_outcome", ""),
                verification_status=row.get("verification_status", "pending_review"),
            )
            for row in csv.DictReader(bestand)
        ]


def laad_bronnen(path: Path) -> list[GoldSource]:
    with path.open(newline="", encoding="utf-8-sig") as bestand:
        return [
            GoldSource(
                case_id=row["case_id"],
                url=canonicaliseer_url(row["url"]),
                expected_usable=row.get("expected_usable", "").lower() == "true",
                verification_status=row.get("verification_status", "pending_review"),
            )
            for row in csv.DictReader(bestand)
        ]


def laad_voorspellingen(path: Path) -> dict[str, dict[str, Any]]:
    resultaat: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as bestand:
        for regelnummer, regel in enumerate(bestand, start=1):
            if not regel.strip():
                continue
            item = json.loads(regel)
            if not item.get("case_id"):
                raise ValueError(f"case_id ontbreekt op JSONL-regel {regelnummer}")
            resultaat[item["case_id"]] = item
    return resultaat


def _ratio(teller: int, noemer: int) -> float | None:
    return teller / noemer if noemer else None


def bereken_metrics(
    cases: list[Case],
    bronnen: list[GoldSource],
    voorspellingen: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    verified_cases = [case for case in cases if case.verification_status == "verified"]
    verified_sources = [bron for bron in bronnen if bron.verification_status == "verified"]
    accepted = [bron for bron in verified_sources if bron.expected_usable]

    source_hits = 0
    accepted_hits = 0
    value_correct = unit_correct = scope_correct = 0
    value_cases = unit_cases = scope_cases = 0
    no_result_correct = no_result_cases = 0
    rejected_predictions = rejected_with_reason = 0
    query_counts: list[float] = []
    costs: list[float] = []
    durations: list[float] = []

    accepted_per_case: dict[str, set[str]] = {}
    for bron in accepted:
        accepted_per_case.setdefault(bron.case_id, set()).add(bron.url)

    for case in verified_cases:
        prediction = voorspellingen.get(case.case_id, {})
        predicted_sources = prediction.get("sources", [])
        usable_predictions = [item for item in predicted_sources if not item.get("rejected", False)]
        predicted_urls = {
            canonicaliseer_url(item["url"])
            for item in usable_predictions
            if item.get("url")
        }
        gold_urls = accepted_per_case.get(case.case_id, set())

        if gold_urls:
            source_hits += int(bool(predicted_urls & gold_urls))
            accepted_hits += len(predicted_urls & gold_urls)

        if case.expected_outcome == "no_public_result":
            no_result_cases += 1
            no_result_correct += int(not usable_predictions)

        if case.expected_wp is not None:
            value_cases += 1
            value_correct += int(any(_getal(item.get("wp")) == case.expected_wp for item in usable_predictions))
        if case.expected_unit:
            unit_cases += 1
            unit_correct += int(any(item.get("unit") == case.expected_unit for item in usable_predictions))
        if case.expected_scope:
            scope_cases += 1
            scope_correct += int(any(item.get("scope") == case.expected_scope for item in usable_predictions))

        for item in predicted_sources:
            if item.get("rejected", False):
                rejected_predictions += 1
                rejected_with_reason += int(bool(item.get("rejection_reasons")))

        for key, target in (
            ("query_count", query_counts),
            ("cost_cents", costs),
            ("duration_ms", durations),
        ):
            if prediction.get(key) is not None:
                target.append(float(prediction[key]))

    cases_with_accepted_source = sum(bool(accepted_per_case.get(case.case_id)) for case in verified_cases)
    return {
        "readiness": {
            "total_cases": len(cases),
            "verified_cases": len(verified_cases),
            "total_sources": len(bronnen),
            "verified_sources": len(verified_sources),
        },
        "quality": {
            "case_source_recall": _ratio(source_hits, cases_with_accepted_source),
            "accepted_source_recall": _ratio(accepted_hits, len(accepted)),
            "exact_value_accuracy": _ratio(value_correct, value_cases),
            "unit_accuracy": _ratio(unit_correct, unit_cases),
            "scope_accuracy": _ratio(scope_correct, scope_cases),
            "no_result_accuracy": _ratio(no_result_correct, no_result_cases),
            "rejection_reason_coverage": _ratio(rejected_with_reason, rejected_predictions),
        },
        "efficiency": {
            "average_query_count": mean(query_counts) if query_counts else None,
            "average_cost_cents": mean(costs) if costs else None,
            "average_duration_ms": mean(durations) if durations else None,
        },
    }


def main() -> None:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=data_dir / "research_testset_v1.csv")
    parser.add_argument("--sources", type=Path, default=data_dir / "research_testset_sources_v1.csv")
    parser.add_argument("--predictions", type=Path, required=True, help="Een JSON-object per regel")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    metrics = bereken_metrics(
        laad_cases(args.cases),
        laad_bronnen(args.sources),
        laad_voorspellingen(args.predictions),
    )
    uitvoer = json.dumps(metrics, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(uitvoer + "\n", encoding="utf-8")
    print(uitvoer)


if __name__ == "__main__":
    main()
