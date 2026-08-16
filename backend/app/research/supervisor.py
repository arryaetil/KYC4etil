"""Researchregie volgens het Open Deep Research-patroon.

Deze eerste productievertical voert gespecialiseerde querypaden parallel uit,
normaliseert bewijs, valideert deterministisch en levert een top 3. Een
volgende iteratie voegt de reflectie/follow-up-rondes toe zonder het
kandidaatcontract te veranderen.
"""
import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from .query_planner import QueryContext, plan_queries, plan_routes
from .ranking import (
    RankedBron,
    behoud_vestigingsanker,
    rank_bronnen,
    selecteer_bronportfolio,
)
from .types import CombinedSearchResult, PlannedQuery
from .urls import is_geen_primaire_wp_bron
from .validation import SourceDocument, valideer_bron


class ResearchTools(Protocol):
    async def search(
        self, query: PlannedQuery, max_results: int,
    ) -> list[CombinedSearchResult]: ...

    async def inspect(
        self,
        context: QueryContext,
        query: PlannedQuery,
        result: CombinedSearchResult,
    ) -> SourceDocument | None: ...


@dataclass
class ResearchOutcome:
    status: str
    kandidaten: list[RankedBron]
    onderzochte_queries: int
    onderzochte_paginas: int
    fouten: list[str]
    diagnostiek: dict = field(default_factory=dict)


class ResearchSupervisor:
    def __init__(
        self,
        tools: ResearchTools,
        max_queries: int,
        max_pages: int,
        max_results_per_query: int = 8,
        max_kandidaten: int = 3,
        reviewer=None,
    ):
        self.tools = tools
        self.max_queries = max_queries
        self.max_pages = max_pages
        self.max_results_per_query = max_results_per_query
        self.max_kandidaten = max_kandidaten
        self.reviewer = reviewer

    async def run(
        self,
        context: QueryContext,
        seed_documents: list[SourceDocument] | None = None,
        route_plan: list[dict] | None = None,
    ) -> ResearchOutcome:
        # Het plan mag van buiten komen, zodat de aanroeper het één keer
        # opstelt (inclusief de sectorprobe die registers zichzelf laat
        # identificeren) en precies hetzelfde plan aan seeds én supervisor
        # geeft. Zonder dat argument blijft het gedrag ongewijzigd.
        route_plan = route_plan if route_plan is not None else plan_routes(context)
        seed_documents = seed_documents or []
        fouten: list[str] = []
        zoekfouten_per_route: Counter = Counter()
        te_inspecteren: list[tuple[PlannedQuery, CombinedSearchResult]] = []
        geziene_urls: set[str] = {
            document.url for document in seed_documents
        }
        resultaten_per_pad: dict[
            str, list[tuple[PlannedQuery, CombinedSearchResult]]
        ] = {}

        def _route_van_document(document: SourceDocument) -> str:
            if document.research_route:
                return document.research_route
            if document.documenttype in {
                "jaarverslag", "jaarrekening", "bestuursverslag", "pdf_document",
            }:
                return "document"
            return "website"

        # DUO/DigiMV kunnen een route rechtstreeks en controleerbaar invullen.
        # Een oude of gedeelde bron telt wel mee voor adaptief stoppen, maar
        # vervangt nooit de primaire jaarlijkse zoekopdracht van die route.
        directe_routes = {
            document.research_route
            for document in seed_documents
            if (
                document.research_route
                and (
                    (document.raw_data or {}).get("route_sufficient") is True
                    or (
                        document.research_route in {"duo", "digimv", "lrk"}
                        and (document.raw_data or {}).get("seed_origin")
                        not in {"existing_source", "organization_source"}
                    )
                )
            )
        }
        route_urls: dict[str, set[str]] = {}
        bruikbaar_bij_stopbesluit: Counter = Counter()
        wp_bewijs_bij_stopbesluit: set[str] = set()
        for document in seed_documents:
            route = _route_van_document(document)
            route_urls.setdefault(route, set()).add(document.url)
            validatie = valideer_bron(document)
            if not validatie.is_afgewezen:
                bruikbaar_bij_stopbesluit[route] += 1
                if document.wp_gevonden is not None and document.bewijsfragment:
                    wp_bewijs_bij_stopbesluit.add(route)

        per_route_queries: dict[str, list[PlannedQuery]] = {}
        for query in plan_queries(context):
            if query.pad not in directe_routes:
                per_route_queries.setdefault(query.pad, []).append(query)
        routevolgorde = [item["route"] for item in route_plan]
        queries: list[PlannedQuery] = []
        vervolgindex = {route: 0 for route in per_route_queries}
        geen_nieuwe_resultaten: Counter = Counter()
        vooraf_geblokkeerd: Counter = Counter()
        stopredenen: dict[str, str] = {
            route: "rechtstreekse sectorspecifieke bron gevonden"
            for route in directe_routes
        }
        vooraf_geinspecteerd: dict[
            str, SourceDocument | BaseException | None
        ] = {}

        def _route_voldoende(route: str) -> bool:
            return (
                route in wp_bewijs_bij_stopbesluit
                or bruikbaar_bij_stopbesluit[route] >= 2
            )

        async def _zoekronde(ronde_queries: list[PlannedQuery]) -> None:
            if not ronde_queries:
                return
            responses = await asyncio.gather(*[
                self.tools.search(query, self.max_results_per_query)
                for query in ronde_queries
            ], return_exceptions=True)
            queries.extend(ronde_queries)
            vooraf_te_inspecteren: list[
                tuple[PlannedQuery, CombinedSearchResult]
            ] = []
            vooraf_per_route: dict[
                str, list[tuple[PlannedQuery, CombinedSearchResult]]
            ] = {}
            for query, results in zip(ronde_queries, responses):
                if isinstance(results, BaseException):
                    fouten.append(f"{query.pad}: {results}")
                    zoekfouten_per_route[query.pad] += 1
                    geen_nieuwe_resultaten[query.pad] += 1
                    continue
                # Filter vóór het ophalen, niet pas in de bronreview. Deze
                # domeinen worden daar toch altijd afgewezen
                # (sociaal_profiel_geen_primaire_wp_bron, 27% van alle
                # afwijzingen), maar dan is de pagina al opgehaald en door de
                # review-LLM gelezen. Wel meetellen als geblokkeerd, zodat de
                # diagnostiek laat zien dat de zoekopdracht wél iets vond.
                geblokkeerd = [r for r in results if is_geen_primaire_wp_bron(r.url)]
                if geblokkeerd:
                    vooraf_geblokkeerd[query.pad] += len(geblokkeerd)
                results = [r for r in results if not is_geen_primaire_wp_bron(r.url)]

                voor = len(route_urls.setdefault(query.pad, set()))
                route_urls[query.pad].update(
                    result.canonical_url for result in results
                )
                if len(route_urls[query.pad]) == voor:
                    geen_nieuwe_resultaten[query.pad] += 1
                else:
                    geen_nieuwe_resultaten[query.pad] = 0
                resultaten_per_pad.setdefault(query.pad, []).extend(
                    (query, result) for result in results
                )
                for result in results:
                    if result.canonical_url in vooraf_geinspecteerd:
                        continue
                    kandidaten = vooraf_per_route.setdefault(query.pad, [])
                    if len(kandidaten) >= 2:
                        break
                    kandidaten.append((query, result))

            # Lees maximaal twee nieuwe hits per route vóór het stopbesluit.
            # Round-robin voorkomt dat een klein paginabudget volledig door
            # de eerste (meestal website-)route wordt opgebruikt.
            for index in range(2):
                for query in ronde_queries:
                    kandidaten = vooraf_per_route.get(query.pad, [])
                    if index >= len(kandidaten):
                        continue
                    if len(vooraf_geinspecteerd) + len(vooraf_te_inspecteren) >= self.max_pages:
                        break
                    vooraf_te_inspecteren.append(kandidaten[index])

            vooraf_resultaten = await asyncio.gather(*[
                self.tools.inspect(context, query, result)
                for query, result in vooraf_te_inspecteren
            ], return_exceptions=True)
            for (query, result), document in zip(
                vooraf_te_inspecteren, vooraf_resultaten,
            ):
                vooraf_geinspecteerd[result.canonical_url] = document
                if isinstance(document, BaseException) or document is None:
                    continue
                validatie = valideer_bron(document)
                if validatie.is_afgewezen:
                    continue
                bruikbaar_bij_stopbesluit[query.pad] += 1
                if document.wp_gevonden is not None and document.bewijsfragment:
                    wp_bewijs_bij_stopbesluit.add(query.pad)

        # Iedere route krijgt eerst precies één kans, parallel. Daarna worden
        # alleen routes met minder dan twee unieke bronnen aangevuld.
        primaire_queries: list[PlannedQuery] = []
        for route in routevolgorde:
            routequeries = per_route_queries.get(route, [])
            if routequeries and len(primaire_queries) < self.max_queries:
                primaire_queries.append(routequeries[0])
                vervolgindex[route] = 1
        await _zoekronde(primaire_queries)

        while len(queries) < self.max_queries:
            ronde_queries = []
            for route in routevolgorde:
                routequeries = per_route_queries.get(route, [])
                index = vervolgindex.get(route, 0)
                if index >= len(routequeries):
                    continue
                if _route_voldoende(route):
                    stopredenen.setdefault(route, "bruikbaar bewijs gevonden")
                    continue
                if geen_nieuwe_resultaten[route] >= 2:
                    stopredenen.setdefault(route, "twee varianten leverden niets nieuws op")
                    continue
                if len(queries) + len(ronde_queries) >= self.max_queries:
                    break
                ronde_queries.append(routequeries[index])
                vervolgindex[route] = index + 1
            if not ronde_queries:
                break
            await _zoekronde(ronde_queries)

        for route, routequeries in per_route_queries.items():
            if route in stopredenen:
                continue
            if _route_voldoende(route):
                stopredenen[route] = "bruikbaar bewijs gevonden"
            elif vervolgindex.get(route, 0) >= len(routequeries):
                stopredenen[route] = "alleen beschikbare varianten uitgevoerd"
            elif len(queries) >= self.max_queries:
                stopredenen[route] = "centraal querybudget bereikt"

        query_aantallen = Counter(query.pad for query in queries)

        # Verdeel het paginabudget over alle zoekpaden. De oude sequentiële
        # selectie kon het hele budget vullen met de eerste websitequery,
        # waardoor jaarstukken en media nooit werden gelezen zodra het budget
        # lager werd. Round-robin bewaart diversiteit én de harde kostenlimiet.
        grootste_resultaatset = max(
            (len(results) for results in resultaten_per_pad.values()),
            default=0,
        )
        for resultaat_index in range(grootste_resultaatset):
            for results in resultaten_per_pad.values():
                if resultaat_index >= len(results):
                    continue
                query, result = results[resultaat_index]
                if result.canonical_url in geziene_urls:
                    continue
                geziene_urls.add(result.canonical_url)
                te_inspecteren.append((query, result))
                if len(te_inspecteren) >= self.max_pages:
                    break
            if len(te_inspecteren) >= self.max_pages:
                break

        nog_te_inspecteren = [
            (query, result) for query, result in te_inspecteren
            if result.canonical_url not in vooraf_geinspecteerd
        ]
        nieuwe_inspecties = await asyncio.gather(*[
            self.tools.inspect(context, query, result)
            for query, result in nog_te_inspecteren
        ], return_exceptions=True)
        nieuwe_inspecties_iter = iter(nieuwe_inspecties)
        inspected = [
            vooraf_geinspecteerd[result.canonical_url]
            if result.canonical_url in vooraf_geinspecteerd
            else next(nieuwe_inspecties_iter)
            for _, result in te_inspecteren
        ]
        inspectiefouten_per_route: Counter = Counter()
        documenten_met_route: list[tuple[SourceDocument, str]] = []
        for document in seed_documents:
            documenten_met_route.append((document, _route_van_document(document)))
        for (query, _), item in zip(te_inspecteren, inspected):
            if isinstance(item, BaseException):
                fouten.append(f"inspectie: {item}")
                inspectiefouten_per_route[query.pad] += 1
            elif item is not None:
                documenten_met_route.append((item, query.pad))
        documenten_om_te_beoordelen = [
            document for document, _ in documenten_met_route
        ]

        # Lokaal (per run) zodat gelijktijdige runs elkaar niet blokkeren; cap
        # voorkomt dat een rate-limit-fout een bron stil laat verdwijnen.
        review_semaphore = asyncio.Semaphore(5)

        async def _beoordeel(document):
            async with review_semaphore:
                if self.reviewer is not None:
                    try:
                        return await self.reviewer.review(context, document)
                    except Exception as exc:
                        return exc
                return valideer_bron(document)

        beoordelingen = await asyncio.gather(*[
            _beoordeel(document) for document in documenten_om_te_beoordelen
        ])

        validaties = []
        afwijzingen = []
        documenten = len(documenten_om_te_beoordelen)
        bruikbaar_per_route: Counter = Counter()
        for (item, route), validatie in zip(documenten_met_route, beoordelingen):
            if isinstance(validatie, BaseException):
                fouten.append(f"bronreview: {validatie}")
                continue
            validaties.append(validatie)
            if not validatie.is_afgewezen:
                bruikbaar_per_route[route] += 1
            if validatie.is_afgewezen and len(afwijzingen) < 12:
                intelligente_review = validatie.validaties.get(
                    "intelligente_review", {}
                )
                afwijzingen.append({
                    "titel": item.titel,
                    "url": item.url,
                    "identity_class": validatie.identity_class,
                    "redenen": list(validatie.afwijsredenen),
                    "review_reden": intelligente_review.get("reden"),
                })

        # Diversiteit bepaalt de vólgorde, het vestigingsanker de inhoud.
        #
        # De eerdere afweging ("bij circa vijf bronnen is een diversiteitsfilter
        # schadelijker dan behulpzaam") ging uit van korte kandidatenlijsten en
        # van een portfoliofunctie die de lijst kon laten krimpen. Beide
        # kloppen niet meer: research_max_kandidaten staat op 8, en gemeten op
        # productiedata komt bij runs met vier of meer kandidaten de mediaan
        # 100% van één domein — 39 van de 53 runs zijn volledig monocultuur.
        # De reviewer krijgt dan acht varianten van dezelfde pagina in plaats
        # van complementair bewijs. selecteer_bronportfolio vult sinds kort
        # altijd aan tot het maximum, dus er kan niets meer stil wegvallen.
        ranked = behoud_vestigingsanker(
            selecteer_bronportfolio(
                rank_bronnen(validaties), self.max_kandidaten,
            ),
            self.max_kandidaten,
        )
        reden_teller = Counter(
            reden
            for validatie in validaties
            if validatie.is_afgewezen
            for reden in validatie.afwijsredenen
        )
        route_statussen = []
        for gepland in route_plan:
            route = gepland["route"]
            query_count = query_aantallen[route]
            fout_count = (
                zoekfouten_per_route[route] + inspectiefouten_per_route[route]
            )
            if bruikbaar_per_route[route]:
                status = "afgerond"
                statusreden = "bruikbare bronnen gevonden"
            elif query_count == 0:
                status = "overgeslagen"
                statusreden = "niet uitgevoerd binnen het querybudget"
            elif query_count and zoekfouten_per_route[route] == query_count:
                status = "mislukt"
                statusreden = "alle zoekopdrachten voor deze route mislukten"
            elif fout_count and bruikbaar_per_route[route] == 0:
                status = "mislukt"
                statusreden = "bronnen konden technisch niet worden verwerkt"
            else:
                status = "afgerond"
                statusreden = "geen bruikbare bron gevonden"
            route_statussen.append({
                **gepland,
                "status": status,
                "statusreden": statusreden,
                "aantal_bronnen": bruikbaar_per_route[route],
                "aantal_queries": query_count,
            })
        technisch_onvolledig = any(
            item["verplicht"] and item["status"] in {"mislukt", "overgeslagen"}
            for item in route_statussen
        )
        resultaat_status = (
            "technisch_onvolledig"
            if technisch_onvolledig
            else "review_nodig" if ranked else "niet_gevonden"
        )
        return ResearchOutcome(
            status=resultaat_status,
            kandidaten=ranked,
            onderzochte_queries=len(queries),
            onderzochte_paginas=len(te_inspecteren),
            fouten=fouten,
            diagnostiek={
                "zoekresultaten": len(geziene_urls),
                "onderzochte_paginas": len(te_inspecteren),
                "gelezen_documenten": documenten,
                "afgewezen_documenten": sum(
                    1 for item in validaties if item.is_afgewezen
                ),
                "bruikbare_documenten": sum(
                    1 for item in validaties if not item.is_afgewezen
                ),
                "afwijsredenen": dict(reden_teller),
                "afwijzingen": afwijzingen,
                # Zoekresultaten die vóór het ophalen zijn weggefilterd omdat
                # het domein nooit primair WP-bewijs kan leveren. Apart
                # zichtbaar zodat "route vond niets" te onderscheiden blijft
                # van "route vond alleen sociale profielen".
                "vooraf_geblokkeerd": dict(vooraf_geblokkeerd),
                "adaptief_stoppen": stopredenen,
                "route_statussen": route_statussen,
            },
        )
