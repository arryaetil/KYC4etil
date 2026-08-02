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
    huidig_jaar: int | None = None


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

    if domein:
        queries.extend([
            PlannedQuery(
                "website",
                f"site:{domein} medewerkers team",
                "officiële websitepagina's met expliciet WP-bewijs",
            ),
            PlannedQuery(
                "website",
                f"site:{domein} over ons organisatie",
                "officiële organisatiepagina",
            ),
        ])

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

    if context.gevraagd_jaar:
        jaar = context.gevraagd_jaar
        publicatiejaar = jaar + 1
        if domein:
            # Zodra het officiële domein bekend is, moet de nieuwste jaargang
            # vóór brede zoekresultaten worden onderzocht; anders verbruiken
            # algemene hits het paginabudget.
            queries.append(PlannedQuery(
                "document",
                f"site:{domein} jaarverslag {jaar}",
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
    return list(uniek.values())
