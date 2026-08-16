"""Rechtstreekse LRK-koppeling voor kinderopvanglocaties.

Het Landelijk Register Kinderopvang publiceert een open CSV zonder sleutel of
registratie, tweemaal per week ververst. Waarom die bron hier de moeite waard
is: hij bevat `vestigingsnummer_houder` en `kvk_nummer_houder` en is dus
koppelbaar op precies de sleutel die het Vestigingsregister zelf gebruikt —
geen naamvergelijking, geen LLM-oordeel over identiteit.

Belangrijke beperking, bewust in code vastgelegd: `aantal_kindplaatsen` is
dagcapaciteit en géén personeelsomvang. De omrekening naar werkzame personen
loopt via de wettelijke beroepskracht-kindratio en vervolgens via de
deeltijdfactor, die in de kinderopvang hoog is. Dat is een proportionele
schatting waarvoor de kalibratie ontbreekt (geen kinderopvangorganisatie in
`data/testset.csv`), en FTE/capaciteit wordt nooit stilzwijgend naar WP
omgerekend. Deze module levert daarom bewust `wp_gevonden=None`: het aantal
vestigingen per houder is hard, het personeelsaantal is dat niet.
"""
import asyncio
import csv
import re
from io import StringIO

import requests
from pydantic import BaseModel, Field

from .organizations import normaliseer_kvk
from .query_planner import QueryContext
from .validation import SourceDocument


OPENDATA_URL = (
    "https://www.landelijkregisterkinderopvang.nl/opendata/export_opendata_lrk.csv"
)
# Publieksregister-URL voor de reviewer; de CSV zelf is geen leesbare bron.
REGISTER_URL = "https://www.landelijkregisterkinderopvang.nl/pp/StartPagina.jsf"

_MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024
_LOCATIE_CACHE: list["LrkLocatie"] | None = None

# Gastouderopvang telt niet mee voor de personeelsomvang van een houder: een
# gastouder is een zelfstandige aan huis, geen medewerker van het
# gastouderbureau. Alleen locaties met eigen beroepskrachten.
_PROFESSIONELE_TYPEN = {"KDV", "BSO", "PSZ"}

_LIMBURGSE_GEMEENTEN = {
    "beek", "beekdaelen", "beesel", "bergen", "brunssum", "echt-susteren",
    "eijsden-margraten", "gennep", "gulpen-wittem", "heerlen",
    "horst aan de maas", "kerkrade", "landgraaf", "leudal", "maasgouw",
    "maastricht", "meerssen", "mook en middelaar", "nederweert",
    "peel en maas", "roerdalen", "roermond", "simpelveld", "sittard-geleen",
    "stein", "vaals", "valkenburg aan de geul", "venlo", "venray",
    "voerendaal", "weert",
}


class LrkLocatie(BaseModel):
    """Gevalideerde rij uit het open LRK-bestand."""

    lrk_id: str = Field(min_length=1)
    type_oko: str
    naam: str = ""
    aantal_kindplaatsen: int | None = None
    status: str = ""
    woonplaats: str = ""
    gemeente: str = ""
    naam_houder: str = ""
    kvk_houder: str | None = None
    vestigingsnummer_houder: str | None = None


def _norm(value: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


# Rechtsvormen en sectorwoorden zeggen niets over wélke houder dit is. Ze
# staan bovendien in wisselende volgorde en spelling aan beide kanten:
# "Hoera Kindercentrum" tegenover "Stichting Hoera kindercentra",
# "Kinderopvang Flow" tegenover "Stichting Flow Kinderopvang". Wat overblijft
# na het strippen is de eigennaam, en die vergelijken we als verzameling zodat
# de volgorde niet uitmaakt.
_NIETSZEGGENDE_TOKENS = {
    "stichting", "vereniging", "cooperatie", "bv", "b", "v", "nv", "vof",
    "holding", "groep", "group", "en", "de", "het", "van", "der", "den",
    "kinderopvang", "kindercentrum", "kindercentra", "kinderdagverblijf",
    "opvang", "peuterspeelzaal", "peuteropvang", "bso", "kdv", "psz",
    "buitenschoolse", "dagopvang",
}


def _kerntokens(value: str | None) -> frozenset[str]:
    """Onderscheidende naamdelen, zonder rechtsvorm en sectorwoorden."""
    return frozenset(
        token for token in _norm(value).split()
        if token not in _NIETSZEGGENDE_TOKENS and len(token) > 1
    )


def _getal(value: str | None) -> int | None:
    tekst = (value or "").strip()
    return int(tekst) if tekst.isdigit() else None


def lees_locaties(data: bytes) -> list[LrkLocatie]:
    """Parseert het open LRK-bestand; alleen ingeschreven locaties."""
    tekst = data.decode("utf-8", "replace")
    locaties: list[LrkLocatie] = []
    for rij in csv.DictReader(StringIO(tekst), delimiter=";"):
        if (rij.get("status") or "").strip() != "Ingeschreven":
            continue
        lrk_id = (rij.get("lrk_id") or "").strip()
        if not lrk_id:
            continue
        locaties.append(LrkLocatie(
            lrk_id=lrk_id,
            type_oko=(rij.get("type_oko") or "").strip(),
            naam=(rij.get("actuele_naam_oko") or "").strip(),
            aantal_kindplaatsen=_getal(rij.get("aantal_kindplaatsen")),
            status="Ingeschreven",
            woonplaats=(rij.get("opvanglocatie_woonplaats") or "").strip(),
            gemeente=(rij.get("verantwoordelijke_gemeente") or "").strip(),
            naam_houder=(rij.get("naam_houder") or "").strip(),
            kvk_houder=normaliseer_kvk(rij.get("kvk_nummer_houder")),
            vestigingsnummer_houder=(
                (rij.get("vestigingsnummer_houder") or "").strip() or None
            ),
        ))
    return locaties


def vind_locaties(
    context: QueryContext, locaties: list[LrkLocatie],
) -> list[LrkLocatie]:
    """Zoekt alle locaties van dezelfde houder.

    Volgorde is bewust: vestigingsnummer en KvK-nummer zijn identiteiten,
    een naam is een gelijkenis. Pas terugvallen op de naam als er geen
    nummer beschikbaar is, en dan alleen bij een exacte genormaliseerde match
    — een gedeeltelijke match koppelt "Kinderopvang Flow" aan "Flow Zorg".
    """
    professioneel = [
        item for item in locaties if item.type_oko in _PROFESSIONELE_TYPEN
    ]

    vestigingsnummer = (context.vestigingsnummer or "").strip()
    if vestigingsnummer:
        treffers = [
            item for item in professioneel
            if item.vestigingsnummer_houder == vestigingsnummer
        ]
        if treffers:
            return treffers

    kvk = normaliseer_kvk(context.kvk_nummer)
    if kvk:
        treffers = [item for item in professioneel if item.kvk_houder == kvk]
        if treffers:
            return treffers

    naam = _norm(context.naam)
    if not naam:
        return []
    treffers = [item for item in professioneel if _norm(item.naam_houder) == naam]
    if treffers:
        return treffers

    # Eén niveau soepeler: vergelijk de onderscheidende naamdelen als
    # verzameling, zodat woordvolgorde en sectorwoorden niet meetellen. Onze
    # tokens moeten volledig in die van de houder zitten — een gedeeltelijke
    # overlap zou "Kinderopvang Flow" aan "Flow Zorg" koppelen.
    kern = _kerntokens(context.naam)
    if not kern:
        return []
    kandidaten: dict[str, list[LrkLocatie]] = {}
    for item in professioneel:
        if kern <= _kerntokens(item.naam_houder):
            kandidaten.setdefault(_norm(item.naam_houder), []).append(item)
    if len(kandidaten) == 1:
        return next(iter(kandidaten.values()))

    if len(kandidaten) > 1:
        # Sectorwoorden zijn zwak bewijs, geen géén bewijs. "Kinderopvang
        # Flow" hoort bij "Stichting Flow Kinderopvang" en niet bij "Flow Zorg
        # B.V." — precies dat onderscheid zit in het woord dat hierboven is
        # weggestript. Alleen doorslaggevend als één houder het meest
        # overlapt; een gelijkspel (kale naam "Flow") blijft ambigu.
        volledig = set(_norm(context.naam).split())
        overlap = {
            houder: len(volledig & set(houder.split()))
            for houder in kandidaten
        }
        hoogste = max(overlap.values())
        besten = [h for h, score in overlap.items() if score == hoogste]
        if len(besten) == 1:
            return kandidaten[besten[0]]

    if len(kandidaten) > 1 and context.gemeente:
        # Meerdere houders met dezelfde eigennaam ("'t Nest Kinderopvang
        # Horst" en "... Venray"). De eigen gemeente mag dat onderscheid
        # maken, maar alleen als precies één houder daar actief is.
        eigen = context.gemeente.strip().lower()
        in_gemeente = {
            houder: items for houder, items in kandidaten.items()
            if any(item.gemeente.lower() == eigen for item in items)
        }
        if len(in_gemeente) == 1:
            return next(iter(in_gemeente.values()))
    # Bewust fail-closed: meerdere houders met dezelfde naam en geen
    # onderscheidende gemeente betekent dat we niet wéten welke het is.
    return []


def _scope(context: QueryContext, treffers: list[LrkLocatie]) -> str:
    gemeenten = {item.gemeente.lower() for item in treffers if item.gemeente}
    if not gemeenten:
        return "unknown"
    eigen = (context.gemeente or "").lower()
    if eigen and gemeenten == {eigen}:
        return "vestiging"
    if gemeenten <= _LIMBURGSE_GEMEENTEN:
        return "limburg"
    return "nederland"


def bouw_lrk_bron(
    context: QueryContext, treffers: list[LrkLocatie],
) -> SourceDocument | None:
    if not treffers:
        return None
    houder = treffers[0].naam_houder or context.naam
    kindplaatsen = sum(
        item.aantal_kindplaatsen or 0 for item in treffers
    )
    per_gemeente: dict[str, int] = {}
    for item in treffers:
        per_gemeente[item.gemeente] = per_gemeente.get(item.gemeente, 0) + 1
    in_limburg = sum(
        aantal for gemeente, aantal in per_gemeente.items()
        if gemeente.lower() in _LIMBURGSE_GEMEENTEN
    )
    eigen_gemeente = (context.gemeente or "").strip()
    hier = per_gemeente.get(eigen_gemeente, 0)

    bewijs = (
        f"Het Landelijk Register Kinderopvang telt voor houder {houder} "
        f"{len(treffers)} ingeschreven opvanglocatie(s), waarvan {in_limburg} "
        f"in Limburg"
    )
    if eigen_gemeente:
        bewijs += f" en {hier} in {eigen_gemeente}"
    bewijs += (
        f". Samen goed voor {kindplaatsen} kindplaatsen. Let op: kindplaatsen "
        "zijn dagcapaciteit en geen werkzame personen — het personeelsaantal "
        "volgt uit de beroepskracht-kindratio en de deeltijdfactor en is hier "
        "bewust niet ingevuld."
    )
    return SourceDocument(
        naam=context.naam,
        company_website_url=context.website_url,
        url=REGISTER_URL,
        titel=f"Landelijk Register Kinderopvang — {houder}",
        tekst=bewijs,
        brontype="overheid",
        documenttype="lrk_locatieregister",
        gevraagd_jaar=context.gevraagd_jaar,
        # Nadrukkelijk geen WP: zie de moduledocstring. De reviewer krijgt de
        # capaciteit als context, niet als personeelsgetal.
        wp_gevonden=None,
        eenheid=None,
        bewijsfragment=bewijs,
        scope_class=_scope(context, treffers),
        research_route="lrk",
        raw_data={
            "aantal_locaties": len(treffers),
            "aantal_locaties_limburg": in_limburg,
            "aantal_locaties_eigen_gemeente": hier,
            "kindplaatsen_totaal": kindplaatsen,
            "locaties_per_gemeente": per_gemeente,
            "lrk_ids": [item.lrk_id for item in treffers],
            "brondefinitie": (
                "ingeschreven kinderdagverblijven, buitenschoolse opvang en "
                "peuterspeelzalen; gastouderopvang telt niet mee"
            ),
        },
    )


def _download_sync(url: str) -> bytes:
    # Zonder User-Agent antwoordt de LRK-server met HTTP 400. Dezelfde
    # identificatie als de rest van de applicatie, zodat de beheerder ons
    # verkeer kan herkennen.
    from ..providers.fetch import USER_AGENT

    response = requests.get(
        url, timeout=120, stream=True, headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    inhoud = bytearray()
    for blok in response.iter_content(chunk_size=1024 * 256):
        inhoud.extend(blok)
        if len(inhoud) > _MAX_DOWNLOAD_BYTES:
            raise ValueError("LRK-bestand groter dan verwacht")
    return bytes(inhoud)


async def _laad_locaties() -> list[LrkLocatie]:
    global _LOCATIE_CACHE
    if _LOCATIE_CACHE is None:
        data = await asyncio.to_thread(_download_sync, OPENDATA_URL)
        _LOCATIE_CACHE = lees_locaties(data)
    return _LOCATIE_CACHE


async def vind_lrk_bron(context: QueryContext) -> SourceDocument | None:
    """Levert één LRK-bron als de houder eenduidig is vast te stellen."""
    try:
        locaties = await _laad_locaties()
    except Exception:
        return None
    return bouw_lrk_bron(context, vind_locaties(context, locaties))
