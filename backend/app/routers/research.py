"""API voor autonome bronvinding en menselijke bronreview."""
from collections import Counter
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_current_user_of_querytoken
from ..database import get_db
from ..models import (
    BronKandidaat, Company, JaarverslagMonitoring, ResearchRun, User,
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
    reason_code: str | None = Field(default=None, max_length=50)
    reden: str | None = Field(default=None, max_length=2000)
    wp_oordeel: str | None = Field(default=None, max_length=30)
    gecorrigeerd_wp: int | None = Field(default=None, ge=0)
    bron_volledig_ingelezen: bool | None = None
    extractie_reason_code: str | None = Field(default=None, max_length=50)


ACCEPT_REASON = "juiste_bron_bruikbaar_bewijs"
SUPPORT_REASON = "juiste_bron_relevante_context"
REJECT_REASONS = {
    "verkeerde_organisatie",
    "verkeerde_scope",
    "verkeerd_jaar",
    "fte_geen_wp",
    "onvoldoende_bewijs",
    "bron_niet_toegankelijk",
    "duplicaat",
    "sterkere_bron_beschikbaar",
    "verouderde_bron",
    "anders",
}
WP_OORDELEN = {"correct", "te_laag", "te_hoog", "niet_te_bepalen", "geen_getal"}
EXTRACTIE_REASONS = {
    "personen_gemist",
    "personen_onterecht_meegeteld",
    "pagina_onvolledig_geladen",
    "informatie_in_afbeelding",
    "verkeerde_scope",
    "verkeerde_eenheid",
    "verouderde_informatie",
    "interpretatiefout",
    "afwijkende_definitie",
    "anders",
}


class ManualSourceBody(BaseModel):
    url: HttpUrl
    titel: str | None = Field(default=None, max_length=500)
    reden: str | None = Field(default=None, max_length=2000)


def _candidate_dict(
    candidate: BronKandidaat,
    gedeeld_met_vestigingen: int = 1,
) -> dict:
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
        "raw_data": candidate.raw_data,
        "status": candidate.status,
        "rang": candidate.rang,
        "review_reason_code": candidate.review_reason_code,
        "review_reason": candidate.review_reason,
        "bron_relevant": candidate.bron_relevant,
        "bron_volledig_ingelezen": candidate.bron_volledig_ingelezen,
        "wp_oordeel": candidate.wp_oordeel,
        "gecorrigeerd_wp": candidate.gecorrigeerd_wp,
        "extractie_reason_code": candidate.extractie_reason_code,
        "extractie_toelichting": candidate.extractie_toelichting,
        "gedeeld_met_vestigingen": gedeeld_met_vestigingen,
    }


def _run_diagnostiek(run: ResearchRun) -> dict:
    return (run.configuratie or {}).get("diagnostiek") or {}


def _run_kosten(run: ResearchRun) -> dict:
    return (run.configuratie or {}).get("kosten") or {}


def _onderzoekspaden(run: ResearchRun) -> list[dict]:
    """Houd oude runs met tekstpaden compatibel met het huidige API-contract."""
    legacy_status = {
        "pending": "wachtend",
        "running": "bezig",
        "completed": "afgerond",
        "error": "mislukt",
    }.get(run.status, "onbekend")
    return [
        {
            "route": item,
            "verplicht": True,
            "status": legacy_status,
            "reden": "route uit eerdere onderzoeksrun",
        }
        if isinstance(item, str) else item
        for item in (run.onderzoekspaden or [])
        if (
            (isinstance(item, str) and item)
            or (isinstance(item, dict) and item.get("route"))
        )
    ]


def _gedeelde_bronnen(
    db: Session,
    batch_id: str,
) -> dict[str, int]:
    return dict(
        db.query(
            BronKandidaat.canonical_url,
            func.count(func.distinct(BronKandidaat.company_id)),
        )
        .join(
            ResearchRun,
            ResearchRun.id == BronKandidaat.research_run_id,
        )
        .filter(ResearchRun.batch_id == batch_id)
        .group_by(BronKandidaat.canonical_url)
        .all()
    )


@router.get("/reviewer-statistics")
def get_reviewer_statistics(
    batch_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Vat expliciete reviewerbeslissingen samen, zonder data te wijzigen."""
    reviewed_query = (
        db.query(BronKandidaat)
        .join(ResearchRun, ResearchRun.id == BronKandidaat.research_run_id)
        .filter(
            BronKandidaat.reviewed_at.is_not(None),
            BronKandidaat.brontype != "handmatig",
            BronKandidaat.status.in_(
                {"geaccepteerd", "alternatief", "afgewezen"},
            ),
        )
    )
    completed_runs_query = db.query(ResearchRun).filter_by(status="completed")
    candidates_query = (
        db.query(BronKandidaat)
        .join(ResearchRun, ResearchRun.id == BronKandidaat.research_run_id)
        .filter(
            ResearchRun.status == "completed",
            BronKandidaat.brontype != "handmatig",
        )
    )
    if batch_id:
        reviewed_query = reviewed_query.filter(ResearchRun.batch_id == batch_id)
        completed_runs_query = completed_runs_query.filter_by(batch_id=batch_id)
        candidates_query = candidates_query.filter(
            ResearchRun.batch_id == batch_id,
        )

    reviewed = reviewed_query.all()
    accepted = [
        item for item in reviewed
        if item.status in {"geaccepteerd", "alternatief"}
    ]
    rejected = [item for item in reviewed if item.status == "afgewezen"]
    rank_counts = Counter(
        str(item.rang) for item in accepted if item.rang is not None
    )
    reason_counts = Counter(
        item.review_reason_code
        or (item.review_reason.strip() if item.review_reason else "onbekend")
        for item in rejected
    )
    decision_count = len(reviewed)
    completed_runs = completed_runs_query.count()

    return {
        "batch_id": batch_id,
        "beoordeelde_bronnen": decision_count,
        "geaccepteerd": len(accepted),
        "afgewezen": len(rejected),
        "acceptatiepercentage": (
            round(len(accepted) / decision_count * 100, 1)
            if decision_count else None
        ),
        "geaccepteerde_rangen": dict(
            sorted(rank_counts.items(), key=lambda item: int(item[0])),
        ),
        "rang_1_percentage": (
            round(rank_counts.get("1", 0) / len(accepted) * 100, 1)
            if accepted else None
        ),
        "afwijsredenen": [
            {"reden": reason, "aantal": count}
            for reason, count in reason_counts.most_common()
        ],
        "afgeronde_runs": completed_runs,
        "gemiddeld_kandidaten_per_run": (
            round(candidates_query.count() / completed_runs, 1)
            if completed_runs else None
        ),
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
    return {
        "run_id": run.id,
        "status": run.status,
        "onderzoekspaden": _onderzoekspaden(run),
    }


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
    gedeelde_bronnen = _gedeelde_bronnen(db, run.batch_id)
    return {
        "id": run.id,
        "company_id": run.company_id,
        "status": run.status,
        "resultaat_status": run.resultaat_status,
        "gevraagd_jaar": run.gevraagd_jaar,
        "onderzoekspaden": _onderzoekspaden(run),
        "fout": run.fout,
        "kosten": _run_kosten(run),
        "diagnostiek": _run_diagnostiek(run),
        "kandidaten": [
            _candidate_dict(
                item,
                gedeelde_bronnen.get(item.canonical_url, 1),
            )
            for item in kandidaten
        ],
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
        return {"items": [], "gevraagd_jaar": None, "diagnostiek": {},
                "kosten": {}, "onderzoekspaden": []}
    kandidaten = (
        db.query(BronKandidaat)
        .filter_by(research_run_id=laatste_run.id)
        .order_by(BronKandidaat.rang)
        .all()
    )
    gedeelde_bronnen = _gedeelde_bronnen(db, laatste_run.batch_id)
    return {
        "items": [
            _candidate_dict(
                item,
                gedeelde_bronnen.get(item.canonical_url, 1),
            )
            for item in kandidaten
        ],
        # Het jaar dat déze run vroeg, zodat de bronkaart het niet hoeft te
        # raden uit het batchjaar. Een monitoringronde en een handmatig gestarte
        # run kunnen een ander gevraagd_jaar hebben.
        "gevraagd_jaar": laatste_run.gevraagd_jaar,
        "kosten": _run_kosten(laatste_run),
        "diagnostiek": _run_diagnostiek(laatste_run),
        "onderzoekspaden": _onderzoekspaden(laatste_run),
    }


@router.post("/candidates/{candidate_id}/review")
def review_candidate(
    candidate_id: str,
    body: ReviewBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.beslissing not in {"accepteren", "ondersteunen", "afwijzen"}:
        raise HTTPException(
            422,
            "beslissing moet accepteren, ondersteunen of afwijzen zijn",
        )
    candidate = db.get(BronKandidaat, candidate_id)
    if candidate is None:
        raise HTTPException(404, "bronkandidaat niet gevonden")
    if body.beslissing == "afwijzen":
        if body.reason_code not in REJECT_REASONS:
            raise HTTPException(422, "kies een geldige afwijsreden")
        if body.reason_code == "anders" and not (body.reden or "").strip():
            raise HTTPException(422, "een toelichting is verplicht bij 'anders'")
    elif body.reason_code not in {None, ACCEPT_REASON, SUPPORT_REASON}:
        raise HTTPException(422, "deze reden hoort niet bij een positieve beoordeling")
    if body.wp_oordeel not in WP_OORDELEN | {None}:
        raise HTTPException(422, "kies een geldig oordeel over het gevonden WP")
    if body.extractie_reason_code not in EXTRACTIE_REASONS | {None}:
        raise HTTPException(422, "kies een geldige extractiereden")
    if body.wp_oordeel in {"te_laag", "te_hoog"}:
        if candidate.wp_gevonden is None or body.gecorrigeerd_wp is None:
            raise HTTPException(422, "een WP-correctie vereist beide aantallen")
        if body.extractie_reason_code is None:
            raise HTTPException(422, "kies waarom het gevonden WP afwijkt")
        if body.wp_oordeel == "te_laag" and body.gecorrigeerd_wp <= candidate.wp_gevonden:
            raise HTTPException(422, "het gecorrigeerde WP moet hoger zijn")
        if body.wp_oordeel == "te_hoog" and body.gecorrigeerd_wp >= candidate.wp_gevonden:
            raise HTTPException(422, "het gecorrigeerde WP moet lager zijn")
    elif body.gecorrigeerd_wp is not None:
        raise HTTPException(422, "een correctie hoort alleen bij te laag of te hoog")
    if (
        body.extractie_reason_code == "anders"
        and not (body.reden or "").strip()
    ):
        raise HTTPException(422, "een toelichting is verplicht bij 'anders'")

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
        candidate.review_reason_code = ACCEPT_REASON
        candidate.bron_relevant = True
    elif body.beslissing == "ondersteunen":
        candidate.status = "alternatief"
        candidate.review_reason_code = SUPPORT_REASON
        candidate.bron_relevant = True
    else:
        candidate.status = "afgewezen"
        candidate.review_reason_code = body.reason_code
        candidate.bron_relevant = False

    candidate.reviewed_by = current_user.id
    candidate.reviewed_at = _now()
    candidate.review_reason = body.reden
    if body.beslissing != "afwijzen":
        candidate.wp_oordeel = body.wp_oordeel or (
            "correct" if candidate.wp_gevonden is not None else "geen_getal"
        )
        candidate.gecorrigeerd_wp = body.gecorrigeerd_wp
        candidate.bron_volledig_ingelezen = body.bron_volledig_ingelezen
        candidate.extractie_reason_code = body.extractie_reason_code
        candidate.extractie_toelichting = body.reden
    else:
        candidate.wp_oordeel = None
        candidate.gecorrigeerd_wp = None
        candidate.bron_volledig_ingelezen = None
        candidate.extractie_reason_code = None
        candidate.extractie_toelichting = None
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
        review_reason_code=ACCEPT_REASON,
        review_reason=body.reden,
        bron_relevant=True,
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
