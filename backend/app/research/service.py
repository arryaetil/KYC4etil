"""Persistente uitvoering van een begrensde bronnenresearchrun."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..models import Batch, BronKandidaat, Company, Enrichment, ResearchRun
from ..providers.website_check import controleer_website
from .live_tools import LiveResearchTools
from .mock_tools import MockResearchTools
from .organizations import koppel_organisatie, vind_bestaande_bronnen
from .query_planner import QueryContext, plan_routes
from .sector_probe import verrijk_routeplan
from .bronsamenvatting import schrijf_samenvatting
from .seeds import verzamel_seed_documenten
from .source_reviewer import IntelligentSourceReviewer
from .supervisor import ResearchSupervisor
from .urls import canonicaliseer_url
from .usage import (
    get_cost_summary,
    get_dienststoringen,
    get_usage_totals,
    start_usage_tracking,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _dedupliceer_kandidaten(kandidaten):
    """Verwijder dezelfde bron uit parallelle onderzoekspaden vóór DB-opslag."""
    uniek = []
    geziene_canonical_urls: set[str] = set()
    for ranked in kandidaten:
        canonical_url = canonicaliseer_url(ranked.document.url)
        if canonical_url in geziene_canonical_urls:
            continue
        geziene_canonical_urls.add(canonical_url)
        uniek.append((ranked, canonical_url))
    return uniek


def _sla_kosten_op(run: ResearchRun) -> None:
    tokens_in, tokens_out = get_usage_totals()
    kosten = get_cost_summary()
    run.tokens_in = tokens_in
    run.tokens_out = tokens_out
    run.kosten_cents = kosten["totaal_cents"]
    run.configuratie = {
        **(run.configuratie or {}),
        "kosten": kosten,
    }


def maak_research_run(
    db: Session,
    company: Company,
    gevraagd_jaar: int | None,
) -> ResearchRun:
    settings = get_settings()
    context = QueryContext(
        naam=company.naam,
        gevraagd_jaar=gevraagd_jaar,
        website_url=company.website_url,
        gemeente=company.gemeente,
        adres=company.adres,
        sbi_code=company.sbi_code,
        sbi_omschrijving=company.sbi_omschrijving,
        kvk_nummer=company.kvk_nummer,
        vestigingsnummer=company.vestigingsnummer,
    )
    koppel_organisatie(
        db,
        company,
        company.website_url or (
            company.enrichment.website_url if company.enrichment else None
        ),
    )
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="actuele en relevante openbare WP-bronnen vinden",
        gevraagd_jaar=gevraagd_jaar,
        status="pending",
        onderzoekspaden=plan_routes(context),
        configuratie={
            "max_queries": settings.research_max_queries,
            "max_pages": settings.research_max_pages,
            "max_rounds": settings.research_max_rounds,
            "media_venster_maanden": settings.research_media_venster_maanden,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _bewaar_website(company_id: str, website_url: str) -> None:
    """Leg de gevonden of gecorrigeerde website vast op de verrijking.

    Niet op `Company.website_url`: dat veld houdt vast wat er is aangeleverd, en
    dat is de enige manier om later te zien dat de aanlevering achterliep.
    """
    with SessionLocal() as db:
        enrichment = (
            db.query(Enrichment).filter_by(company_id=company_id).one_or_none()
        )
        if enrichment is None:
            db.add(Enrichment(
                company_id=company_id,
                website_url=website_url,
                lookup_failed=False,
            ))
        else:
            enrichment.website_url = website_url
            enrichment.lookup_failed = False
        db.commit()


async def _run_research_run(run_id: str) -> None:
    context = None
    website_resolution = {
        "status": "niet_gevonden",
        "website_url": None,
        "bron": None,
    }
    start_usage_tracking()
    try:
        settings = get_settings()
        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is None:
                return
            company = db.get(Company, run.company_id)
            if company is None:
                run.status = "error"
                run.fout = "company niet gevonden"
                db.commit()
                return

            # Maak alle lazy-loaded context af vóór de netwerkfase. De sessie
            # sluit daarna, zodat research nooit minutenlang een DB-connectie
            # vasthoudt.
            enrichment_website = (
                company.enrichment.website_url if company.enrichment else None
            )
            company_id = company.id
            company_naam = company.naam
            company_gemeente = company.gemeente
            company_adres = company.adres
            company_sbi_code = company.sbi_code
            company_sbi_omschrijving = company.sbi_omschrijving
            company_kvk_nummer = company.kvk_nummer
            company_vestigingsnummer = company.vestigingsnummer
            gevraagd_jaar = run.gevraagd_jaar
            website_url = company.website_url or enrichment_website
            if website_url:
                website_resolution = {
                    "status": "gevonden",
                    "website_url": website_url,
                    "bron": (
                        "company"
                        if company.website_url
                        else "enrichment"
                    ),
                }
            run.status = "running"
            run.onderzoekspaden = [
                {**item, "status": "bezig"}
                for item in (run.onderzoekspaden or [])
            ]
            run.started_at = _now()
            db.commit()

        # Een aangeleverde URL is niet vanzelf nog geldig: bedrijven verhuizen,
        # fuseren of laten hun domein verlopen. Zonder deze controle onderzocht
        # de agent een dood adres en kwam er "niets gevonden" uit, wat iets
        # heel anders betekent.
        if settings.provider_mode == "live" and website_url:
            controle = await controleer_website(website_url)
            if controle.bruikbaar and controle.url != website_url:
                website_url = controle.url
                _bewaar_website(company_id, website_url)
                website_resolution = {
                    "status": "gevonden",
                    "website_url": website_url,
                    "bron": "redirect",
                    "controle": controle.reden,
                }
            elif not controle.bruikbaar:
                # Loslaten en hieronder opnieuw zoeken; de oude URL is niets waard.
                website_resolution = {
                    "status": "verlopen",
                    "website_url": None,
                    "bron": None,
                    "controle": controle.reden,
                    "vervangen_url": website_url,
                }
                website_url = None

        if settings.provider_mode == "live" and not website_url:
            try:
                from ..providers.live import LivePlacesProvider

                place = await LivePlacesProvider().lookup(
                    company_naam, company_gemeente,
                )
                vorige = website_resolution
                website_url = place.website if place else None
                website_resolution = {
                    "status": "gevonden" if website_url else "niet_gevonden",
                    "website_url": website_url,
                    "bron": (
                        (place.raw or {}).get("bron", "google_places")
                        if place else None
                    ),
                }
                # Bewaar dat er een dood adres is vervangen: anders lijkt dit op
                # een organisatie die nooit een website meekreeg.
                if vorige.get("vervangen_url"):
                    website_resolution["vervangen_url"] = vorige["vervangen_url"]
                    website_resolution["controle"] = vorige.get("controle")
                if website_url:
                    _bewaar_website(company_id, website_url)
            except Exception as exc:
                # Places is een versterking, geen single point of failure.
                website_url = None
                website_resolution = {
                    "status": "fout",
                    "website_url": None,
                    "bron": None,
                    "fout": type(exc).__name__,
                }

        context = QueryContext(
            naam=company_naam,
            gevraagd_jaar=gevraagd_jaar,
            website_url=website_url,
            gemeente=company_gemeente,
            adres=company_adres,
            sbi_code=company_sbi_code,
            sbi_omschrijving=company_sbi_omschrijving,
            kvk_nummer=company_kvk_nummer,
            vestigingsnummer=company_vestigingsnummer,
        )
        with SessionLocal() as db:
            company = db.get(Company, company_id)
            if company is None:
                return
            koppel_organisatie(db, company, website_url)
            db.flush()
            bestaande_bronnen = vind_bestaande_bronnen(db, company)
            db.commit()
        tools = (
            LiveResearchTools()
            if settings.provider_mode == "live"
            else MockResearchTools()
        )
        # Eén routeplan voor de hele run. In live-modus mogen de registers
        # zichzelf identificeren wanneer er geen SBI-code is; dat plan gaat
        # daarna ongewijzigd naar zowel de seeds als de supervisor.
        route_plan = plan_routes(context)
        if settings.provider_mode == "live":
            route_plan = await verrijk_routeplan(context, route_plan)
        seed_documents = (
            await verzamel_seed_documenten(
                tools,
                context,
                {item["route"] for item in route_plan},
                bestaande_bronnen=bestaande_bronnen,
            )
            if settings.provider_mode == "live"
            else []
        )
        outcome = await ResearchSupervisor(
            tools,
            max_queries=settings.research_max_queries,
            max_pages=settings.research_max_pages,
            max_kandidaten=settings.research_max_kandidaten,
            reviewer=(
                IntelligentSourceReviewer()
                if settings.provider_mode == "live"
                else None
            ),
        ).run(context, seed_documents=seed_documents, route_plan=route_plan)

        kandidaten = list(_dedupliceer_kandidaten(outcome.kandidaten))
        # Vóór de sessie: dit is een netwerkcall, en de sessie hoort niet open
        # te staan terwijl we op een model wachten. Mislukt hij, dan is
        # `samenvatting` None en valt de kaart terug op zijn vaste tekst.
        samenvatting = await schrijf_samenvatting(
            company_naam,
            gevraagd_jaar,
            [
                {
                    "brontype": ranked.document.brontype,
                    "documenttype": ranked.document.documenttype,
                    "verslagjaar": ranked.document.verslagjaar,
                    "informatie_peilmoment": ranked.document.informatie_peilmoment,
                    "wp_gevonden": ranked.document.wp_gevonden,
                    "eenheid": ranked.document.eenheid,
                    "bewijsfragment": ranked.document.bewijsfragment,
                    "scope_class": ranked.document.scope_class,
                    "identity_class": ranked.identity_class,
                }
                for ranked, _ in kandidaten
            ],
        )

        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is None:
                return
            for rang, (ranked, canonical_url) in enumerate(kandidaten, start=1):
                document = ranked.document
                db.add(BronKandidaat(
                    research_run_id=run.id,
                    company_id=company_id,
                    url=document.url,
                    canonical_url=canonical_url,
                    titel=document.titel,
                    brontype=document.brontype,
                    documenttype=document.documenttype,
                    verslagjaar=document.verslagjaar,
                    publicatiedatum=document.publicatiedatum,
                    informatie_peilmoment=document.informatie_peilmoment,
                    wp_gevonden=document.wp_gevonden,
                    eenheid=document.eenheid,
                    bewijsfragment=document.bewijsfragment,
                    bron_pagina=document.bron_pagina,
                    identity_class=ranked.identity_class,
                    scope_class=document.scope_class,
                    autoriteit_score=ranked.score_breakdown["autoriteit"],
                    actualiteit_score=ranked.score_breakdown["actualiteit"],
                    identiteit_score=ranked.score_breakdown["identiteit"],
                    relevantie_score=ranked.score_breakdown["relevantie"],
                    ranking_score=ranked.ranking_score,
                    score_breakdown=ranked.score_breakdown,
                    validaties=ranked.validaties,
                    waarschuwingen=ranked.waarschuwingen,
                    raw_data=document.raw_data,
                    status="voorgesteld",
                    rang=rang,
                ))

            run.status = "completed"
            run.resultaat_status = outcome.status
            run.onderzoekspaden = outcome.diagnostiek.get(
                "route_statussen",
                run.onderzoekspaden,
            )
            run.completed_at = _now()
            _sla_kosten_op(run)
            run.configuratie = {
                **(run.configuratie or {}),
                "diagnostiek": outcome.diagnostiek,
            }
            run.configuratie["diagnostiek"]["website_resolution"] = (
                website_resolution
            )
            # Zonder dit ziet een run waarin Serper of OpenAI geen tegoed meer
            # had er hetzelfde uit als een organisatie waarover niets te vinden
            # is. Dat verschil moet de reviewer zien.
            run.configuratie["diagnostiek"]["dienststoringen"] = (
                get_dienststoringen()
            )
            run.configuratie["bronsamenvatting"] = samenvatting
            if outcome.fouten:
                run.fout = " | ".join(outcome.fouten)[:4000]
            db.commit()
    except asyncio.CancelledError:
        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is not None:
                run.status = "error"
                run.resultaat_status = "error"
                run.fout = "onderzoek afgebroken"
                _sla_kosten_op(run)
                run.completed_at = _now()
                db.commit()
        raise
    except Exception as exc:
        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is not None:
                run.status = "error"
                run.resultaat_status = "error"
                run.fout = str(exc)[:4000]
                storingen = get_dienststoringen()
                if storingen:
                    run.configuratie = {
                        **(run.configuratie or {}),
                        "diagnostiek": {
                            **((run.configuratie or {}).get("diagnostiek") or {}),
                            "dienststoringen": storingen,
                        },
                    }
                _sla_kosten_op(run)
                run.completed_at = _now()
                db.commit()


async def run_research_run(run_id: str) -> None:
    """Voer één researchrun uit binnen de centrale tijdslimiet."""
    timeout_seconds = get_settings().research_company_timeout_seconds
    try:
        await asyncio.wait_for(
            _run_research_run(run_id),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is not None:
                run.status = "error"
                run.resultaat_status = "error"
                run.fout = (
                    f"onderzoek afgebroken na {timeout_seconds} seconden"
                )
                run.completed_at = _now()
                db.commit()


def _tel_verwerkt_op(batch_id: str) -> None:
    """Eén organisatie erbij, in de database opgeteld en niet in Python.

    `batch.verwerkt += 1` is lezen, optellen en terugschrijven. Zolang er één
    organisatie tegelijk draaide kon daar niets tussen komen; nu wel, en dan
    verdwijnt er stilletjes voortgang uit de teller.
    """
    with SessionLocal() as db:
        db.execute(
            update(Batch)
            .where(Batch.id == batch_id)
            .values(verwerkt=Batch.verwerkt + 1),
        )
        db.commit()


async def _verwerk_company(
    batch_id: str,
    company_id: str,
    gevraagd_jaar: int | None,
    plaatsen: asyncio.Semaphore,
) -> None:
    async with plaatsen:
        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            # Bij "annuleren" stoppen de organisaties die nog niet begonnen
            # waren; wie al bezig is maakt zijn run af en wordt netjes
            # weggeschreven.
            if batch is None or batch.status == "cancelled":
                return
            company = db.get(Company, company_id)
            if company is None:
                return
            run = maak_research_run(db, company, gevraagd_jaar)
            run_id = run.id
        await run_research_run(run_id)
    _tel_verwerkt_op(batch_id)


async def run_research_batch(batch_id: str) -> None:
    """Voert de primaire researchworkflow begrensd uit, meerdere tegelijk.

    Dit was bewust sequentieel, om API-budgetten te bewaken. Dat werkte, maar
    het maakte de doorlooptijd van een lijst gelijk aan de som van al haar
    runs: op productie gemeten 100% bezetting, geen dode tijd ertussen, en dus
    6 uur 19 voor 108 vestigingen. Budgetbewaking is een taak voor een limiet,
    niet voor het op een rij zetten van al het werk.

    Hoeveel er tegelijk mogen staat in `research_max_parallel_companies`; op 1
    is het gedrag exact als voorheen. De gedeelde browser heeft een eigen rem
    (`crawl4ai_max_parallel`), en de kostenteller loopt per taak via
    contextvars, dus die telt niet door elkaar heen.

    Alle vestigingen staan hier door elkaar, en dat is met opzet. Het lag voor
    de hand om vestigingen van dezelfde organisatie te groeperen en er één
    vooruit te sturen, zodat de rest haar gedeelde bronnen kan hergebruiken in
    plaats van ze allemaal tegelijk op te halen. Gemeten (`scripts.bench_batch`)
    kost die kopvestiging meer dan ze oplevert: alleen de eerste golf loopt het
    hergebruik mis, alles daarna pakt het vanzelf mee. Bij 48 vestigingen
    scheelde groeperen zes leesbeurten en kostte het anderhalve seconde op
    zeventien. Niet doen dus.
    """
    try:
        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            if batch is None:
                return
            stale_runs = (
                db.query(ResearchRun)
                .filter_by(batch_id=batch.id, status="running")
                .all()
            )
            for stale_run in stale_runs:
                stale_run.status = "error"
                stale_run.resultaat_status = "error"
                stale_run.fout = "onderbroken proces; opnieuw ingepland"
                stale_run.completed_at = _now()
            afgeronde_company_ids = {
                company_id
                for (company_id,) in (
                    db.query(ResearchRun.company_id)
                    .filter_by(batch_id=batch.id, status="completed")
                    .distinct()
                )
            }
            company_ids = [
                item.id
                for item in db.query(Company).filter_by(batch_id=batch.id).all()
                if item.id not in afgeronde_company_ids
            ]
            gevraagd_jaar = batch.jaar - 1
            batch.status = "running"
            batch.verwerkt = len(afgeronde_company_ids)
            batch.completed_at = None
            db.commit()

        plaatsen = asyncio.Semaphore(
            max(1, get_settings().research_max_parallel_companies),
        )
        # return_exceptions: één organisatie die alsnog omvalt mag de rest van
        # de lijst niet meenemen. De fout staat dan al op haar eigen run.
        resultaten = await asyncio.gather(*[
            _verwerk_company(batch_id, company_id, gevraagd_jaar, plaatsen)
            for company_id in company_ids
        ], return_exceptions=True)
        for resultaat in resultaten:
            if isinstance(resultaat, BaseException):
                logging.getLogger(__name__).warning(
                    "organisatie in lijst %s mislukt (%s: %s)",
                    batch_id, type(resultaat).__name__, str(resultaat)[:200],
                )

        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            # Een geannuleerde lijst blijft geannuleerd. De oude lus verliet de
            # functie bij "cancelled" en kwam hier dus nooit; nu lopen de
            # organisaties in een gather en komen we hier altijd langs.
            if batch is not None and batch.status != "cancelled":
                batch.status = "review"
                batch.completed_at = _now()
                db.commit()
    except Exception:
        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            if batch is not None:
                batch.status = "error"
                batch.completed_at = _now()
                db.commit()
        raise
