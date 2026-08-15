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
_DOCUMENT_PRIORITEIT = {
    "bestuursverslag": 0,
    "jaarrekening": 1,
    "accountantsverklaring (controle-, beoordelings- of samenstellingsverklaring)": 2,
    "verslag interne toezichthouder": 3,
}


def _normaal(value: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


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

    naam = _normaal(context.naam)
    exact = [row for row in rows if _normaal(row.get("name")) == naam]
    if context.gemeente:
        plaats = _normaal(context.gemeente)
        plaats_exact = [row for row in exact if _normaal(row.get("town")) == plaats]
        if len(plaats_exact) == 1:
            return plaats_exact[0]
    return exact[0] if len(exact) == 1 else None


def _document_url(document_id: int, jaar: int) -> str:
    return f"{DOCUMENT_URL}?{urlencode({
        'documentId': document_id,
        'year': jaar,
        'fileNameOption': '',
        'fileName': '',
    })}"


async def zoek_digimv_documenten(
    context: QueryContext,
    max_documenten: int = 3,
) -> list[CombinedSearchResult]:
    """Geef alleen documenten terug als de zorgorganisatie exact vaststaat."""
    if context.gevraagd_jaar is None:
        return []
    params = {
        "organization": context.naam,
        "town": context.gemeente or "",
        "year": str(context.gevraagd_jaar),
    }
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        response = await client.get(
            SEARCH_URL, params=params, headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        rows = response.json()
    if not isinstance(rows, list):
        return []
    organisatie = _selecteer_organisatie(rows, context)
    if organisatie is None:
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
        url = _document_url(int(document_id), context.gevraagd_jaar)
        resultaat.append(CombinedSearchResult(
            title=f"{document.get('type')}: {bestandsnaam}",
            url=url,
            canonical_url=canonicaliseer_url(url),
            snippets=[
                f"DigiMV {context.gevraagd_jaar}: {organisatie.get('name')} "
                f"({organisatie.get('town') or 'plaats onbekend'})"
            ],
            providers=["digimv_direct"],
            queries=[f"DigiMV direct: {context.naam} {context.gevraagd_jaar}"],
        ))
        if len(resultaat) >= max_documenten:
            break
    return resultaat
