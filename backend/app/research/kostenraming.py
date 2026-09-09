"""Wat kost het onderzoeken van één organisatie? Vraag het de vorige keer.

De schatting stond als twee vaste getallen in de frontend ($0,01–$0,02 per
organisatie), opgeschreven op 26-07-2026 en daarna nooit meer aangeraakt.
Sindsdien is het hoofdmodel gewisseld, zijn de DUO-, DigiMV- en LRK-routes
erbij gekomen en is de bronreview toegevoegd. Gemeten over 177 runs sinds
augustus is het werkelijke bedrag $0,015 (p10) tot $0,056 (p90), met een
mediaan van $0,034 — twee tot drie keer wat er in het scherm stond.

Elke vaste schatting van iets dat verandert loopt vroeg of laat achter. Daarom
komt het bedrag nu uit de runs die er al zijn: elke researchrun legt zijn eigen
kosten vast in `configuratie.kosten.totaal_usd`, over alle providers heen. Bij
een volgende modelwissel klopt het scherm vanzelf weer.
"""
from statistics import median

from sqlalchemy.orm import Session

from ..models import ResearchRun

# Zonder eigen historie: de gemeten bandbreedte van september 2026. Alleen een
# startwaarde voor een verse database, geen tweede waarheid.
STANDAARD_LAAG_USD = 0.015
STANDAARD_HOOG_USD = 0.056

# Onder dit aantal is een mediaan meer toeval dan meting.
MINIMUM_RUNS = 10
# Alleen de recente runs. Een cijfer van drie modellen geleden is geen betere
# schatting dan de standaardwaarde.
VENSTER_RUNS = 200


def _kosten_van(run: ResearchRun) -> float | None:
    bedrag = ((run.configuratie or {}).get("kosten") or {}).get("totaal_usd")
    if not isinstance(bedrag, (int, float)) or bedrag <= 0:
        return None
    return float(bedrag)


def kosten_per_organisatie(db: Session) -> dict:
    """Bandbreedte per organisatie, afgeleid uit eerdere runs.

    De ondergrens is niet het minimum maar het eerste deciel, en de bovengrens
    het negende: één organisatie waar niets over te vinden was en één concern
    met veertien documenten zeggen niets over wat de volgende lijst kost.
    """
    runs = (
        db.query(ResearchRun)
        .filter(ResearchRun.status == "completed")
        .order_by(ResearchRun.created_at.desc())
        .limit(VENSTER_RUNS)
        .all()
    )
    bedragen = sorted(
        bedrag for bedrag in (_kosten_van(run) for run in runs)
        if bedrag is not None
    )
    if len(bedragen) < MINIMUM_RUNS:
        return {
            "laag_usd": STANDAARD_LAAG_USD,
            "hoog_usd": STANDAARD_HOOG_USD,
            "mediaan_usd": None,
            "gebaseerd_op_runs": len(bedragen),
        }
    aantal = len(bedragen)
    return {
        "laag_usd": round(bedragen[int(aantal * 0.10)], 4),
        "hoog_usd": round(bedragen[min(int(aantal * 0.90), aantal - 1)], 4),
        "mediaan_usd": round(median(bedragen), 4),
        "gebaseerd_op_runs": aantal,
    }
