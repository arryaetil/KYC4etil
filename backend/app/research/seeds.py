"""Seed-documenten voor de researchsupervisor: officiële website, nieuwste
formele document en (indien nodig) het jaarverslag-agent-pad.

Website- en documentzoektocht zijn onderling onafhankelijk (beide werken op
de al bekende context.website_url) en lopen daarom parallel. De
jaarverslag-agent (LangGraph, met eigen retries) wordt alleen nog aangeroepen
als de documentzoektocht nog geen document met zowel het gevraagde
verslagjaar als een WP-getal heeft opgeleverd — anders proberen twee
onafhankelijke strategieën hetzelfde te vinden."""
import asyncio

from .live_tools import LiveResearchTools
from .query_planner import QueryContext
from .validation import SourceDocument


def _is_volledige_match(document: SourceDocument | None, gevraagd_jaar: int | None) -> bool:
    return (
        document is not None
        and gevraagd_jaar is not None
        and document.verslagjaar == gevraagd_jaar
        and document.wp_gevonden is not None
    )


async def verzamel_seed_documenten(
    tools: LiveResearchTools,
    context: QueryContext,
) -> list[SourceDocument]:
    seed_documents: list[SourceDocument] = []

    async def _veilig(coroutine):
        try:
            return await coroutine
        except Exception:
            return None

    officiele_website, nieuwste_document = await asyncio.gather(
        _veilig(tools.find_officiele_website(context)),
        _veilig(tools.find_nieuwste_officiele_document(context)),
    )
    if officiele_website is not None:
        seed_documents.append(officiele_website)
    if nieuwste_document is not None:
        seed_documents.append(nieuwste_document)

    if not _is_volledige_match(nieuwste_document, context.gevraagd_jaar):
        jaarverslag = await _veilig(tools.find_jaarverslag(context))
        if jaarverslag is not None:
            seed_documents.append(jaarverslag)

    return seed_documents
