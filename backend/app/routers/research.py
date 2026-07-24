"""API voor autonome bronvinding en menselijke bronreview."""
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import BronKandidaat, Company, ResearchRun, User
from ..research.service import maak_research_run, run_research_run
from ..research.urls import canonicaliseer_url

router = APIRouter(
    prefix="/research",
    tags=["research"],
    dependencies=[Depends(get_current_user)],
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StartResearchBody(BaseModel):
    gevraagd_jaar: int | None = Field(default=None, ge=2000, le=2100)


class ReviewBody(BaseModel):
    beslissing: str
    reden: str | None = Field(default=None, max_length=2000)


class ManualSourceBody(BaseModel):
    url: HttpUrl
    titel: str | None = Field(default=None, max_length=500)
    reden: str | None = Field(default=None, max_length=2000)


def _candidate_dict(candidate: BronKandidaat) -> dict:
    return {
        "id": candidate.id,
        "research_run_id": candidate.research_run_id,
        "url": candidate.url,
        "titel": candidate.titel,
        "brontype": candidate.brontype,
        "documenttype": candidate.documenttype,
        "verslagjaar": candidate.verslagjaar,
        "publicatiedatum": (
            candidate.publicatiedatum.isoformat()
            if candidate.publicatiedatum else None
        ),
        "informatie_peilmoment": candidate.informatie_peilmoment,
        "wp_gevonden": candidate.wp_gevonden,
        "eenheid": candidate.eenheid,
        "bewijsfragment": candidate.bewijsfragment,
        "bron_pagina": candidate.bron_pagina,
        "identity_class": candidate.identity_class,
        "scope_class": candidate.scope_class,
        "ranking_score": candidate.ranking_score,
        "score_breakdown": candidate.score_breakdown,
        "validaties": candidate.validaties,
        "waarschuwingen": candidate.waarschuwingen,
        "status": candidate.status,
        "rang": candidate.rang,
        "review_reason": candidate.review_reason,
    }


@router.post(
    "/companies/{company_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
)
def start_research(
    company_id: str,
    body: StartResearchBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "company niet gevonden")
    run = maak_research_run(db, company, body.gevraagd_jaar)
    background_tasks.add_task(run_research_run, run.id)
    return {"run_id": run.id, "status": run.status}


@router.get("/runs/{run_id}")
def get_research_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(404, "researchrun niet gevonden")
    kandidaten = (
        db.query(BronKandidaat)
        .filter_by(research_run_id=run.id)
        .order_by(BronKandidaat.rang)
        .all()
    )
    return {
        "id": run.id,
        "company_id": run.company_id,
        "status": run.status,
        "resultaat_status": run.resultaat_status,
        "gevraagd_jaar": run.gevraagd_jaar,
        "fout": run.fout,
        "kandidaten": [_candidate_dict(item) for item in kandidaten],
    }


@router.get("/companies/{company_id}/candidates")
def get_company_candidates(company_id: str, db: Session = Depends(get_db)):
    if db.get(Company, company_id) is None:
        raise HTTPException(404, "company niet gevonden")
    laatste_run = (
        db.query(ResearchRun)
        .filter_by(company_id=company_id)
        .order_by(ResearchRun.created_at.desc())
        .first()
    )
    if laatste_run is None:
        return {"items": []}
    kandidaten = (
        db.query(BronKandidaat)
        .filter_by(research_run_id=laatste_run.id)
        .order_by(BronKandidaat.rang)
        .all()
    )
    return {"items": [_candidate_dict(item) for item in kandidaten]}


@router.post("/candidates/{candidate_id}/review")
def review_candidate(
    candidate_id: str,
    body: ReviewBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.beslissing not in {"accepteren", "afwijzen"}:
        raise HTTPException(422, "beslissing moet accepteren of afwijzen zijn")
    candidate = db.get(BronKandidaat, candidate_id)
    if candidate is None:
        raise HTTPException(404, "bronkandidaat niet gevonden")

    if body.beslissing == "accepteren":
        andere = (
            db.query(BronKandidaat)
            .filter(
                BronKandidaat.research_run_id == candidate.research_run_id,
                BronKandidaat.id != candidate.id,
                BronKandidaat.status == "geaccepteerd",
            )
            .all()
        )
        for item in andere:
            item.status = "alternatief"
        candidate.status = "geaccepteerd"
    else:
        candidate.status = "afgewezen"

    candidate.reviewed_by = current_user.id
    candidate.reviewed_at = _now()
    candidate.review_reason = body.reden
    db.commit()
    return _candidate_dict(candidate)


@router.post(
    "/companies/{company_id}/manual-source",
    status_code=status.HTTP_201_CREATED,
)
def add_manual_source(
    company_id: str,
    body: ManualSourceBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "company niet gevonden")
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="handmatige bron door reviewer",
        status="completed",
        resultaat_status="review_nodig",
        completed_at=_now(),
    )
    db.add(run)
    db.flush()
    url = str(body.url)
    candidate = BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url=url,
        canonical_url=canonicaliseer_url(url),
        titel=body.titel,
        brontype="handmatig",
        status="geaccepteerd",
        rang=1,
        reviewed_by=current_user.id,
        reviewed_at=_now(),
        review_reason=body.reden,
        validaties={"handmatig_toegevoegd": True},
    )
    db.add(candidate)
    db.commit()
    return {"candidate_id": candidate.id, "run_id": run.id}
