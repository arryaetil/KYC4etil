"""Vergelijkt autonome mockresearch met de legacy-ground-truth zonder API-kosten.

Gebruik vanuit backend/: python -m scripts.compare_research_workflows
"""
import asyncio
import csv
import json
from pathlib import Path

from app.research.mock_tools import MockResearchTools
from app.research.query_planner import QueryContext
from app.research.supervisor import ResearchSupervisor

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


async def vergelijk() -> dict:
    with (DATA_DIR / "testset.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    mock_data = json.loads(
        (DATA_DIR / "mock_data.json").read_text(encoding="utf-8")
    )

    results = []
    for row in rows:
        entry = mock_data[row["naam"]]
        outcome = await ResearchSupervisor(
            MockResearchTools(),
            max_queries=12,
            max_pages=30,
        ).run(QueryContext(
            naam=row["naam"],
            gemeente=row["gemeente"],
            website_url=entry.get("places", {}).get("website"),
            gevraagd_jaar=2025,
            huidig_jaar=2026,
        ))
        top = outcome.kandidaten[0] if outcome.kandidaten else None
        gevonden_raw = top.document.wp_gevonden if top else None
        bruikbaar = bool(
            top
            and top.document.eenheid == "werkzame_personen"
            and top.document.scope_class in {"vestiging", "limburg"}
        )
        gevonden = gevonden_raw if bruikbaar else None
        werkelijk = int(row["wp_werkelijk"])
        results.append({
            "naam": row["naam"],
            "werkelijk": werkelijk,
            "research_wp": gevonden,
            "research_wp_raw": gevonden_raw,
            "scope": top.document.scope_class if top else None,
            "verschil": gevonden - werkelijk if gevonden is not None else None,
            "bron": top.document.brontype if top else None,
        })

    gevonden = [item for item in results if item["research_wp"] is not None]
    exact = [item for item in gevonden if item["verschil"] == 0]
    return {
        "aantal": len(results),
        "coverage": len(gevonden) / len(results),
        "exact_match": len(exact) / len(results),
        "afwijkend": [
            item for item in results
            if item["research_wp"] is None or item["verschil"] != 0
        ],
        "resultaten": results,
    }


def main() -> int:
    resultaat = asyncio.run(vergelijk())
    print(json.dumps(resultaat, ensure_ascii=False, indent=2))
    return 0 if resultaat["coverage"] >= 0.7 else 1


if __name__ == "__main__":
    raise SystemExit(main())
