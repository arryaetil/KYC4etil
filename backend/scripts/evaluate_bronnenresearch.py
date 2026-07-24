"""Meet bronvinding los van WP-extractie.

Alleen benchmarkregels met status ``verified`` tellen mee. De meegeleverde
seedregels zijn bewust ``pending_review`` totdat een domeinexpert de golden
bron en verwachte scope heeft bevestigd.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    naam: str
    gevraagd_jaar: int | None
    accepted_urls: set[str]
    status: str


@dataclass(frozen=True)
class Prediction:
    url: str
    identity_class: str | None = None


def canonicaliseer_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower().removeprefix("www."),
        path,
        query,
        "",
    ))


def laad_benchmark(path: Path) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    with path.open(newline="", encoding="utf-8") as bestand:
        for row in csv.DictReader(bestand):
            urls = {
                canonicaliseer_url(url)
                for url in row.get("accepted_urls", "").split("|")
                if url.strip()
            }
            cases.append(BenchmarkCase(
                case_id=row["case_id"],
                naam=row["naam"],
                gevraagd_jaar=int(row["gevraagd_jaar"]) if row.get("gevraagd_jaar") else None,
                accepted_urls=urls,
                status=row.get("status", "pending_review"),
            ))
    return cases


def bereken_metrics(
    cases: list[BenchmarkCase],
    predictions: dict[str, list[Prediction]],
) -> dict[str, float | int]:
    verified = [case for case in cases if case.status == "verified"]
    if not verified:
        return {
            "aantal_cases": 0,
            "top_1_accuracy": 0.0,
            "top_3_recall": 0.0,
            "wrong_entity_at_1": 0.0,
            "no_result_accuracy": 0.0,
        }

    top_1_correct = 0
    top_3_correct = 0
    wrong_entity_at_1 = 0
    no_result_cases = 0
    no_result_correct = 0

    for case in verified:
        voorspeld = predictions.get(case.case_id, [])
        voorspelde_urls = [canonicaliseer_url(item.url) for item in voorspeld]

        if not case.accepted_urls:
            no_result_cases += 1
            is_correct = not voorspeld
            top_1_correct += int(is_correct)
            top_3_correct += int(is_correct)
            no_result_correct += int(is_correct)
        else:
            accepted = {canonicaliseer_url(url) for url in case.accepted_urls}
            top_1_correct += int(bool(voorspelde_urls) and voorspelde_urls[0] in accepted)
            top_3_correct += int(any(url in accepted for url in voorspelde_urls[:3]))

        if voorspeld and voorspeld[0].identity_class == "mismatch":
            wrong_entity_at_1 += 1

    aantal = len(verified)
    return {
        "aantal_cases": aantal,
        "top_1_accuracy": top_1_correct / aantal,
        "top_3_recall": top_3_correct / aantal,
        "wrong_entity_at_1": wrong_entity_at_1 / aantal,
        "no_result_accuracy": (
            no_result_correct / no_result_cases if no_result_cases else 0.0
        ),
    }


def _laad_predictions(path: Path) -> dict[str, list[Prediction]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        case_id: [
            Prediction(item["url"], item.get("identity_class"))
            for item in items
        ]
        for case_id, items in data.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "bronnenresearch_benchmark.csv",
    )
    parser.add_argument("--predictions", type=Path, required=True)
    args = parser.parse_args()
    metrics = bereken_metrics(
        laad_benchmark(args.benchmark),
        _laad_predictions(args.predictions),
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
