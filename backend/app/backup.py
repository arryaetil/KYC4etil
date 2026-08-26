"""Een herstelpunt van de database, op het volume en er weer af te halen.

Waarom dit bestaat: al het reviewwerk — elke beoordeling, elke opmerking, elke
gevonden bron — stond op één Railway-volume zonder enig herstelpunt. Eén
verkeerde `delete`, één migratie die misgaat, en een week werk is weg.

Bewust geen `pg_dump`: dat programma zit niet in de container, en een back-up
die alleen werkt als er toevallig een binary aanwezig is, is er geen. Dit leest
de tabellen via SQLAlchemy en schrijft ze als gecomprimeerde JSON Lines. Dat is
draagbaar, leesbaar, en te herstellen met `scripts/herstel_backup.py`.

Wees eerlijk over wat dit wel en niet is: het bestand staat op hetzelfde
platform als de database. Het beschermt tegen de werkelijke risico's — iemand
verwijdert iets, een wijziging pakt verkeerd uit — maar niet tegen het wegvallen
van Railway zelf. Daarvoor haal je het bestand er periodiek af:

    railway volume files download /data/brondocumenten/_backups/<naam> ./
"""
import gzip
import json
import logging
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import inspect, select, text

from .config import get_settings
from .database import engine

logger = logging.getLogger(__name__)

# Hoeveel herstelpunten er blijven staan. Twee weken dagelijks is genoeg om een
# fout te ontdekken die je niet meteen zag; daarboven kost het alleen ruimte.
MAX_BACKUPS = 14


def backupmap() -> Path | None:
    """Waar de back-ups staan, of None als er geen is ingesteld.

    Leeg betekent uit. Naar een niet-gemonteerde map schrijven levert een
    bestand op dat bij de volgende deploy verdwijnt, en dat is geen back-up maar
    een geruststelling.
    """
    pad = get_settings().backup_pad
    if not pad:
        return None
    map_pad = Path(pad)
    try:
        map_pad.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("backupmap %s niet bruikbaar: %s", pad, exc)
        return None
    return map_pad


def _leesbaar(waarde):
    """Datums en tijden als tekst; de rest laat JSON zelf zien."""
    if isinstance(waarde, (datetime, date)):
        return waarde.isoformat()
    if isinstance(waarde, (bytes, bytearray)):
        return waarde.decode("utf-8", "replace")
    return waarde


def maak_backup() -> Path | None:
    """Schrijf één herstelpunt weg. Geeft het pad terug, of None."""
    map_pad = backupmap()
    if map_pad is None:
        return None

    stempel = datetime.now().strftime("%Y-%m-%dT%H%M")
    doel = map_pad / f"kyc-{stempel}.jsonl.gz"
    tijdelijk = doel.with_suffix(".deel")
    tabellen = inspect(engine).get_table_names()
    tellingen: dict[str, int] = {}

    try:
        with gzip.open(tijdelijk, "wt", encoding="utf-8") as bestand:
            # Eerste regel is de inhoudsopgave: zonder dat weet een herstel niet
            # of het bestand compleet is.
            kop = {"_backup": stempel, "tabellen": tabellen}
            bestand.write(json.dumps(kop, ensure_ascii=False) + "\n")
            with engine.connect() as verbinding:
                for tabel in tabellen:
                    aantal = 0
                    resultaat = verbinding.execute(
                        select(text("*")).select_from(text(f'"{tabel}"')),
                    )
                    for rij in resultaat.mappings():
                        bestand.write(json.dumps(
                            {"_tabel": tabel,
                             "rij": {k: _leesbaar(v) for k, v in rij.items()}},
                            ensure_ascii=False,
                        ) + "\n")
                        aantal += 1
                    tellingen[tabel] = aantal
            # Sluitregel: staat die er niet, dan is het bestand afgebroken.
            bestand.write(json.dumps(
                {"_klaar": True, "tellingen": tellingen}, ensure_ascii=False,
            ) + "\n")
        tijdelijk.replace(doel)
    except Exception as exc:
        logger.exception("back-up mislukt: %s", exc)
        tijdelijk.unlink(missing_ok=True)
        return None

    _ruim_op(map_pad)
    logger.info(
        "back-up gemaakt: %s (%s rijen over %s tabellen)",
        doel.name, sum(tellingen.values()), len(tellingen),
    )
    return doel


def _ruim_op(map_pad: Path) -> None:
    bestanden = sorted(map_pad.glob("kyc-*.jsonl.gz"))
    for oud in bestanden[:-MAX_BACKUPS]:
        oud.unlink(missing_ok=True)


def bestaande_backups() -> list[Path]:
    map_pad = backupmap()
    return sorted(map_pad.glob("kyc-*.jsonl.gz")) if map_pad else []


def is_compleet(pad: Path) -> bool:
    """Eindigt dit bestand op de sluitregel?

    Een afgebroken back-up ziet er van buiten hetzelfde uit als een goede. Dit
    is het verschil tussen een herstelpunt en een vals gevoel van veiligheid.
    """
    try:
        with gzip.open(pad, "rt", encoding="utf-8") as bestand:
            laatste = None
            for regel in bestand:
                laatste = regel
        return bool(laatste) and json.loads(laatste).get("_klaar") is True
    except Exception:
        return False
