"""Deterministische basisqueries; een LLM mag later alleen aanvullen."""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .types import PlannedQuery

_ADMINISTRATIEVE_NAAMDELEN = {
    "afdeling", "filiaal", "groepswoning", "locatie", "regio", "unit",
    "vestiging", "woongroep", "woonzorgcentrum", "zorgcentrum",
}


@dataclass(frozen=True)
class QueryContext:
    naam: str
    gevraagd_jaar: int | None = None
    website_url: str | None = None
    gemeente: str | None = None
    adres: str | None = None
    huidig_jaar: int | None = None
    sbi_code: str | None = None
    sbi_omschrijving: str | None = None
    kvk_nummer: str | None = None


def plan_routes(context: QueryContext) -> list[dict]:
    """Kleine beslistabel voor redelijke onderzoeksroutes.

    Dit is bewust geen AI-planner. SBI bepaalt de drie profielen waar nu een
    concrete sectorspecifieke route voor bekend is; onbekende bedrijven
    houden het bestaande website/document/media-plan.

    KvK-verrijking levert niet altijd een SBI-code op (mislukte lookup,
    net ingeschreven bedrijf, handmatig aangeleverde testrijen). Daarom
    kijken de trefwoorden hieronder zowel naar `sbi_omschrijving` als naar de
    bedrijfsnaam zelf — een "Hospice de Ark" of "Woonzorgcentrum Amaliahof"
    is ook zonder SBI-code herkenbaar als zorgaanbieder. Dit is een fallback,
    geen vervanging: een SBI-treffer blijft leidend, en een generieke naam
    zonder sectorwoord (bijvoorbeeld een merknaam) wordt terecht niet
    herkend — dat is dan aan de reviewer.
    """
    sbi = (context.sbi_code or "").replace(".", "").strip()
    naam_en_omschrijving = (
        f"{context.sbi_omschrijving or ''} {context.naam}"
    ).lower()
    onderwijs = sbi.startswith("85") or any(
        woord in naam_en_omschrijving
        for woord in (
            "onderwijs", "school", "college", "universiteit", "hogeschool",
            "opleiding",
        )
    )
    zorg = sbi.startswith(("86", "87", "88")) or any(
        woord in naam_en_omschrijving
        for woord in (
            "zorg", "ziekenhuis", "verpleging", "welzijn", "hospice",
            "kliniek", "revalidatie", "psychogeriatrie", "gehandicapt",
            "groepswoning",
        )
    )
    lokale_zorgpraktijk = sbi.startswith(("862", "8691", "8692")) or any(
        woord in naam_en_omschrijving
        for woord in (
            "tandarts", "huisarts", "fysiotherap", "verloskund",
            "podotherap", "orthodont",
        )
    )
    institutionele_zorg = zorg and not lokale_zorgpraktijk
    lokale_teamdienst = lokale_zorgpraktijk or sbi.startswith("9602") or any(
        woord in naam_en_omschrijving
        for woord in ("kapper", "haarverzorging", "schoonheidsverzorging")
    )

    routes = [{
        "route": "website",
        "verplicht": True,
        "status": "wachtend",
        "reden": "officiële website en organisatiepagina's",
    }]
    if not lokale_teamdienst:
        routes.append({
            "route": "document",
            "verplicht": onderwijs or institutionele_zorg,
            "status": "wachtend",
            "reden": (
                "formele documenten zijn een kernbron voor dit profiel"
                if onderwijs or institutionele_zorg
                else "formele documenten onderzoeken wanneer beschikbaar"
            ),
        })
    if onderwijs:
        routes.append({
            "route": "duo",
            "verplicht": True,
            "status": "wachtend",
            "reden": "DUO publiceert instellings- en personeelsgegevens",
        })
    if zorg:
        routes.append({
            "route": "digimv",
            "verplicht": institutionele_zorg,
            "status": "wachtend",
            "reden": (
                "DigiMV is een kernbron voor institutionele zorg"
                if institutionele_zorg
                else "DigiMV onderzoeken wanneer de lokale zorgpraktijk erin voorkomt"
            ),
        })
    if lokale_teamdienst:
        routes.append({
            "route": "team_afspraak",
            "verplicht": True,
            "status": "wachtend",
            "reden": "team- en afspraakmodules tonen vaak de werkzame personen",
        })
    routes.append({
        "route": "media",
        "verplicht": True,
        "status": "wachtend",
        "reden": "aanvullende openbare context en personeelsinformatie",
    })
    return routes


def _domein(url: str | None) -> str | None:
    if not url:
        return None
    return urlsplit(url).netloc.lower().removeprefix("www.") or None


def vereenvoudigde_zoeknaam(naam: str) -> str | None:
    """Verwijder administratieve labels/codes, maar behoud de eigennaam."""
    ascii_naam = unicodedata.normalize("NFKD", naam).encode(
        "ascii", "ignore",
    ).decode("ascii")
    tokens = re.findall(r"[A-Za-z0-9]+", ascii_naam)
    bruikbaar = [
        token for token in tokens
        if (
            token.lower() not in _ADMINISTRATIEVE_NAAMDELEN
            and not token.isdigit()
            and len(token) > 1
        )
    ]
    vereenvoudigd = " ".join(bruikbaar).strip()
    if not vereenvoudigd or vereenvoudigd.lower() == ascii_naam.strip().lower():
        return None
    return vereenvoudigd


def plan_queries(context: QueryContext) -> list[PlannedQuery]:
    """Bouwt korte, gerichte zoekopdrachten.

    Gemeten op de jaarverslagzoeker (tien organisaties die aantoonbaar
    publiceren): een query met de naam tussen aanhalingstekens plus een stapel
    synoniemen scoorde 2/10, een beknopte variant 8/10. De index matcht dan op
    de trefwoorden in plaats van op de organisatie. Daarom hier: geen exacte
    frase om de naam, hooguit twee verwante termen per query, en het jaartal
    één keer. De breedte zit in het aantal query's, niet in de lengte ervan."""
    naam = context.naam.strip()
    gemeente = f" {context.gemeente.strip()}" if context.gemeente else ""
    domein = _domein(context.website_url)
    huidig_jaar = context.huidig_jaar or datetime.now(timezone.utc).year
    queries: list[PlannedQuery] = []
    actieve_routes = {item["route"] for item in plan_routes(context)}

    if domein:
        queries.extend([
            PlannedQuery(
                "website",
                f"site:{domein} {naam} medewerkers team",
                "officiële websitepagina's met expliciet WP-bewijs",
            ),
            PlannedQuery(
                "website",
                f"site:{domein} {naam} over ons organisatie",
                "officiële organisatiepagina",
            ),
        ])

    # Sectorspecifieke routes komen vóór de bredere documentqueries, zodat
    # iedere verplichte route ook bij een klein querybudget minstens één kans
    # krijgt.
    if "duo" in actieve_routes:
        queries.append(PlannedQuery(
            "duo",
            f"site:duo.nl/open_onderwijsdata {naam} personeel",
            "DUO-instellings- en personeelsgegevens",
        ))
    if "digimv" in actieve_routes:
        queries.append(PlannedQuery(
            "digimv",
            f"site:digimv13.desan.nl {naam}",
            "DigiMV-archief en zorgverantwoording",
        ))
    if "team_afspraak" in actieve_routes:
        if domein:
            queries.append(PlannedQuery(
                "team_afspraak",
                f"site:{domein} team medewerkers afspraak boeken",
                "team- of afspraakmodule op de officiële website",
            ))
        else:
            queries.append(PlannedQuery(
                "team_afspraak",
                f"{naam}{gemeente} team afspraak medewerker kiezen",
                "team- of afspraakmodule vinden",
            ))

    queries.append(PlannedQuery(
        "website",
        f"{naam}{gemeente} medewerkers team",
        "officiële website of expliciete organisatiepagina vinden",
    ))
    zoekalias = vereenvoudigde_zoeknaam(naam)
    if zoekalias:
        queries.append(PlannedQuery(
            "website",
            f"{zoekalias}{gemeente} medewerkers team",
            "openbare bronnen onder de naam zonder administratieve code",
        ))

    if context.gevraagd_jaar and "document" in actieve_routes:
        jaar = context.gevraagd_jaar
        publicatiejaar = jaar + 1
        if domein:
            # Zodra het officiële domein bekend is, moet de nieuwste jaargang
            # vóór brede zoekresultaten worden onderzocht; anders verbruiken
            # algemene hits het paginabudget.
            queries.append(PlannedQuery(
                "document",
                f"site:{domein} {naam} jaarverslag {jaar}",
                "nieuwste formele document op het officiële domein",
            ))
        queries.extend([
            PlannedQuery(
                "document",
                f"{naam} jaarverslag pdf",
                "formeel document voor het gevraagde verslagjaar",
            ),
            PlannedQuery(
                "document",
                f"{naam} jaarrekening {jaar}",
                "jaarrekening als het jaarverslag ontbreekt",
            ),
            PlannedQuery(
                "document",
                # Overheden publiceren geen jaarverslag maar jaarstukken.
                f"{naam} jaarstukken filetype:pdf",
                "jaarstukken van gemeenten, provincies en waterschappen",
            ),
            PlannedQuery(
                "document",
                f"{naam} annual report pdf",
                "Engelstalig formeel document",
            ),
            PlannedQuery(
                "document",
                f"{naam} jaarverslag gepubliceerd {publicatiejaar}",
                "document gepubliceerd in jaar N+1 over verslagjaar N",
            ),
        ])
    if "media" in actieve_routes:
        queries.extend([
            PlannedQuery(
                "media",
                f"{naam} nieuws medewerkers {huidig_jaar}",
                "recente media over organisatieomvang of veranderingen",
            ),
            PlannedQuery(
                "media",
                f"{naam} reorganisatie overname",
                "recente gebeurtenissen die officiële cijfers kunnen hebben gewijzigd",
            ),
        ])

    uniek: dict[str, PlannedQuery] = {}
    for query in queries:
        uniek.setdefault(query.query, query)
    per_route: dict[str, list[PlannedQuery]] = {}
    for query in uniek.values():
        per_route.setdefault(query.pad, []).append(query)
    routevolgorde = [item["route"] for item in plan_routes(context)]
    geordend: list[PlannedQuery] = []
    grootste_route = max((len(items) for items in per_route.values()), default=0)
    for index in range(grootste_route):
        for route in routevolgorde:
            routequeries = per_route.get(route, [])
            if index < len(routequeries):
                geordend.append(routequeries[index])
    return geordend
