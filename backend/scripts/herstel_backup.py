"""Zet een back-up terug in een lege database.

Een back-up die je niet kunt terugzetten is er geen. Dit script bestaat zodat
dat is uitgeprobeerd voordat het nodig is, en niet op de dag dat er iets weg is.

Bewust alleen in een lege database. Terugzetten over bestaande gegevens heen is
een samenvoeging, en die gaat mis op manieren die je pas later merkt: dubbele
rijen, verwijzingen naar iets wat er niet meer is, een beoordeling die
terugkomt nadat ze was ingetrokken. Wie echt wil overschrijven, maakt eerst een
lege database aan en wijst DATABASE_URL daarheen.

## Gebruik

    cd backend
    python -m scripts.herstel_backup --toon                    # wat zit erin
    DATABASE_URL=... python -m scripts.herstel_backup <bestand> --toepassen
"""
import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text  # noqa: E402

from app.backup import bestaande_backups, is_compleet  # noqa: E402
from app.database import Base, engine  # noqa: E402
import app.models  # noqa: E402,F401  — laadt alle tabellen in Base.metadata;
#     zonder deze import maakt create_all niets aan en zet het herstel
#     nul rijen terug zonder te klagen.


def _lees(pad: Path):
    with gzip.open(pad, "rt", encoding="utf-8") as bestand:
        for regel in bestand:
            regel = regel.strip()
            if regel:
                yield json.loads(regel)


def toon(pad: Path) -> int:
    tellingen = Counter()
    kop = None
    klaar = False
    for record in _lees(pad):
        if "_backup" in record:
            kop = record
        elif "_klaar" in record:
            klaar = True
        else:
            tellingen[record["_tabel"]] += 1
    print(f"{pad.name}  ({pad.stat().st_size / 1024:.0f} kB)")
    print(f"  gemaakt op : {kop.get('_backup') if kop else 'onbekend'}")
    print(f"  compleet   : {'ja' if klaar else 'NEE — afgebroken bestand'}")
    for tabel, aantal in sorted(tellingen.items(), key=lambda x: -x[1]):
        if aantal:
            print(f"    {tabel:34} {aantal:6}")
    return 0 if klaar else 1


def herstel(pad: Path) -> int:
    if not is_compleet(pad):
        print("Dit bestand is afgebroken; niets teruggezet.")
        return 1

    Base.metadata.create_all(bind=engine)
    bestaande = inspect(engine).get_table_names()
    with engine.connect() as verbinding:
        for tabel in bestaande:
            aantal = verbinding.execute(
                text(f'SELECT COUNT(*) FROM "{tabel}"'),
            ).scalar()
            if aantal:
                print(
                    f"De database is niet leeg ({tabel} heeft {aantal} rijen).\n"
                    "Terugzetten over bestaande gegevens heen gaat mis op "
                    "manieren die je pas later merkt. Wijs DATABASE_URL naar "
                    "een lege database.",
                )
                return 1

    tellingen = Counter()
    with engine.begin() as verbinding:
        for record in _lees(pad):
            if "_tabel" not in record:
                continue
            tabel = record["_tabel"]
            if tabel not in bestaande:
                continue
            rij = record["rij"]
            kolommen = ", ".join(f'"{k}"' for k in rij)
            plaatsen = ", ".join(f":{k}" for k in rij)
            verbinding.execute(
                text(f'INSERT INTO "{tabel}" ({kolommen}) VALUES ({plaatsen})'),
                rij,
            )
            tellingen[tabel] += 1

    print(f"{sum(tellingen.values())} rijen teruggezet over "
          f"{len(tellingen)} tabellen.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bestand", nargs="?", help="pad naar een back-upbestand")
    parser.add_argument("--toon", action="store_true",
                        help="laat zien wat erin zit, zet niets terug")
    parser.add_argument("--toepassen", action="store_true",
                        help="zet de gegevens daadwerkelijk terug")
    args = parser.parse_args()

    if args.bestand:
        pad = Path(args.bestand)
    else:
        backups = bestaande_backups()
        if not backups:
            print("Geen back-ups gevonden. Staat BACKUP_PAD goed?")
            return 1
        pad = backups[-1]
        print(f"Nieuwste back-up: {pad}\n")

    if not pad.exists():
        print(f"{pad} bestaat niet")
        return 1
    if args.toepassen:
        return herstel(pad)
    return toon(pad)


if __name__ == "__main__":
    raise SystemExit(main())
