"""Run a lightweight pipeline eval over backend/data/testset.csv.

Default mode is deterministic mock providers:

    python backend/scripts/evaluate_testset.py

Use live providers only when you explicitly want external API/network calls:

    PROVIDER_MODE=live python backend/scripts/evaluate_testset.py --provider-mode live
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.pipeline.confidence import bereken_confidence
from app.pipeline.evidence import assess_finding_evidence
from app.pipeline.reconcile import Strategie, bepaal_strategie, reconcilieer
from app.providers.base import AgentFinding, LocationInfo, PlacesResult


DEFAULT_TESTSET = ROOT / "data" / "testset.csv"
DEFAULT_OUTPUT = ROOT / "evals" / "testset_eval.jsonl"


def _providers(provider_mode: str):
    if provider_mode == "live":
        from app.providers.live import LiveJaarverslagAgent, LivePlacesProvider, LiveWebsiteAgent

        return LivePlacesProvider(), LiveWebsiteAgent(), LiveJaarverslagAgent()
    from app.providers.mock import MockJaarverslagAgent, MockLookupProvider, MockWebsiteAgent

    return MockLookupProvider(), MockWebsiteAgent(), MockJaarverslagAgent()


async def _timed(label: str, coro) -> tuple[Any, dict]:
    t0 = time.monotonic()
    try:
        result = await coro
        return result, {"status": "ok" if result else "skipped", "duration_ms": _duration_ms(t0)}
    except Exception as exc:
        return None, {"status": "error", "duration_ms": _duration_ms(t0), "error": str(exc)[:500]}


def _duration_ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


def _finding_dict(finding: AgentFinding | None) -> dict | None:
    if finding is None:
        return None
    data = asdict(finding)
    data["evidence"] = assess_finding_evidence(finding).as_dict()
    return data


def _place_dict(place: PlacesResult | None) -> dict | None:
    return asdict(place) if place else None


def _loc_dict(loc: LocationInfo | None) -> dict | None:
    return asdict(loc) if loc else None


def _error_type(expected: int | None, candidate: int | None, rec_reason: str) -> str:
    if candidate is None:
        return "no_source_found"
    if expected is None:
        return "no_baseline"
    if candidate == expected:
        return "exact_correct"
    delta = abs(candidate - expected) / max(expected, candidate)
    if delta <= 0.10:
        return "acceptable_estimate"
    reason = rec_reason.lower()
    if "niet-limburg" in reason or "landelijk" in reason or "nationaal" in reason:
        return "wrong_scope"
    return "extraction_glitch"


async def evaluate_row(row: dict[str, str], provider_mode: str, jaar: int) -> dict:
    lookup, website_agent, jaarverslag_agent = _providers(provider_mode)
    naam = row["naam"]
    expected = int(row["wp_werkelijk"]) if row.get("wp_werkelijk") else None

    place, lookup_log = await _timed("resolve_website", lookup.lookup(naam, row.get("gemeente")))
    loc, loc_log = await _timed("location_count", lookup.locations(naam, row.get("kvk_nummer")))
    website_url = (place.website if place else None)
    strategie = bepaal_strategie(
        lookup_failed=place is None and not website_url,
        count_nl=loc.count_nl if loc else None,
        count_lb=loc.count_lb if loc else None,
    )

    website_finding, website_log = await _timed(
        "website_agent",
        website_agent.run(naam, row.get("adres"), website_url, gemeente=row.get("gemeente")),
    )

    if website_finding and website_finding.zekerheid == "hoog":
        jaarverslag_finding = None
        jaarverslag_log = {
            "status": "skipped",
            "duration_ms": 0,
            "reason": "website_agent_hoog",
        }
    else:
        jaarverslag_finding, jaarverslag_log = await _timed(
            "annual_report_agent",
            jaarverslag_agent.run(naam, jaar),
        )

    rec = reconcilieer(
        website_finding,
        jaarverslag_finding,
        loc.count_nl if loc else None,
        loc.count_lb if loc else None,
    )

    confidence = None
    final_strategy = strategie.value
    if rec.finding is not None:
        score = bereken_confidence(
            rec.finding,
            n_bronnen=rec.n_bronnen,
            bronnen_consistent=rec.bronnen_consistent,
            peiljaar=jaar,
            is_schatting=rec.is_schatting,
            schatting_penalty=rec.schatting_penalty,
            locatie_bron=loc.bron if loc else "unknown",
        )
        confidence = asdict(score)
        final_strategy = (
            Strategie.DIRECT_VERWERKEN.value if score.label == "hoog"
            else Strategie.GERICHTE_CHAT.value if score.label == "middel"
            else Strategie.VOLLEDIGE_CHAT_OF_BELLIJST.value
        )

    return {
        "vestigingsnummer": row.get("vestigingsnummer"),
        "naam": naam,
        "gemeente": row.get("gemeente"),
        "adres": row.get("adres"),
        "expected_wp": expected,
        "expected_source_type": row.get("bron_verwacht"),
        "provider_mode": provider_mode,
        "place": _place_dict(place),
        "location": _loc_dict(loc),
        "website_finding": _finding_dict(website_finding),
        "annual_report_finding": _finding_dict(jaarverslag_finding),
        "candidate_wp": rec.wp_kandidaat,
        "is_estimate": rec.is_schatting,
        "reconciliation_reason": rec.reden,
        "confidence": confidence,
        "strategy": final_strategy,
        "error_type": _error_type(expected, rec.wp_kandidaat, rec.reden),
        "nodes": {
            "resolve_website": lookup_log,
            "location_count": loc_log,
            "website_agent": website_log,
            "annual_report_agent": jaarverslag_log,
        },
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--testset", type=Path, default=DEFAULT_TESTSET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--provider-mode", choices=["mock", "live"],
                        default=get_settings().provider_mode)
    parser.add_argument("--jaar", type=int, default=2025)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(args.testset.open(newline="", encoding="utf-8")))
    results = [await evaluate_row(row, args.provider_mode, args.jaar) for row in rows]

    with args.output.open("w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}
    for result in results:
        counts[result["error_type"]] = counts.get(result["error_type"], 0) + 1
    summary = {
        "provider_mode": args.provider_mode,
        "rows": len(results),
        "output": str(args.output),
        "error_type_counts": counts,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
