"""Bewaart brondocumenten, zodat het bewijs blijft bestaan als de bron verdwijnt.

Waarom dit nodig is, gemeten: van de 120 bronkaarten in de inhaalslag van
25-08-2026 waren er documenten die niet meer op te halen waren — 404, of een
domein dat het niet meer deed. Die bron ís gevonden, is beoordeeld of stond op
het punt beoordeeld te worden, en het bewijs is weg. Een organisatie vervangt
haar jaarverslag door de nieuwe editie op dezelfde URL en de onderbouwing van
vorig jaar bestaat niet meer.

De opslag is bewust dom: één bestand per bron, met de hash van de canonieke URL
als naam. Geen index, geen tabel die uit de pas kan lopen met de schijf — het
bestand is er of het is er niet. Dat maakt ook opruimen eenvoudig.

Dit is een tussenstation. De bedoeling is dat documenten uiteindelijk naar de
documentatietab in VVL gaan; tot die tijd staan ze op een Railway-volume.
"""
import hashlib
import logging
from pathlib import Path

from .config import get_settings
from .research.urls import canonicaliseer_url

logger = logging.getLogger(__name__)

# Ruimer dan wat de viewer doorlaat kan niet: wat we niet mogen tonen hoeven we
# ook niet te bewaren.
MAX_DOCUMENT_BYTES = 60 * 1024 * 1024


def opslagmap() -> Path | None:
    """De map waar documenten staan, of None als opslag uit staat.

    Leeg betekent uit: zonder volume schrijven we naar een schijf die bij de
    volgende deploy weg is, en dan is "bewaard" een loze belofte.
    """
    pad = get_settings().brondocumenten_pad
    if not pad:
        return None
    map_pad = Path(pad)
    try:
        map_pad.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("opslagmap %s niet bruikbaar: %s", pad, exc)
        return None
    return map_pad


def _bestandsnaam(url: str) -> str:
    """De canonieke URL als sleutel, zodat dezelfde bron één bestand krijgt.

    Canoniek en niet ruw: `?utm_source=...` of een trailing slash maken van
    hetzelfde document geen tweede document. Dat is dezelfde regel waarmee de
    bronkandidaten worden ontdubbeld.
    """
    sleutel = hashlib.sha256(canonicaliseer_url(url).encode("utf-8")).hexdigest()
    return f"{sleutel}.pdf"


def pad_van(url: str) -> Path | None:
    """Waar dit document zou staan, of None als opslag uit staat."""
    map_pad = opslagmap()
    return map_pad / _bestandsnaam(url) if map_pad else None


def lees(url: str) -> bytes | None:
    """Het bewaarde document, of None als we het niet hebben."""
    pad = pad_van(url)
    if pad is None or not pad.exists():
        return None
    try:
        return pad.read_bytes()
    except OSError as exc:
        logger.warning("bewaard document niet leesbaar (%s): %s", pad.name, exc)
        return None


def bewaar(url: str, inhoud: bytes) -> bool:
    """Leg dit document vast. Geeft terug of dat is gelukt.

    Een bestaand bestand wordt niet overschreven: de eerste versie die we zagen
    is de versie waarop is beoordeeld. Vervangt een organisatie haar jaarverslag
    op dezelfde URL, dan is juist de oude versie het bewijs.

    Mislukt het — volle schijf, geen rechten — dan is dat geen reden om een run
    of een weergave te laten mislukken. Bewaren is een extra, geen voorwaarde.
    """
    pad = pad_van(url)
    if pad is None or not inhoud or len(inhoud) > MAX_DOCUMENT_BYTES:
        return False
    if pad.exists():
        return True
    try:
        # Eerst naar een tijdelijke naam: een half geschreven bestand mag nooit
        # als geldig bewijs worden teruggelezen.
        tijdelijk = pad.with_suffix(".deel")
        tijdelijk.write_bytes(inhoud)
        tijdelijk.replace(pad)
        return True
    except OSError as exc:
        logger.warning("document niet te bewaren (%s): %s", pad.name, exc)
        return False


def aantal_bewaard() -> int:
    map_pad = opslagmap()
    return len(list(map_pad.glob("*.pdf"))) if map_pad else 0
