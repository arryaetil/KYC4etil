"""Laat de registers zelf bepalen of een organisatie tot hun sector hoort.

Tussenoplossing zolang het Vestigingsregister nog geen SBI-codes aanlevert.
De routeplanner leidt de sector nu af uit SBI en anders uit trefwoorden in de
naam. Dat tweede werkt voor beschrijvende namen ("Woonzorgcentrum Amaliahof")
maar niet voor merknamen, en juist de zorg zit vol merknamen. Gemeten op de
205 monitoringorganisaties — die alle 205 géén SBI-code hebben — herkende de
naamfallback maar 14 van de 32 zorgorganisaties: Mondriaan, Envida, Sevagram,
Proteion, Daelzicht, Pergamijn, Kentalis, Philadelphia, LEVANTOgroep en Ciro
vielen er allemaal buiten.

De omkering: niet raden of we het register moeten raadplegen, maar het
register raadplegen en dát de sector laten bepalen. Wie in het DigiMV-tableau
staat, ís zorgaanbieder. Wie in het LRK staat, ís kinderopvang. Eén
HTTP-lookup, geen sleutel en geen LLM.

Gemeten op de achttien gemiste zorgorganisaties: twaalf worden alsnog
gevonden (DigiMV-dekking 14/32 → 26/32), en acht niet-zorgorganisaties
(Bakkerij Voncken, DSM-Firmenich, Rabobank, Gemeente Heerlen, Tata Steel,
Seacon, Dreessen Advocaten, Holland Casino) leveren correct niets op.

Bewust additief: zodra een SBI-code beschikbaar is, of de naam de sector al
verraadt, wordt er niets extra opgevraagd. Deze module kan dan blijven staan
zonder kosten, of zonder gevolgen verdwijnen.
"""
import asyncio
import logging

import httpx

from .query_planner import QueryContext

_LOG = logging.getLogger(__name__)

# Routes die een register zelf kan bevestigen. Website, document en media
# draaien altijd en hebben geen sectorbewijs nodig.
PROBEERBARE_ROUTES = ("digimv", "duo", "lrk")


async def _staat_in_digimv(context: QueryContext) -> bool:
    from .digimv import _kandidaat_boekjaren, _zoek_rijen

    if context.gevraagd_jaar is None:
        return False
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        for boekjaar in _kandidaat_boekjaren(context.gevraagd_jaar):
            if await _zoek_rijen(client, context.naam, "", boekjaar):
                return True
    return False


async def _staat_in_lrk(context: QueryContext) -> bool:
    from .lrk import _laad_locaties, vind_locaties

    return bool(vind_locaties(context, await _laad_locaties()))


async def _staat_in_duo(context: QueryContext) -> bool:
    from .duo import _ADRES_URLS, _VESTIGING_CACHE, _download_sync
    from .duo import _naam_tokens, lees_vestigingen, vind_vestigingen

    alle = []
    for sector in ("po", "vo", "mbo"):
        if sector not in _VESTIGING_CACHE:
            data = await asyncio.to_thread(_download_sync, _ADRES_URLS[sector])
            _VESTIGING_CACHE[sector] = await asyncio.to_thread(
                lees_vestigingen, data, sector,
            )
        alle.extend(_VESTIGING_CACHE[sector])

    treffers = vind_vestigingen(context, alle)
    if not treffers:
        return False

    # Strenger dan de DUO-route zelf. `_match_score` vraagt of ónze naam in
    # die van DUO zit; "Mondriaan" past dan op "ROC Mondriaan" in Den Haag,
    # een andere organisatie dan de GGZ-instelling in Heerlen. Voor de route
    # is dat te overzien — `bouw_duo_bron` eist daarna instellingscodes en de
    # reviewer toetst de identiteit. Voor een sectorprobe niet: één valse
    # treffer voegt een hele route toe en verbruikt querybudget.
    #
    # Daarom symmetrisch: ook hún onderscheidende naamdelen moeten in de onze
    # zitten. "Stichting Yuverta" ↔ "Yuverta" overleeft dat (stichting is een
    # stopwoord), "Mondriaan" ↔ "ROC Mondriaan" niet.
    onze_tokens = _naam_tokens(context.naam)
    return any(
        _naam_tokens(item.naam) and _naam_tokens(item.naam) <= onze_tokens
        for item in treffers
    )


_PROBES = {
    "digimv": (
        _staat_in_digimv,
        "het DigiMV-tableau kent deze organisatie als zorgaanbieder",
    ),
    "duo": (
        _staat_in_duo,
        "DUO kent deze organisatie als onderwijsinstelling",
    ),
    "lrk": (
        _staat_in_lrk,
        "het Landelijk Register Kinderopvang kent deze houder",
    ),
}


async def verrijk_routeplan(
    context: QueryContext, routes: list[dict],
) -> list[dict]:
    """Vul het routeplan aan met registers die de organisatie zelf kennen.

    Raakt het bestaande plan niet aan: routes die de planner al toekende
    blijven staan zoals ze zijn, inclusief hun `verplicht`-vlag.
    """
    # Met een SBI-code is de planner betrouwbaar; dan geen extra verkeer.
    if (context.sbi_code or "").strip():
        return routes

    aanwezig = {item["route"] for item in routes}
    ontbrekend = [r for r in PROBEERBARE_ROUTES if r not in aanwezig]
    if not ontbrekend:
        return routes

    async def _veilig(route: str) -> tuple[str, bool]:
        probe, _ = _PROBES[route]
        try:
            return route, await probe(context)
        except Exception as exc:
            # Een onbereikbaar register mag de researchrun niet blokkeren; we
            # verliezen dan alleen de aanvulling, niet het plan.
            _LOG.warning(
                "sectorprobe %s mislukt voor %s (%s)",
                route, context.naam, type(exc).__name__,
            )
            return route, False

    uitkomsten = await asyncio.gather(*[_veilig(r) for r in ontbrekend])

    aangevuld = list(routes)
    # Media staat per conventie achteraan; sectorroutes horen ervóór.
    for route, gevonden in uitkomsten:
        if not gevonden:
            continue
        _, reden = _PROBES[route]
        aangevuld.append({
            "route": route,
            # Niet verplicht: dit is een aanvulling op een plan dat zonder
            # SBI-code is opgesteld, geen harde eis aan de run.
            "verplicht": False,
            "status": "wachtend",
            "reden": reden,
            "herkomst": "sectorprobe",
        })
    if len(aangevuld) == len(routes):
        return routes
    media = [item for item in aangevuld if item["route"] == "media"]
    overig = [item for item in aangevuld if item["route"] != "media"]
    return overig + media
