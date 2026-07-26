"""API voor autonome bronvinding en menselijke bronreview."""
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_current_user_of_querytoken
from ..database import get_db
from ..models import (
    AgentResult, BronKandidaat, Company, JaarverslagMonitoring, ResearchRun, User,
)
from ..research.service import maak_research_run, run_research_run
from ..providers.live import USER_AGENT
from ..research.urls import canonicaliseer_url

router = APIRouter(
    prefix="/research",
    tags=["research"],
    dependencies=[Depends(get_current_user)],
)

# De PDF-viewer kan geen Authorization-header meesturen; deze router laat
# daarom het token ook als queryparameter toe (zie bron_pdf).
bron_router = APIRouter(prefix="/research", tags=["research"])


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


def _run_diagnostiek(run: ResearchRun) -> dict:
    return (run.configuratie or {}).get("diagnostiek") or {}


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
        "diagnostiek": _run_diagnostiek(run),
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
        return {"items": [], "diagnostiek": {}}
    kandidaten = (
        db.query(BronKandidaat)
        .filter_by(research_run_id=laatste_run.id)
        .order_by(BronKandidaat.rang)
        .all()
    )
    return {
        "items": [_candidate_dict(item) for item in kandidaten],
        "diagnostiek": _run_diagnostiek(laatste_run),
    }


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


# Maximale omvang van een doorgegeven brondocument. Jaarverslagen zijn zelden
# groter dan een paar tientallen MB; deze grens voorkomt dat één bron het
# geheugen van de webserver opeet.
MAX_BRON_BYTES = 60 * 1024 * 1024


def _is_bekende_bron(db: Session, url: str) -> bool:
    """Alleen URL's die de agent zelf heeft gevonden mogen worden opgehaald.

    Zonder deze controle zou dit endpoint een server-side request forgery
    opleveren: een ingelogde gebruiker zou de backend elk willekeurig adres
    kunnen laten benaderen, inclusief interne diensten die van buitenaf niet
    bereikbaar zijn. De kandidaten- en monitoringtabellen fungeren daarom als
    allowlist; die URL's komen aantoonbaar van het open web.
    """
    if db.query(BronKandidaat).filter_by(url=url).first() is not None:
        return True
    if db.query(AgentResult).filter_by(bron_url=url).first() is not None:
        return True
    return (
        db.query(JaarverslagMonitoring)
        .filter_by(laatste_bron_url=url)
        .first()
        is not None
    )


@bron_router.get("/bron-pdf")
async def bron_pdf(
    url: str,
    db: Session = Depends(get_db),
    _gebruiker=Depends(get_current_user_of_querytoken),
):
    """Geeft een brondocument door vanaf hetzelfde domein als de applicatie.

    De ingebouwde PDF-viewer kan een document van een ander domein niet tonen:
    de browser blokkeert het ophalen zodra de bronserver geen CORS-headers
    stuurt, en dat doet lang niet elke organisatie. Door het document hier op
    te halen en door te geven komt het voor de browser van onze eigen oorsprong
    en werkt zowel de weergave als het springen naar de juiste pagina.
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "alleen http(s)-bronnen worden ondersteund")
    if not _is_bekende_bron(db, url):
        raise HTTPException(404, "onbekende bron")

    client = httpx.AsyncClient(timeout=60, follow_redirects=True)
    try:
        request = client.build_request(
            "GET", url, headers={"User-Agent": USER_AGENT},
        )
        response = await client.send(request, stream=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(502, f"bron niet op te halen: {exc}") from exc

    lengte = response.headers.get("content-length")
    if lengte and int(lengte) > MAX_BRON_BYTES:
        await response.aclose()
        await client.aclose()
        raise HTTPException(413, "brondocument is te groot")

    async def doorgeven():
        gelezen = 0
        try:
            async for blok in response.aiter_bytes():
                gelezen += len(blok)
                if gelezen > MAX_BRON_BYTES:
                    break
                yield blok
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(
        doorgeven(),
        media_type=response.headers.get("content-type", "application/pdf"),
        headers={"Content-Disposition": "inline"},
    )
