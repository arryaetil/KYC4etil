"""Seed-documenten voor de researchsupervisor: officiële website, nieuwste
formele document en (indien nodig) het jaarverslag-agent-pad.

Website- en documentzoektocht zijn onderling onafhankelijk (beide werken op
de al bekende context.website_url) en lopen daarom parallel. De
jaarverslag-agent (LangGraph, met eigen retries) wordt alleen nog aangeroepen
als de documentzoektocht nog geen document met zowel het gevraagde
verslagjaar als een WP-getal heeft opgeleverd — anders proberen twee
onafhankelijke strategieën hetzelfde te vinden."""
import asyncio
from dataclasses import replace

from .digimv import zoek_digimv_documenten
from .duo import vind_duo_personeelsbron
from .lrk import vind_lrk_bron
from .live_tools import LiveResearchTools
from .organizations import BestaandeBron
from .query_planner import QueryContext
from .types import CombinedSearchResult, PlannedQuery
from .urls import canonicaliseer_url
from .validation import SourceDocument


def _is_volledige_match(document: SourceDocument | None, gevraagd_jaar: int | None) -> bool:
    return (
        document is not None
        and gevraagd_jaar is not None
        and document.verslagjaar == gevraagd_jaar
        and document.wp_gevonden is not None
        # FTE ≠ WP: een FTE-getal mag de jaarverslag-agent nooit stilzwijgend
        # onderdrukken, want dan blijft het echte WP-getal onvindbaar.
        and document.eenheid == "werkzame_personen"
    )


async def verzamel_seed_documenten(
    tools: LiveResearchTools,
    context: QueryContext,
    actieve_routes: set[str] | None = None,
    bestaande_bronnen: list[BestaandeBron] | None = None,
) -> list[SourceDocument]:
    seed_documents: list[SourceDocument] = []
    actieve_routes = actieve_routes or {"website", "document"}

    async def _veilig(coroutine):
        try:
            return await coroutine
        except Exception:
            return None

    async def _digimv_documenten() -> list[SourceDocument]:
        resultaten = await zoek_digimv_documenten(context)
        documenten = await asyncio.gather(*[
            _veilig(tools.inspect(
                context,
                PlannedQuery(
                    "digimv", result.queries[0],
                    "rechtstreeks document uit het openbare DigiMV-archief",
                ),
                result,
            ))
            for result in resultaten
        ])
        return [
            replace(
                document,
                research_route="digimv",
                raw_data={
                    **(document.raw_data or {}),
                    "seed_origin": "digimv_direct",
                    "route_sufficient": True,
                },
            )
            for document in documenten if document is not None
        ]

    async def _bestaande_documenten() -> list[SourceDocument]:
        async def _inspecteer(bron: BestaandeBron):
            route = (
                "digimv" if bron.brontype == "digimv"
                else "media" if bron.brontype == "media"
                else "document" if bron.documenttype in {
                    "jaarverslag", "jaarrekening", "bestuursverslag", "pdf_document",
                }
                else "website"
            )
            document = await _veilig(tools.inspect(
                context,
                PlannedQuery(
                    route, "bestaande bron opnieuw controleren",
                    "eerst de bron uit een eerdere researchrun actualiseren",
                ),
                CombinedSearchResult(
                    title=bron.titel,
                    url=bron.url,
                    canonical_url=canonicaliseer_url(bron.url),
                    providers=["existing_source"],
                    queries=["bestaande bron opnieuw controleren"],
                ),
            ))
            if document is None:
                return None
            return replace(
                document,
                research_route=route,
                raw_data={
                    **(document.raw_data or {}),
                    "seed_origin": (
                        "organization_source" if bron.van_andere_vestiging
                        else "existing_source"
                    ),
                    "van_andere_vestiging": bron.van_andere_vestiging,
                },
            )

        return [
            document for document in await asyncio.gather(*[
                _inspecteer(bron) for bron in (bestaande_bronnen or [])
            ])
            if document is not None
        ]

    (
        officiele_website, nieuwste_document, duo_bron, digimv_bronnen,
        lrk_bron, oude_bronnen,
    ) = await asyncio.gather(
        _veilig(tools.find_officiele_website(context)),
        (
            _veilig(tools.find_nieuwste_officiele_document(context))
            if "document" in actieve_routes
            else asyncio.sleep(0, result=None)
        ),
        (
            _veilig(vind_duo_personeelsbron(context))
            if "duo" in actieve_routes
            else asyncio.sleep(0, result=None)
        ),
        (
            _veilig(_digimv_documenten())
            if "digimv" in actieve_routes
            else asyncio.sleep(0, result=[])
        ),
        (
            _veilig(vind_lrk_bron(context))
            if "lrk" in actieve_routes
            else asyncio.sleep(0, result=None)
        ),
        _bestaande_documenten(),
    )
    if officiele_website is not None:
        seed_documents.append(officiele_website)
    if nieuwste_document is not None:
        seed_documents.append(nieuwste_document)
    if duo_bron is not None:
        seed_documents.append(duo_bron)
    seed_documents.extend(digimv_bronnen or [])
    if lrk_bron is not None:
        seed_documents.append(lrk_bron)
    seed_documents.extend(oude_bronnen or [])

    if (
        "document" in actieve_routes
        and not any(
            _is_volledige_match(document, context.gevraagd_jaar)
            for document in [nieuwste_document, *(digimv_bronnen or [])]
        )
    ):
        jaarverslag = await _veilig(tools.find_jaarverslag(context))
        if jaarverslag is not None:
            seed_documents.append(jaarverslag)

    return seed_documents
