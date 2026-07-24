"""Deterministische basisqueries; een LLM mag later alleen aanvullen."""
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .types import PlannedQuery


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


def plan_queries(context: QueryContext) -> list[PlannedQuery]:
    naam = context.naam.strip()
    gemeente = f" {context.gemeente.strip()}" if context.gemeente else ""
    domein = _domein(context.website_url)
    huidig_jaar = context.huidig_jaar or datetime.now(timezone.utc).year
    queries: list[PlannedQuery] = []

    if domein:
        queries.extend([
            PlannedQuery(
                "website",
                f'site:{domein} medewerkers personeel werknemers "over ons" team',
                "officiële websitepagina's met expliciet WP-bewijs",
            ),
            PlannedQuery(
                "website",
                f"site:{domein} nieuws medewerkers groei organisatie",
                "recente officiële organisatieberichten",
            ),
        ])

    queries.append(PlannedQuery(
        "website",
        f'"{naam}"{gemeente} medewerkers personeel werknemers team',
        "officiële website of expliciete organisatiepagina vinden",
    ))

    if context.gevraagd_jaar:
        jaar = context.gevraagd_jaar
        publicatiejaar = jaar + 1
        if domein:
            # Zodra het officiële domein bekend is, moet de exacte nieuwste
            # jaargang vóór brede zoekresultaten worden onderzocht. Anders
            # verbruiken algemene website- en documenthits het paginabudget
            # voordat deze betrouwbare query aan bod komt.
            queries.append(PlannedQuery(
                "document",
                (
                    f"site:{domein} jaarverslag {jaar} jaarrekening {jaar} "
                    f"jaarverantwoording {jaar}"
                ),
                "nieuwste formele document op het officiële domein",
            ))
        queries.extend([
            PlannedQuery(
                "document",
                f'"{naam}" jaarverslag {jaar} jaarrekening bestuursverslag pdf',
                "formeel document voor het gevraagde verslagjaar",
            ),
            PlannedQuery(
                "document",
                f'"{naam}" "annual report" {jaar} employees headcount pdf',
                "Engelstalig formeel document",
            ),
            PlannedQuery(
                "document",
                f'"{naam}" {publicatiejaar} jaarverslag {jaar} publicatie',
                "document gepubliceerd in jaar N+1 over verslagjaar N",
            ),
        ])
    queries.extend([
        PlannedQuery(
            "media",
            f'"{naam}" nieuws medewerkers personeel groei {huidig_jaar}',
            "recente media over organisatieomvang of veranderingen",
        ),
        PlannedQuery(
            "media",
            f'"{naam}" medewerkers reorganisatie overname ontslag uitbreiding',
            "recente gebeurtenissen die officiële cijfers kunnen hebben gewijzigd",
        ),
    ])

    uniek: dict[str, PlannedQuery] = {}
    for query in queries:
        uniek.setdefault(query.query, query)
    return list(uniek.values())
