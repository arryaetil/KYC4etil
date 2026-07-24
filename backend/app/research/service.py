"""Persistente uitvoering van een begrensde bronnenresearchrun."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..models import Batch, BronKandidaat, Company, ResearchRun
from .live_tools import LiveResearchTools
from .mock_tools import MockResearchTools
from .query_planner import QueryContext
from .supervisor import ResearchSupervisor
from .urls import canonicaliseer_url


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
            context = QueryContext(
                naam=company.naam,
                gevraagd_jaar=run.gevraagd_jaar,
                website_url=company.website_url or enrichment_website,
                gemeente=company.gemeente,
            )
            run.status = "running"
            run.started_at = _now()
            db.commit()

        tools = (
            LiveResearchTools()
            if settings.provider_mode == "live"
            else MockResearchTools()
        )
        outcome = await ResearchSupervisor(
            tools,
            max_queries=settings.research_max_queries,
            max_pages=settings.research_max_pages,
        ).run(context)

        with SessionLocal() as db:
            run = db.get(ResearchRun, run_id)
            if run is None:
                return
            for rang, ranked in enumerate(outcome.kandidaten, start=1):
                document = ranked.document
                db.add(BronKandidaat(
                    research_run_id=run.id,
                    company_id=company_id,
                    url=document.url,
                    canonical_url=canonicaliseer_url(document.url),
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
            await run_research_run(run.id)
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
