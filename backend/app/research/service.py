"""Persistente uitvoering van een begrensde bronnenresearchrun."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..models import BronKandidaat, Company, ResearchRun
from .live_tools import LiveResearchTools
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
    db = SessionLocal()
    try:
        run = db.get(ResearchRun, run_id)
        if run is None:
            return
        company = db.get(Company, run.company_id)
        if company is None:
            run.status = "error"
            run.fout = "company niet gevonden"
            db.commit()
            return

        settings = get_settings()
        run.status = "running"
        run.started_at = _now()
        db.commit()

        outcome = await ResearchSupervisor(
            LiveResearchTools(),
            max_queries=settings.research_max_queries,
            max_pages=settings.research_max_pages,
        ).run(QueryContext(
            naam=company.naam,
            gevraagd_jaar=run.gevraagd_jaar,
            website_url=company.website_url or (
                company.enrichment.website_url if company.enrichment else None
            ),
            gemeente=company.gemeente,
        ))

        for rang, ranked in enumerate(outcome.kandidaten, start=1):
            document = ranked.document
            db.add(BronKandidaat(
                research_run_id=run.id,
                company_id=company.id,
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
        db.rollback()
        run = db.get(ResearchRun, run_id)
        if run is not None:
            run.status = "error"
            run.resultaat_status = "error"
            run.fout = str(exc)[:4000]
            run.completed_at = _now()
            db.commit()
    finally:
        db.close()
