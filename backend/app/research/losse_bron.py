"""Eén bron uitlezen voor één vestiging, buiten een volledige researchrun om.

Twee plekken leveren een bron aan die niet uit het zoeken komt: de reviewer die
zelf een URL toevoegt, en de reviewer die een jaarverslag uploadt dat de agent
niet heeft gevonden. Allebei hadden ze tot nu toe hetzelfde probleem — de bron
werd vastgelegd maar nooit gelezen, dus stond er een kaart zonder WP-getal,
zonder citaat en zonder paginanummer. Als bewijs is dat niets waard.

Het lezen zelf is hetzelfde werk als in een researchrun (`tools.inspect`) en
dezelfde weging (`valideer_bron` + `rank_bronnen`). Alleen het oordeel over
"hoort deze bron hier thuis" verschilt, en daarom staat dat hier apart: zie
`valideer_reviewersbron`.
"""
import logging
from dataclasses import replace
from datetime import datetime, timezone

from ..config import get_settings
from ..models import BronKandidaat, Company, ResearchRun
from .live_tools import LiveResearchTools
from .mock_tools import MockResearchTools
from .query_planner import QueryContext
from .ranking import RankedBron, rank_bronnen
from .types import CombinedSearchResult, PlannedQuery
from .urls import canonicaliseer_url
from .validation import BronValidatie, SourceDocument, valideer_bron

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Sleutel op `validaties`: deze bron komt van de reviewer, niet uit het zoeken.
# De kaart mag dat zeggen, en de ranking mag er niet op vertrouwen alsof de
# agent hem heeft gevonden.
AANGEDRAGEN = "aangedragen_door_reviewer"
# Wat `valideer_bron` zou hebben afgewezen, maar wat hier een voorbehoud wordt.
VOORBEHOUD = "voorbehoud_bij_aangedragen_bron"

# Een afwijsreden is geen waarschuwingssleutel. Zonder deze vertaling kwamen
# de motieven als losse chips op de kaart ("verkeerd verslagjaar"), in andere
# woorden en op een andere hoogte dan de regel die hetzelfde al zegt. `None`
# betekent: geen eigen chip, het staat elders op de kaart.
_WAARSCHUWING_VOOR_AFWIJZING = {
    # Dezelfde sleutel als de batchflow en de monitoring zetten; de regel
    # Verslagjaar noemt beide jaartallen al.
    "verkeerd verslagjaar": "afwijkend_verslagjaar",
    # Spreekt zich uit via `identity_class` hieronder: de regel Bedrijf zegt
    # dan "Mogelijk ander bedrijf".
    "verkeerde organisatie": None,
}


def context_van_company(
    company: Company,
    gevraagd_jaar: int | None,
) -> QueryContext:
    """Dezelfde vestigingscontext als een researchrun gebruikt."""
    return QueryContext(
        naam=company.naam,
        gevraagd_jaar=gevraagd_jaar,
        website_url=company.website_url or (
            company.enrichment.website_url if company.enrichment else None
        ),
        gemeente=company.gemeente,
        adres=company.adres,
        sbi_code=company.sbi_code,
        sbi_omschrijving=company.sbi_omschrijving,
        kvk_nummer=company.kvk_nummer,
        vestigingsnummer=company.vestigingsnummer,
    )


def gevraagd_jaar_van(company: Company) -> int | None:
    """Het verslagjaar waar deze lijst om draait.

    Een jaarverslag over jaar X verschijnt pas in X+1, dus het nieuwste verslag
    dat kán bestaan is dat over `batch.jaar - 1`. Dezelfde afleiding als in
    `research/service.py::run_research_batch`, `pipeline/monitoring.py` en het
    bronnenpaneel — één begrip, één berekening.
    """
    jaar = company.batch.jaar if company.batch else None
    return jaar - 1 if jaar is not None else None


async def lees_bron(
    context: QueryContext,
    url: str,
    titel: str | None = None,
    route: str = "document",
) -> SourceDocument | None:
    """Haal deze ene bron op en lees er een WP-getal uit.

    Geeft None terug als de bron niet op te halen of niet te lezen was; dat is
    geen fout maar een uitkomst, en de kaart blijft dan gewoon staan met de
    mededeling dat er niets uit kwam.
    """
    tools = (
        LiveResearchTools()
        if get_settings().provider_mode == "live"
        else MockResearchTools()
    )
    try:
        return await tools.inspect(
            context,
            PlannedQuery(
                route,
                "door de reviewer aangedragen bron",
                "een bron die de reviewer zelf heeft toegevoegd uitlezen",
            ),
            CombinedSearchResult(
                title=titel or url,
                url=url,
                canonical_url=canonicaliseer_url(url),
                providers=["reviewer"],
                queries=["door de reviewer aangedragen bron"],
            ),
        )
    except Exception as exc:
        logger.warning(
            "aangedragen bron %s niet te lezen (%s: %s)",
            url, type(exc).__name__, str(exc)[:200],
        )
        return None


def valideer_reviewersbron(document: SourceDocument) -> BronValidatie:
    """Valideren zonder weg te gooien.

    `valideer_bron` wijst een bron hard af bij een afwijkend verslagjaar of een
    naam die niet matcht, en `rank_bronnen` slaat een afgewezen bron over. Voor
    het zoeken is dat juist — de agent levert er tientallen aan en de slechte
    horen er niet tussen. Maar een bron die de reviewer zelf aandraagt hoort
    nooit stilzwijgend te verdwijnen: dan klikt hij op toevoegen en gebeurt er
    zichtbaar niets.

    Wat een afwijzing zou zijn wordt hier dus een voorbehoud: de kaart komt er,
    met de reden erbij, en de reviewer beslist. Dezelfde keuze als monitoring
    maakt in `_valideer_voor_monitoring`, om dezelfde reden.
    """
    validatie = valideer_bron(document)
    validaties = {**validatie.validaties, AANGEDRAGEN: True}
    if not validatie.is_afgewezen:
        return replace(validatie, validaties=validaties)

    redenen = list(validatie.afwijsredenen)
    identity_class = validatie.identity_class
    # "Verkeerde organisatie" komt van een naamvergelijking tussen de titel en
    # het citaat. Bij een geüpload verslag is de titel de bestandsnaam en staat
    # de naam vaak nergens in het citaat — dan luidt het oordeel "ander bedrijf"
    # precies zo vaak als de naam toevallig in de geciteerde zin stond. Dezelfde
    # situatie als een DigiMV-archiefbestand dat `Jaardocument.pdf` heet, en
    # dezelfde afhandeling: geen `exact_entity`, want wij hebben niets
    # vastgesteld, maar `possible_match` — "Mogelijk ander bedrijf", amber. De
    # koppeling komt van de reviewer; die heeft deze vestiging én dit document
    # gekozen.
    if "verkeerde organisatie" in redenen:
        identity_class = "possible_match"
        validaties["aangedragen_identificatie"] = {
            "reden": "de reviewer koppelde deze bron zelf aan deze vestiging",
            "heuristiek": validatie.identity_class,
        }

    extra = [
        _WAARSCHUWING_VOOR_AFWIJZING.get(reden, reden.replace(" ", "_"))
        for reden in redenen
    ]
    return replace(
        validatie,
        identity_class=identity_class,
        is_afgewezen=False,
        afwijsredenen=[],
        # De motieven blijven ongewijzigd bewaard: dit is wat het zoeken van
        # deze bron gevonden zou hebben, en dat hoort navolgbaar te blijven.
        validaties={**validaties, VOORBEHOUD: redenen},
        waarschuwingen=[
            *validatie.waarschuwingen,
            *[sleutel for sleutel in extra if sleutel],
        ],
    )


def weeg_reviewersbron(document: SourceDocument) -> RankedBron | None:
    """Van uitgelezen document naar een weging die op de kaart past."""
    ranked = rank_bronnen([valideer_reviewersbron(document)])
    return ranked[0] if ranked else None


def maak_kandidaat(
    db,
    company: Company,
    document: SourceDocument,
    doel: str,
    onderzoekspaden: list[dict] | None = None,
) -> BronKandidaat:
    """Leg een aangedragen document vast als beoordeelbare bronkaart.

    Met een eigen `ResearchRun` eromheen, net als de monitoring doet: zo blijft
    zichtbaar wanneer en waarom deze kaart is ontstaan, en blijft het werk van
    de agent gescheiden van dat van de reviewer.
    """
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel=doel,
        gevraagd_jaar=document.gevraagd_jaar,
        status="completed",
        resultaat_status="review_nodig",
        onderzoekspaden=onderzoekspaden or [],
        started_at=_now(),
        completed_at=_now(),
    )
    db.add(run)
    db.flush()
    kandidaat = BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url=document.url,
        canonical_url=canonicaliseer_url(document.url),
        titel=document.titel,
        brontype=document.brontype,
        status="voorgesteld",
        rang=1,
    )
    db.add(kandidaat)
    ranked = weeg_reviewersbron(document)
    if ranked is not None:
        vul_kandidaat(kandidaat, ranked)
    db.flush()
    return kandidaat


def vul_kandidaat(kandidaat: BronKandidaat, ranked: RankedBron) -> None:
    """Schrijf wat er uit de bron is gelezen op de bestaande kaart.

    Bijwerken en niet een tweede kaart aanmaken: de reviewer heeft er één
    toegevoegd, en twee kaarten voor dezelfde URL zijn voor hem niet te
    onderscheiden. `brontype` blijft daarom ook wat het was — daar hangt aan op
    of het bronnenpaneel de kaart altijd toont, los van welke run de laatste is.
    """
    bewijs = ranked.document
    kandidaat.titel = kandidaat.titel or bewijs.titel
    kandidaat.documenttype = bewijs.documenttype
    kandidaat.verslagjaar = bewijs.verslagjaar
    kandidaat.publicatiedatum = bewijs.publicatiedatum
    kandidaat.informatie_peilmoment = bewijs.informatie_peilmoment
    kandidaat.wp_gevonden = bewijs.wp_gevonden
    kandidaat.eenheid = bewijs.eenheid
    kandidaat.bewijsfragment = bewijs.bewijsfragment
    kandidaat.bron_pagina = bewijs.bron_pagina
    kandidaat.identity_class = ranked.identity_class
    kandidaat.scope_class = bewijs.scope_class
    kandidaat.autoriteit_score = ranked.score_breakdown["autoriteit"]
    kandidaat.actualiteit_score = ranked.score_breakdown["actualiteit"]
    kandidaat.identiteit_score = ranked.score_breakdown["identiteit"]
    kandidaat.relevantie_score = ranked.score_breakdown["relevantie"]
    kandidaat.ranking_score = ranked.ranking_score
    kandidaat.score_breakdown = ranked.score_breakdown
    kandidaat.validaties = {**(kandidaat.validaties or {}), **ranked.validaties}
    kandidaat.waarschuwingen = list(ranked.waarschuwingen)
    kandidaat.raw_data = bewijs.raw_data or kandidaat.raw_data
