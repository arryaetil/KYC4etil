"""Controleer de onderwijs-testset tegen de actuele officiële DUO-bestanden.

Gebruik vanuit backend/: python -m scripts.validate_duo
"""
import asyncio
import csv
from pathlib import Path

from app.research.duo import vind_duo_personeelsbron
from app.research.query_planner import QueryContext


TESTSET = Path(__file__).resolve().parents[1] / "data" / "onderwijsgroepen_testset.csv"


async def main() -> int:
    with TESTSET.open(encoding="utf-8") as bestand:
        cases = list(csv.DictReader(bestand))
    fouten = []
    for case in cases:
        bron = await vind_duo_personeelsbron(QueryContext(
            naam=case["naam"],
            gemeente=case["gemeente"],
            adres=case["adres"],
            sbi_code=case["sbi_code"],
            gevraagd_jaar=2025,
        ))
        verwacht_codes = set(filter(None, case["verwachte_instellingscodes"].split("|")))
        gevonden_codes = set((bron.raw_data or {}).get("instellingscodes", [])) if bron else set()
        verwacht_wp = int(case["verwacht_aantal_2025"]) if case["verwacht_aantal_2025"] else None
        gevonden_wp = bron.wp_gevonden if bron else None
        gevonden_scope = bron.scope_class if bron else "onbekend"
        ok = (
            gevonden_codes == verwacht_codes
            and gevonden_wp == verwacht_wp
            and gevonden_scope == case["verwachte_scope"]
        )
        print(
            f"{'OK' if ok else 'FOUT':<4} {case['case_id']:<20} "
            f"codes={sorted(gevonden_codes)} aantal={gevonden_wp} scope={gevonden_scope}"
        )
        if not ok:
            fouten.append(case["case_id"])
    print(f"\n{len(cases) - len(fouten)}/{len(cases)} DUO-cases geslaagd")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
