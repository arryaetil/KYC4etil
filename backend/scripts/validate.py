"""Validatiescript (doc §13): draait de pipeline op de testset en rapporteert
coverage, afwijking (MAPE) en confidence-kalibratie tegen de ground truth.

Gebruik:  python -m scripts.validate   (vanuit backend/, PROVIDER_MODE=mock)
"""
import asyncio
import csv
import sys
from pathlib import Path

# Windows-consoles gebruiken cp1252 standaard; forceer UTF-8 voor de ≥ en ✅ tekens
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Batch, Candidate, Company  # noqa: E402
from app.pipeline.runner import run_batch  # noqa: E402

TESTSET = Path(__file__).resolve().parents[1] / "data" / "testset.csv"


async def main() -> int:
    # De docstring hierboven zegt "PROVIDER_MODE=mock", maar `.env` staat op
    # live en die waarde wint als je hem niet expliciet overschrijft. Het
    # gevolg is geen foutmelding maar een stille nulmeting: alle twintig
    # bedrijven komen zonder WP terug en coverage rapporteert 0% — wat eruitziet
    # als een regressie in de pipeline. Liever hier hard stoppen dan een
    # verkeerd cijfer publiceren.
    from app.config import get_settings

    modus = get_settings().provider_mode
    if modus != "mock":
        print(
            f"\n❌ PROVIDER_MODE staat op '{modus}', niet op 'mock'.\n"
            "   De streefwaarden gelden voor de deterministische mockproviders;\n"
            "   in live-modus meet dit script netwerkbeschikbaarheid, niet de\n"
            "   pipeline. Draai als:  PROVIDER_MODE=mock python -m scripts.validate\n",
        )
        return 1

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    with open(TESTSET, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ground_truth = {r["naam"]: int(r["wp_werkelijk"]) for r in rows}

    batch = Batch(naam="validatie-testset", jaar=2026, totaal=len(rows))
    db.add(batch)
    db.flush()
    for r in rows:
        db.add(Company(batch_id=batch.id, vestigingsnummer=r["vestigingsnummer"],
                       naam=r["naam"], gemeente=r["gemeente"], adres=r["adres"],
                       sbi_code=r["sbi_code"], cb_er=r["cb_er"] or None,
                       kvk_nummer=r["kvk_nummer"]))
    db.commit()

    await run_batch(db, batch.id)

    gevonden, afwijkingen_groen, kalibratie_ok = 0, [], 0
    print(f"\n{'bedrijf':<42} {'werkelijk':>9} {'gevonden':>9} {'afw':>7} {'score':>6} label  strategie")
    print("-" * 110)
    for comp in db.query(Company).filter_by(batch_id=batch.id):
        cand: Candidate = comp.candidate
        truth = ground_truth[comp.naam]
        wp = cand.wp_kandidaat if cand else None
        afw = abs(wp - truth) / truth if wp else None
        if wp is not None:
            gevonden += 1
        label = cand.confidence_label if cand else "-"
        if label == "hoog" and afw is not None:
            afwijkingen_groen.append(afw)
        # kalibratie: 🟢 hoort ≤10% te zitten; 🟡/🔴 mag ernaast zitten of leeg zijn
        correct = (afw is not None and afw <= 0.10) if label == "hoog" else True
        kalibratie_ok += correct
        schat = "~" if (cand and cand.is_schatting) else " "
        print(f"{comp.naam:<42} {truth:>9} {schat}{wp if wp is not None else '-':>8} "
              f"{f'{afw:.1%}' if afw is not None else '-':>7} "
              f"{cand.confidence_score if cand else 0:>6.2f} {label:<6} {cand.strategie if cand else '-'}")

    n = len(rows)
    coverage = gevonden / n
    mape_groen = sum(afwijkingen_groen) / len(afwijkingen_groen) if afwijkingen_groen else 0.0
    kalibratie = kalibratie_ok / n
    print("-" * 110)
    print(f"Coverage:            {coverage:.0%}  (streef ≥70%)")
    print(f"MAPE 🟢-records:     {mape_groen:.1%}  over {len(afwijkingen_groen)} records (streef ≤10%)")
    print(f"Kalibratie:          {kalibratie:.0%}  (streef ≥80%)")

    ok = coverage >= 0.70 and mape_groen <= 0.10 and kalibratie >= 0.80
    print(f"\nResultaat: {'✅ alle streefwaarden gehaald' if ok else '❌ streefwaarden niet gehaald'}")
    db.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
