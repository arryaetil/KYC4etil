"""Eenmalig: lees alsnog het WP-getal uit bronkaarten die er geen hebben.

De monitoring leest sinds 17-08-2026 het WP-getal uit het gevonden jaarverslag,
maar dat gebeurt pas nadat is vastgesteld dát er een bronkaart komt. Kaarten die
daarvóór zijn aangemaakt bestonden al en hun URL verandert niet meer, dus elke
volgende ronde kwam uit op "ongewijzigd" en ze bleven leeg. De reviewer moest
die documenten met de hand openen.

`check_company_jaarverslag` haalt dit sinds vandaag zelf in, maar pas bij een
volgende ronde — en zo'n ronde doet per organisatie ook een zoekopdracht. Dit
script slaat dat over: de URL is al bekend, dus alleen de extractie draait.
Ongeveer 1 cent per document.

Wat er niet gebeurt: een bestaand getal overschrijven, of een kaart aanraken die
al is doorzocht. Een verslag zonder personeelsgetal wordt één keer doorzocht en
daarna met rust gelaten; dat is wat de markering `wp_extractie` vastlegt.

## Gebruik

Standaard een droogloop; er wordt niets geschreven zonder `--toepassen`.

    cd backend
    PROVIDER_MODE=live python -m scripts.backfill_wp_uit_bronkaarten
    PROVIDER_MODE=live python -m scripts.backfill_wp_uit_bronkaarten --toepassen
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models import BronKandidaat, Company  # noqa: E402
from app.pipeline.monitoring import (  # noqa: E402
    WP_EXTRACTIE,
    _markeer_wp_gezocht,
)
from app.providers import get_providers  # noqa: E402


def _te_doen(db) -> list[BronKandidaat]:
    """Bronkaarten zonder getal die nog nooit zijn doorzocht."""
    kandidaten = (
        db.query(BronKandidaat)
        .filter(
            BronKandidaat.wp_gevonden.is_(None),
            BronKandidaat.brontype == "jaarverslag",
            BronKandidaat.url.isnot(None),
        )
        .order_by(BronKandidaat.created_at)
        .all()
    )
    return [
        kandidaat for kandidaat in kandidaten
        if not (kandidaat.validaties or {}).get(WP_EXTRACTIE)
    ]


async def _verwerk(kandidaat: BronKandidaat, naam: str, agent):
    """(uitkomst, gelezen) — gelezen zegt of het document überhaupt open ging.

    Die twee moeten uit elkaar. `run_met_bron` geeft None terug in twee
    gevallen die niets met elkaar te maken hebben: het document was niet op te
    halen (404, time-out — dan weten we niets), of het is netjes gelezen en er
    stond geen personeelsgetal in (dan weten we juist wél iets).

    Alleen het tweede geval mag als "doorzocht" worden gemarkeerd. Het eerste
    hoort een volgende keer opnieuw geprobeerd te worden, want een verlopen
    certificaat of een tijdelijke storing is geen antwoord.
    """
    try:
        return await agent.run_met_bron(naam, kandidaat.url), True
    except Exception as exc:
        print(f"    niet op te halen ({type(exc).__name__}: {str(exc)[:110]})")
        return None, False


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toepassen", action="store_true",
                        help="schrijf de gevonden getallen weg")
    parser.add_argument("--maximum", type=int, default=0,
                        help="stop na dit aantal documenten (0 = alles)")
    args = parser.parse_args()

    _, _, jaarverslag_agent, _ = get_providers()
    db = SessionLocal()
    gevonden = leeg = mislukt = 0
    try:
        kandidaten = _te_doen(db)
        if args.maximum:
            kandidaten = kandidaten[:args.maximum]
        print(f"{len(kandidaten)} bronkaarten zonder WP-getal en zonder eerdere poging\n")

        for kandidaat in kandidaten:
            company = db.get(Company, kandidaat.company_id)
            naam = company.naam if company else "onbekend"
            print(f"  {naam[:40]:42} {kandidaat.url[:70]}")
            uitkomst, gelezen = await _verwerk(kandidaat, naam, jaarverslag_agent)
            if not gelezen:
                mislukt += 1
                continue
            if uitkomst is None or uitkomst.wp_gevonden is None:
                # Gelezen, maar er stond niets bruikbaars in. Dat is een
                # uitkomst en geen mislukking; markeren voorkomt dat hetzelfde
                # document elke ronde opnieuw wordt doorzocht.
                leeg += 1
                print("    geen WP-getal in dit document")
                if args.toepassen:
                    _markeer_wp_gezocht(kandidaat, gevonden=False)
                continue
            gevonden += 1
            print(f"    {uitkomst.wp_gevonden} WP"
                  f"{f', pagina {uitkomst.bron_pagina}' if uitkomst.bron_pagina else ''}")
            if args.toepassen:
                kandidaat.wp_gevonden = uitkomst.wp_gevonden
                kandidaat.eenheid = (
                    "fte" if uitkomst.is_fte else "werkzame_personen"
                )
                kandidaat.bewijsfragment = uitkomst.context
                kandidaat.bron_pagina = uitkomst.bron_pagina
                kandidaat.informatie_peilmoment = (
                    kandidaat.informatie_peilmoment or uitkomst.peilmoment
                )
                _markeer_wp_gezocht(kandidaat, gevonden=True)

        if args.toepassen:
            db.commit()
    finally:
        db.close()

    print(
        f"\n{gevonden} met een getal, {leeg} zonder, {mislukt} mislukt."
        + ("" if args.toepassen else "\nDroogloop — niets weggeschreven."
                                     " Draai opnieuw met --toepassen.")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
