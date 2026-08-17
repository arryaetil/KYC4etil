"""Directe, openbare DigiMV-archiefkoppeling voor zorgorganisaties."""
import re
from urllib.parse import urlencode

import httpx

from .organizations import normaliseer_kvk
from .query_planner import QueryContext
from .types import CombinedSearchResult
from .urls import canonicaliseer_url


BASE_URL = "https://digimv13.desan.nl"
SEARCH_URL = f"{BASE_URL}/api/ArchiveSearch/GetArchiveSearchResult"
DOCUMENT_URL = f"{BASE_URL}/api/ArchiveSearch/GetDocument"
# Volgorde volgt de gemeten trefkans op productiedata: van de kandidaten met
# een WP-waarde haalde documenttype bestuursverslag 100% en jaarrekening 86%
# binnen 10% van de waarheid (n=2 resp. n=7 — richting, geen bewijs). Het
# verzameldocument is de gebundelde jaarverantwoording; bij Mondriaan is dat
# precies het bestand dat in juli 2.400 opleverde tegen een waarheid van 2.281.
# De accountantsverklaring bevat per definitie geen personeelscijfer en zakt
# daarom onder de inhoudelijke stukken.
_DOCUMENT_PRIORITEIT = {
    "bestuursverslag": 0,
    "jaarrekening": 1,
    "verzameldocument": 2,
    "verslag interne toezichthouder": 3,
    "accountantsverklaring (controle-, beoordelings- of samenstellingsverklaring)": 4,
    "overig": 5,
}


# Rechtsvormen staan wél in het DigiMV-tableau en niet in ons register (of
# andersom): "Mondriaan" tegenover "Stichting Mondriaan". Ze wegstrippen houdt
# de vergelijking exact — het is geen fuzzy match, alleen een genormaliseerde
# schrijfwijze van dezelfde naam.
_RECHTSVORMEN = {
    "stichting", "vereniging", "cooperatie", "cooperatieve", "bv", "nv",
    "vof", "cv", "maatschap", "holding", "groep",
}


def _normaal(value: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def _kernnaam(value: str | None) -> str:
    """Naam zonder rechtsvorm, voor een exacte vergelijking op de kern."""
    woorden = [w for w in _normaal(value).split() if w not in _RECHTSVORMEN]
    return " ".join(woorden)


def _selecteer_organisatie(
    rows: list[dict], context: QueryContext,
) -> dict | None:
    kvk = normaliseer_kvk(context.kvk_nummer)
    if kvk:
        exact = [
            row for row in rows
            if normaliseer_kvk(str(row.get("externalOrganizationId") or "")) == kvk
        ]
        if len(exact) == 1:
            return exact[0]

    kern = _kernnaam(context.naam)
    if not kern:
        return None
    exact = [row for row in rows if _kernnaam(row.get("name")) == kern]
    if context.gemeente:
        plaats = _normaal(context.gemeente)
        plaats_exact = [row for row in exact if _normaal(row.get("town")) == plaats]
        if len(plaats_exact) == 1:
            return plaats_exact[0]
    # Bewust fail-closed: meerdere naamgenoten zonder onderscheidende plaats of
    # KvK-nummer betekent dat we niet wéten welke rechtspersoon de vestiging
    # voert. Zuyderland heeft zeven ingeschreven entiteiten; er willekeurig een
    # kiezen levert een jaarrekening van de verkeerde op.
    return exact[0] if len(exact) == 1 else None


def _document_url(document_id: int, jaar: int) -> str:
    return f"{DOCUMENT_URL}?{urlencode({
        'documentId': document_id,
        'year': jaar,
        'fileNameOption': '',
        'fileName': '',
    })}"


def _kandidaat_boekjaren(gevraagd_jaar: int) -> list[int]:
    """DigiMV archiveert per boekjaar; `gevraagd_jaar` is het gevraagde verslagjaar.

    Het gevraagde verslagjaar is meteen het gezochte boekjaar, met één jaar
    speling erachter voor organisaties die het recentste boekjaar nog niet
    hebben aangeleverd (de jaarverantwoording over boekjaar X komt uiterlijk
    31 mei van X+1 binnen).

    Deze functie telde eerder twee jaar terug, omdat `gevraagd_jaar` destijds
    het peiljaar was (`batch.jaar`): op het peiljaar zelf antwoordt DigiMV met
    HTTP 500, waardoor élke aanroep stil faalde — 16 inzetten in productie, 0
    bronnen. Inmiddels geven zowel `service.py` als de monitoring `batch.jaar - 1`
    door, dus het verslagjaar zelf. Daarmee sloeg het terugtellen één jaar te
    ver door. Gemeten op 17-08-2026 bij Stichting MeanderGroep Zuid-Limburg,
    verslagjaar 2025 gevraagd:

        oude boekjaren [2024, 2023] -> "Bestuursverslag.pdf", boekjaar 2024
        nieuwe boekjaren [2025, 2024] -> "Jaarverslag 2025 definitief
                                          gestempeld", boekjaar 2025

    Het verslag over het gevraagde jaar lag er dus wél. Een aanroeper die
    alsnog een peiljaar doorgeeft, loopt niet vast: `_zoek_rijen` vangt de
    HTTP 500 op en het tweede boekjaar levert dan het bruikbare antwoord.
    """
    return [gevraagd_jaar, gevraagd_jaar - 1]


async def _zoek_rijen(client, naam: str, town: str, jaar: int) -> list[dict]:
    """Eén archiefzoekopdracht; een foutend jaar mag de route niet slopen."""
    try:
        response = await client.get(
            SEARCH_URL,
            params={"organization": naam, "town": town, "year": str(jaar)},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        rows = response.json()
    except Exception:
        return []
    return rows if isinstance(rows, list) else []


async def zoek_digimv_documenten(
    context: QueryContext,
    max_documenten: int = 3,
) -> list[CombinedSearchResult]:
    """Geef alleen documenten terug als de zorgorganisatie exact vaststaat."""
    if context.gevraagd_jaar is None:
        return []

    # Het town-filter knijpt te hard: de statutaire plaats in DigiMV is vaak een
    # andere dan de vestigingsgemeente in ons register. "Stichting Pergamijn"
    # met town=Echt-Susteren geeft nul treffers, zonder gemeente één organisatie
    # met vijf documenten. Daarom eerst mét gemeente (scherpste identificatie),
    # en pas zonder als dat niets oplevert.
    plaatsen = [context.gemeente, ""] if context.gemeente else [""]

    organisatie = None
    boekjaar = None
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        for kandidaat_jaar in _kandidaat_boekjaren(context.gevraagd_jaar):
            for plaats in plaatsen:
                rijen = await _zoek_rijen(
                    client, context.naam, plaats or "", kandidaat_jaar,
                )
                gevonden = _selecteer_organisatie(rijen, context)
                if gevonden is not None and (gevonden.get("documents") or []):
                    organisatie, boekjaar = gevonden, kandidaat_jaar
                    break
            if organisatie is not None:
                break
    if organisatie is None or boekjaar is None:
        return []

    documenten = sorted(
        organisatie.get("documents") or [],
        key=lambda item: _DOCUMENT_PRIORITEIT.get(
            str(item.get("type") or "").lower(), 99,
        ),
    )
    resultaat: list[CombinedSearchResult] = []
    geziene_bestanden: set[str] = set()
    for document in documenten:
        document_id = document.get("id")
        bestandsnaam = str(document.get("fileName") or "")
        if not document_id or not bestandsnaam:
            continue
        bestandsleutel = bestandsnaam.casefold()
        if bestandsleutel in geziene_bestanden:
            continue
        geziene_bestanden.add(bestandsleutel)
        # Het boekjaar dat de treffer opleverde, niet het peiljaar: een
        # documentlink met een jaar waarin het document niet bestaat, is dood.
        url = _document_url(int(document_id), boekjaar)
        resultaat.append(CombinedSearchResult(
            title=f"{document.get('type')}: {bestandsnaam}",
            url=url,
            canonical_url=canonicaliseer_url(url),
            snippets=[
                f"DigiMV boekjaar {boekjaar}: {organisatie.get('name')} "
                f"({organisatie.get('town') or 'plaats onbekend'})"
            ],
            providers=["digimv_direct"],
            queries=[f"DigiMV direct: {context.naam} boekjaar {boekjaar}"],
        ))
        if len(resultaat) >= max_documenten:
            break
    return resultaat
