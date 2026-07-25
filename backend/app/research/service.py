"""Persistente uitvoering van een begrensde bronnenresearchrun."""
import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..models import Batch, BronKandidaat, Company, Enrichment, ResearchRun
from ..pipeline.identity_scope import domain_matches_company
from .live_tools import LiveResearchTools
from .mock_tools import MockResearchTools
from .query_planner import QueryContext
from .seeds import verzamel_seed_documenten
from .source_reviewer import IntelligentSourceReviewer
from .supervisor import ResearchSupervisor
from .urls import canonicaliseer_url


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


def maak_research_run(
    db: Session,
    company: Company,
    gevraagd_jaar: int | None,
) -> ResearchRun:
    settings = get_settings()
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="actuele en relevante openbare WP-bronnen vinden",
        gevraagd_jaar=gevraagd_jaar,
        status="pending",
        onderzoekspaden=["website", "document", "media"],
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


async def run_research_run(run_id: str) -> None:
    context = None
    website_resolution = {
        "status": "niet_gevonden",
        "website_url": None,
        "bron": None,
    }
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
            run.started_at = _now()
            db.commit()

        if settings.provider_mode == "live" and not website_url:
            try:
                from ..providers.live import LivePlacesProvider

                place = await LivePlacesProvider().lookup(
                    company_naam, company_gemeente,
                )
                website_url = place.website if place else None
                website_resolution = {
                    "status": "gevonden" if website_url else "niet_gevonden",
                    "website_url": website_url,
                    "bron": (
                        (place.raw or {}).get("bron", "google_places")
                        if place else None
                    ),
                }
                if website_url:
                    with SessionLocal() as db:
                        enrichment = (
                            db.query(Enrichment)
                            .filter_by(company_id=company_id)
                            .one_or_none()
                        )
                        if enrichment is None:
                            enrichment = Enrichment(
                                company_id=company_id,
                                website_url=website_url,
                                lookup_failed=False,
                            )
                            db.add(enrichment)
                        else:
                            enrichment.website_url = website_url
                            enrichment.lookup_failed = False
                        db.commit()
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
        )
        tools = (
            LiveResearchTools()
            if settings.provider_mode == "live"
            else MockResearchTools()
        )
        seed_documents = (
            await verzamel_seed_documenten(tools, context)
            if settings.provider_mode == "live"
            else []
        )
        heeft_exacte_officiele_primaire_bron = any(
            document.verslagjaar == gevraagd_jaar
            and domain_matches_company(
                document.url, document.company_website_url,
            ) is True
            for document in seed_documents
        )
        effectief_max_paginas = (
            min(
                settings.research_max_pages,
                settings.research_max_pages_after_primary,
            )
            if heeft_exacte_officiele_primaire_bron
            else settings.research_max_pages
        )
        outcome = await ResearchSupervisor(
            tools,
            max_queries=settings.research_max_queries,
            max_pages=effectief_max_paginas,
            max_kandidaten=settings.research_max_kandidaten,
            reviewer=(
                IntelligentSourceReviewer()
                if settings.provider_mode == "live"
                else None
            ),
        ).run(context, seed_documents=seed_documents)

        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is None:
                return
            for rang, (ranked, canonical_url) in enumerate(
                _dedupliceer_kandidaten(outcome.kandidaten),
                start=1,
            ):
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
                    status="voorgesteld",
                    rang=rang,
                ))

            run.status = "completed"
            run.resultaat_status = outcome.status
            run.completed_at = _now()
            run.configuratie = {
                **(run.configuratie or {}),
                "effectief_max_paginas": effectief_max_paginas,
                "exacte_officiele_primaire_bron": (
                    heeft_exacte_officiele_primaire_bron
                ),
                "diagnostiek": outcome.diagnostiek,
            }
            run.configuratie["diagnostiek"]["website_resolution"] = (
                website_resolution
            )
            if outcome.fouten:
                run.fout = " | ".join(outcome.fouten)[:4000]
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is not None:
                run.status = "error"
                run.resultaat_status = "error"
                run.fout = str(exc)[:4000]
                run.completed_at = _now()
                db.commit()


async def run_research_batch(batch_id: str) -> None:
    """Voert de primaire researchworkflow begrensd en sequentieel uit.

    Sequentieel is bewust: het bewaakt API-budgetten en voorkomt dat een batch
    van twintig organisaties honderden extractiecalls tegelijk start.
    """
    try:
        settings = get_settings()
        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            if batch is None:
                return
            company_ids = [
                item.id
                for item in db.query(Company).filter_by(batch_id=batch.id).all()
            ]
            gevraagd_jaar = batch.jaar - 1
            batch.status = "running"
            batch.verwerkt = 0
            batch.completed_at = None
            db.commit()

        for company_id in company_ids:
            with SessionLocal() as db:
                batch = db.get(Batch, batch_id)
                if batch is None or batch.status == "cancelled":
                    return
                company = db.get(Company, company_id)
                run = maak_research_run(db, company, gevraagd_jaar)
            try:
                await asyncio.wait_for(
                    run_research_run(run.id),
                    timeout=settings.research_company_timeout_seconds,
                )
            except TimeoutError:
                # Eén trage of niet-reagerende externe bron mag de overige
                # organisaties niet blokkeren. Bewaar de timeout als expliciet
                # onderzoeksresultaat en ga gecontroleerd door.
                with SessionLocal() as db:
                    timed_out_run = db.get(ResearchRun, run.id)
                    if timed_out_run is not None:
                        timed_out_run.status = "error"
                        timed_out_run.resultaat_status = "error"
                        timed_out_run.fout = (
                            "onderzoek afgebroken na "
                            f"{settings.research_company_timeout_seconds} seconden"
                        )
                        timed_out_run.completed_at = _now()
                        db.commit()
            with SessionLocal() as db:
                batch = db.get(Batch, batch_id)
                if batch is None:
                    return
                batch.verwerkt += 1
                db.commit()

        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            if batch is not None:
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
