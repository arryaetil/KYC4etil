"""Validatiescript: draait de bronnenresearch op de testset en rapporteert
dekking, afwijking en kalibratie tegen de ground truth.

Gebruik:  python -m scripts.validate   (vanuit backend/, PROVIDER_MODE=mock)

Dit script mat tot 09-09-2026 `pipeline.runner.run_batch` — de oude
Candidate-pipeline met reconciliatie en confidence-score. Die draait nergens
meer: de API start `research.service.run_research_batch`, en er is zelfs een
test die vastlegt dat `/batches/{id}/run-legacy` een 404 geeft. De poort stond
dus op groen voor code die niemand meer uitvoert, en dat is erger dan geen
poort: hij gaf dekking aan wijzigingen die hij niet kon zien.

De drie maten zijn vertaald naar wat de werkbank nu oplevert — bronkaarten in
plaats van één kandidaatgetal:

- dekking      voor hoeveel organisaties ligt er überhaupt een WP-getal?
- afwijking    hoe ver zitten de bronnen die zichzelf als hard bewijs
               aandienen ernaast? Dat is de opvolger van "MAPE over
               🟢-records": `direct_wp_bewijs` betekent getal + citaat +
               bruikbare scope, precies wat 🟢 beweerde.
- kalibratie   als de bovenste kaart zich als hard bewijs presenteert, klopt
               die dan? Doet ze dat niet, dan belooft ze niets en valt er niets
               te weerleggen; dat telt als eerlijk.
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
from app.models import Batch, BronKandidaat, Company, ResearchRun  # noqa: E402
from app.research.service import run_research_batch  # noqa: E402

TESTSET = Path(__file__).resolve().parents[1] / "data" / "testset.csv"

DREMPEL_AFWIJKING = 0.10
STREEF_DEKKING = 0.70
STREEF_AFWIJKING = 0.10
STREEF_KALIBRATIE = 0.80


def _is_wp_getal(kandidaat: BronKandidaat) -> bool:
    return (
        kandidaat.wp_gevonden is not None
        and kandidaat.eenheid == "werkzame_personen"
    )


def _rol(kandidaat: BronKandidaat) -> str:
    """Wat deze bron volgens de ranking voor de reviewer betekent."""
    waarde = (kandidaat.validaties or {}).get("menselijke_waarde") or {}
    return waarde.get("rol", "-")


def _belooft_hard_bewijs(kandidaat: BronKandidaat) -> bool:
    """De opvolger van het 🟢-label: getal, citaat én bruikbare scope.

    Bewust de rol uit `ranking._menselijke_waarde` en geen eigen herleiding.
    Eén berekening per begrip: zou dit script zijn eigen definitie van "hard
    bewijs" hanteren, dan meet het iets anders dan de reviewer ziet staan.
    """
    return _rol(kandidaat) == "direct_wp_bewijs"


def _bronnen_van(db, company_id: str) -> list[BronKandidaat]:
    run = (
        db.query(ResearchRun)
        .filter_by(company_id=company_id, status="completed")
        .order_by(ResearchRun.created_at.desc())
        .first()
    )
    if run is None:
        return []
    return (
        db.query(BronKandidaat)
        .filter_by(research_run_id=run.id)
        .order_by(BronKandidaat.rang)
        .all()
    )


async def main() -> int:
    # De docstring hierboven zegt "PROVIDER_MODE=mock", maar `.env` staat op
    # live en die waarde wint als je hem niet expliciet overschrijft. Het
    # gevolg is geen foutmelding maar een stille nulmeting: alle twintig
    # bedrijven komen zonder WP terug en de dekking rapporteert 0% — wat eruit
    # ziet als een regressie. Liever hier hard stoppen dan een verkeerd cijfer
    # publiceren.
    from app.config import get_settings

    modus = get_settings().provider_mode
    if modus != "mock":
        print(
            f"\n❌ PROVIDER_MODE staat op '{modus}', niet op 'mock'.\n"
            "   De streefwaarden gelden voor de deterministische mockproviders;\n"
            "   in live-modus meet dit script netwerkbeschikbaarheid, niet de\n"
            "   werkbank. Draai als:  PROVIDER_MODE=mock python -m scripts.validate\n",
        )
        return 1

    Base.metadata.create_all(bind=engine)

    with open(TESTSET, encoding="utf-8") as bestand:
        rijen = list(csv.DictReader(bestand))
    ground_truth = {rij["naam"]: int(rij["wp_werkelijk"]) for rij in rijen}

    with SessionLocal() as db:
        batch = Batch(naam="validatie-testset", jaar=2026, totaal=len(rijen))
        db.add(batch)
        db.flush()
        for rij in rijen:
            db.add(Company(
                batch_id=batch.id, vestigingsnummer=rij["vestigingsnummer"],
                naam=rij["naam"], gemeente=rij["gemeente"], adres=rij["adres"],
                sbi_code=rij["sbi_code"], cb_er=rij["cb_er"] or None,
                kvk_nummer=rij["kvk_nummer"],
            ))
        db.commit()
        batch_id = batch.id

    await run_research_batch(batch_id)

    met_getal = 0
    afwijkingen_hard: list[float] = []
    kalibratie_ok = 0
    kop = f"{'organisatie':<42} {'werkelijk':>9} {'bovenste':>9} {'afw':>7}  rol bovenste bron"
    print()
    print(kop)
    print("-" * 110)

    with SessionLocal() as db:
        for company in db.query(Company).filter_by(batch_id=batch_id).all():
            werkelijk = ground_truth[company.naam]
            bronnen = _bronnen_van(db, company.id)
            met_wp = [bron for bron in bronnen if _is_wp_getal(bron)]
            if met_wp:
                met_getal += 1

            # De bovenste kaart is waar de reviewer op beslist.
            bovenste = bronnen[0] if bronnen else None
            waarde = (
                bovenste.wp_gevonden
                if bovenste is not None and _is_wp_getal(bovenste)
                else None
            )
            afwijking = (
                abs(waarde - werkelijk) / werkelijk
                if waarde is not None and werkelijk
                else None
            )

            for bron in met_wp:
                if _belooft_hard_bewijs(bron):
                    afwijkingen_hard.append(
                        abs(bron.wp_gevonden - werkelijk) / werkelijk,
                    )

            # Belooft de bovenste kaart niets hards, dan valt er niets te
            # weerleggen: dat is een eerlijke uitkomst, geen fout.
            if bovenste is not None and _belooft_hard_bewijs(bovenste):
                correct = afwijking is not None and afwijking <= DREMPEL_AFWIJKING
            else:
                correct = True
            kalibratie_ok += correct

            getal = str(waarde) if waarde is not None else "-"
            afw = f"{afwijking:.1%}" if afwijking is not None else "-"
            rol = _rol(bovenste) if bovenste is not None else "geen bron"
            waarschuwing = "" if correct else "  <- belooft hard bewijs"
            print(
                f"{company.naam:<42} {werkelijk:>9} {getal:>9} {afw:>7}  "
                f"{rol}{waarschuwing}"
            )

    aantal = len(rijen)
    dekking = met_getal / aantal
    afwijking_hard = (
        sum(afwijkingen_hard) / len(afwijkingen_hard) if afwijkingen_hard else 0.0
    )
    kalibratie = kalibratie_ok / aantal
    print("-" * 110)
    print(f"Dekking:               {dekking:.0%}  (streef >={STREEF_DEKKING:.0%})")
    print(f"Afwijking hard bewijs: {afwijking_hard:.1%}  over "
          f"{len(afwijkingen_hard)} bronnen (streef <={STREEF_AFWIJKING:.0%})")
    print(f"Kalibratie:            {kalibratie:.0%}  (streef >={STREEF_KALIBRATIE:.0%})")

    gehaald = (
        dekking >= STREEF_DEKKING
        and afwijking_hard <= STREEF_AFWIJKING
        and kalibratie >= STREEF_KALIBRATIE
    )
    print("\nResultaat: "
          + ("✅ alle streefwaarden gehaald" if gehaald
             else "❌ streefwaarden niet gehaald"))
    return 0 if gehaald else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
