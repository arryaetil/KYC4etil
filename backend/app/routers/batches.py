import csv
import io
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import SessionLocal, get_db
from ..models import (AgentResult, Batch, BronKandidaat, CallListItem, Candidate,
                      ChatSession, Company, Enrichment, JaarverslagMonitoring,
                      PipelineRun, ResearchRun, User, VastgoedRecord, WPRecord)
from ..pipeline.runner import run_batch, verwerk_company
from ..research.service import run_research_batch

router = APIRouter(prefix="/batches", tags=["batches"], dependencies=[Depends(get_current_user)])

CSV_VELDEN = {"naam"}  # minimaal vereist
MONITORINGLIJST_NAAM_MARKERS = ("monitoringlijst", "monitorlijst", "watchlist")


def _lijkt_monitoringlijst_batch(batch: Batch) -> bool:
    naam = (batch.naam or "").lower()
    return any(marker in naam for marker in MONITORINGLIJST_NAAM_MARKERS)


def _latest_research_maps(
    db: Session,
    batch_id: str,
) -> tuple[dict[str, ResearchRun], dict[str, BronKandidaat], set[str]]:
    latest_runs: dict[str, ResearchRun] = {}
    for run in (
        db.query(ResearchRun)
        .filter_by(batch_id=batch_id)
        .order_by(ResearchRun.created_at.desc())
    ):
        latest_runs.setdefault(run.company_id, run)

    run_ids = [run.id for run in latest_runs.values()]
    top_candidates: dict[str, BronKandidaat] = {}
    accepted_run_ids: set[str] = set()
    if run_ids:
        candidates = (
            db.query(BronKandidaat)
            .filter(BronKandidaat.research_run_id.in_(run_ids))
            .order_by(BronKandidaat.rang, BronKandidaat.created_at)
            .all()
        )
        for candidate in candidates:
            top_candidates.setdefault(candidate.research_run_id, candidate)
            if candidate.status == "geaccepteerd":
                accepted_run_ids.add(candidate.research_run_id)
                top_candidates[candidate.research_run_id] = candidate
    return latest_runs, top_candidates, accepted_run_ids


def run_batch_background(batch_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(run_batch(db, batch_id))
    finally:
        db.close()


def run_research_batch_background(batch_id: str) -> None:
    asyncio.run(run_research_batch(batch_id))


def run_single_background(company_id: str, batch_id: str) -> None:
    db = SessionLocal()
    try:
        company = db.get(Company, company_id)
        batch = db.get(Batch, batch_id)
        asyncio.run(verwerk_company(db, company, batch))
        db.commit()
    except Exception as exc:
        db.rollback()
        db.add(PipelineRun(batch_id=batch_id, company_id=company_id,
                           stap="herverwerk", status="error", duur_ms=0,
                           error=str(exc)[:1000]))
        db.commit()
    finally:
        db.close()


@router.post("/upload")
async def upload_batch(file: UploadFile, naam: str | None = None,
                       jaar: int | None = None, monitoringlijst: bool = False,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    """CSV-upload -> batch + companies. Verwachte kolommen (flexibel):
    vestigingsnummer, naam, gemeente, adres, sbi_code, cb_er, kvk_nummer.
    monitoringlijst=true markeert deze batch als de actieve jaarverslag-watchlist
    en ontmarkeert automatisch een eventuele vorige watchlist."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows or not CSV_VELDEN.issubset({k.strip().lower() for k in rows[0]}):
        raise HTTPException(422, "CSV mist verplichte kolom 'naam'")

    if monitoringlijst:
        db.query(Batch).filter_by(is_monitoringlijst=True).update(
            {"is_monitoringlijst": False})

    batch = Batch(naam=naam or file.filename, jaar=jaar or datetime.now(timezone.utc).replace(tzinfo=None).year,
                  totaal=len(rows), is_monitoringlijst=monitoringlijst,
                  geupload_door=current_user.id)
    db.add(batch)
    db.flush()
    for r in rows:
        r = {k.strip().lower(): (v.strip() if v else None) for k, v in r.items()}
        db.add(Company(batch_id=batch.id, vestigingsnummer=r.get("vestigingsnummer"),
                       naam=r["naam"], gemeente=r.get("gemeente"), adres=r.get("adres"),
                       sbi_code=r.get("sbi_code"), cb_er=r.get("cb_er"),
                       kvk_nummer=r.get("kvk_nummer"), website_url=r.get("website_url"),
                       telefoonnummer=r.get("telefoonnummer")))
    db.commit()
    return {"batch_id": batch.id, "aantal_companies": len(rows)}


@router.post("/{batch_id}/run")
async def start_batch(batch_id: str, background_tasks: BackgroundTasks,
                      db: Session = Depends(get_db)):
    """Start standaard de autonome bronnenresearch voor de volledige batch."""
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, f"batch {batch_id} bestaat niet")
    if batch.status == "running":
        return {"batch_id": batch.id, "status": batch.status, "verwerkt": batch.verwerkt,
                "totaal": batch.totaal}

    batch.status = "running"
    batch.verwerkt = 0
    batch.completed_at = None
    db.commit()
    background_tasks.add_task(run_research_batch_background, batch.id)
    return {"batch_id": batch.id, "status": batch.status, "verwerkt": batch.verwerkt,
            "totaal": batch.totaal, "workflow": "autonome_bronnenresearch"}


@router.post("/{batch_id}/run-legacy")
async def start_legacy_batch(
    batch_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start de voormalige WP-pipeline uitsluitend voor interne vergelijking."""
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, f"batch {batch_id} bestaat niet")
    if batch.status == "running":
        raise HTTPException(409, "batch draait al")
    batch.status = "running"
    batch.verwerkt = 0
    batch.completed_at = None
    db.commit()
    background_tasks.add_task(run_batch_background, batch.id)
    return {
        "batch_id": batch.id,
        "status": batch.status,
        "verwerkt": batch.verwerkt,
        "totaal": batch.totaal,
        "workflow": "legacy_pipeline",
    }


@router.post("/{batch_id}/cancel")
def cancel_batch(batch_id: str, db: Session = Depends(get_db)):
    """Annuleert een lopende batch. De achtergrondtaak stopt na de huidige vestiging."""
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "batch niet gevonden")
    if batch.status != "running":
        raise HTTPException(409, f"batch heeft status '{batch.status}', niet 'running'")
    batch.status = "cancelled"
    db.commit()
    return {"batch_id": batch.id, "status": batch.status}


@router.post("/{batch_id}/reset-vastgelopen")
def reset_vastgelopen(batch_id: str, db: Session = Depends(get_db)):
    """Zet een vastzittende 'running'-batch terug naar 'pending' na een server-herstart.
    Alleen bedoeld als de achtergrondtaak aantoonbaar niet meer draait (bijv. na deploy).
    Veilig: maakt geen data aan of verwijdert niets — wijzigt alleen de batch-status."""
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "batch niet gevonden")
    if batch.status != "running":
        raise HTTPException(409, f"batch heeft status '{batch.status}'; alleen 'running' batches kunnen worden gereset")
    batch.status = "pending"
    db.commit()
    return {"batch_id": batch.id, "status": batch.status, "bericht": "batch teruggezet naar 'pending'; kan opnieuw gestart worden"}


@router.delete("/{batch_id}")
def delete_batch(batch_id: str, db: Session = Depends(get_db)):
    """Verwijdert een batch en alle gekoppelde records. Blokkeert bij status 'running'."""
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "batch niet gevonden")
    if batch.status == "running":
        raise HTTPException(409, "batch draait nog; annuleer eerst")

    company_ids = [c.id for c in db.query(Company).filter_by(batch_id=batch_id)]

    if company_ids:
        db.query(CallListItem).filter(CallListItem.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(WPRecord).filter(WPRecord.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(ChatSession).filter(ChatSession.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(Candidate).filter(Candidate.batch_id == batch_id).delete(synchronize_session=False)
        db.query(AgentResult).filter(AgentResult.batch_id == batch_id).delete(synchronize_session=False)
        db.query(Enrichment).filter(Enrichment.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(JaarverslagMonitoring).filter(JaarverslagMonitoring.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(BronKandidaat).filter(BronKandidaat.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(ResearchRun).filter(ResearchRun.company_id.in_(company_ids)).delete(synchronize_session=False)

    db.query(PipelineRun).filter_by(batch_id=batch_id).delete(synchronize_session=False)
    db.query(Company).filter_by(batch_id=batch_id).delete(synchronize_session=False)
    db.delete(batch)
    db.commit()
    return {"deleted": batch_id}


@router.get("/companies/zoeken")
def zoek_companies(q: str = "", db: Session = Depends(get_db)):
    """Globale bedrijvenzoek voor dropdowns — zoekt op naam over alle batches."""
    query = db.query(Company, Batch.naam.label("batch_naam")).join(Batch, Batch.id == Company.batch_id)
    if q:
        query = query.filter(Company.naam.ilike(f"%{q}%"))
    rows = query.order_by(Company.naam).limit(50).all()
    return [
        {"id": c.id, "naam": c.naam, "gemeente": c.gemeente, "batch_naam": batch_naam}
        for c, batch_naam in rows
    ]


@router.get("")
def list_batches(db: Session = Depends(get_db)):
    labels_by_batch: dict[str, dict[str, int]] = {}
    for batch_id, label, aantal in (
        db.query(Candidate.batch_id, Candidate.confidence_label, func.count())
        .group_by(Candidate.batch_id, Candidate.confidence_label)
        .all()
    ):
        labels_by_batch.setdefault(
            batch_id, {"hoog": 0, "middel": 0, "laag": 0},
        )[label] = aantal
    fouten_by_batch = dict(
        db.query(PipelineRun.batch_id, func.count())
        .filter(PipelineRun.status == "error")
        .group_by(PipelineRun.batch_id)
        .all()
    )
    batches = [b for b in db.query(Batch).filter(Batch.is_monitoringlijst.isnot(True))
               .order_by(Batch.created_at.desc()).all()
               if not _lijkt_monitoringlijst_batch(b)]
    uploader_ids = {b.geupload_door for b in batches if b.geupload_door}
    naam_per_id: dict[str, str] = {}
    if uploader_ids:
        for user in db.query(User).filter(User.id.in_(uploader_ids)):
            naam_per_id[user.id] = user.naam
    return [{"id": b.id, "naam": b.naam, "jaar": b.jaar, "status": b.status,
             "totaal": b.totaal, "verwerkt": b.verwerkt,
             "labels": labels_by_batch.get(
                 b.id, {"hoog": 0, "middel": 0, "laag": 0},
             ),
             "fouten": fouten_by_batch.get(b.id, 0),
             "created_at": b.created_at.isoformat() + "Z" if b.created_at else None,
             "completed_at": b.completed_at.isoformat() + "Z" if b.completed_at else None,
             "geupload_door_naam": naam_per_id.get(b.geupload_door)}
            for b in batches]


@router.get("/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    b = db.get(Batch, batch_id)
    if not b:
        raise HTTPException(404, "batch niet gevonden")
    labels = {"hoog": 0, "middel": 0, "laag": 0}
    for c in db.query(Candidate).filter_by(batch_id=batch_id):
        if c.confidence_label in labels:
            labels[c.confidence_label] += 1
    fouten = db.query(PipelineRun).filter_by(batch_id=batch_id, status="error").count()
    company_ids = [c.id for c in db.query(Company.id).filter_by(batch_id=batch_id)]
    chat_sessies_open = (
        db.query(ChatSession)
        .filter(ChatSession.company_id.in_(company_ids),
                ChatSession.status == "completed",
                ChatSession.verwerkt == False)  # noqa: E712
        .count()
    ) if company_ids else 0
    latest_runs, top_candidates, accepted_run_ids = _latest_research_maps(
        db, batch_id,
    )
    research = {
        "gestart": len(latest_runs),
        "afgerond": sum(run.status == "completed" for run in latest_runs.values()),
        "review_nodig": sum(
            run.status == "completed"
            and run.id not in accepted_run_ids
            and run.id in top_candidates
            for run in latest_runs.values()
        ),
        "geaccepteerd": len(accepted_run_ids),
        "niet_gevonden": sum(
            run.status == "completed"
            and run.resultaat_status == "niet_gevonden"
            for run in latest_runs.values()
        ),
        "fouten": sum(run.status == "error" for run in latest_runs.values()),
    }
    return {"id": b.id, "naam": b.naam, "jaar": b.jaar, "status": b.status,
            "totaal": b.totaal, "verwerkt": b.verwerkt, "labels": labels, "fouten": fouten,
            "workflow": "autonome_bronnenresearch", "research": research,
            "chat_sessies_open": chat_sessies_open,
            "created_at": b.created_at.isoformat() + "Z" if b.created_at else None,
            "completed_at": b.completed_at.isoformat() + "Z" if b.completed_at else None}


@router.post("/{batch_id}/companies/{company_id}/herverwerk")
async def herverwerk_company(batch_id: str, company_id: str,
                              background_tasks: BackgroundTasks,
                              db: Session = Depends(get_db)):
    """Verwijdert de vorige run-data voor dit bedrijf en verwerkt het opnieuw."""
    comp = db.get(Company, company_id)
    if not comp or comp.batch_id != batch_id:
        raise HTTPException(404, "company niet gevonden")
    batch = db.get(Batch, batch_id)
    if batch.status == "running":
        raise HTTPException(409, "batch draait al; wacht tot hij klaar is")

    if comp.enrichment:
        db.delete(comp.enrichment)
    if comp.candidate:
        db.delete(comp.candidate)
    for ar in list(comp.agent_results):
        db.delete(ar)
    db.query(PipelineRun).filter_by(company_id=company_id, status="error").delete(
        synchronize_session=False)
    db.commit()

    background_tasks.add_task(run_single_background, company_id, batch_id)
    return {"status": "gestart", "company_id": company_id}


@router.get("/{batch_id}/companies")
def list_companies(batch_id: str, label: str | None = None, db: Session = Depends(get_db)):
    # Één query voor alle pipeline-fouten — voorkomt N+1
    fouten_map: dict[str, str] = {}
    for pr in (db.query(PipelineRun)
               .filter_by(batch_id=batch_id, status="error")
               .order_by(PipelineRun.created_at)):
        if pr.company_id:
            fouten_map[pr.company_id] = pr.error or "onbekende fout"

    # Losse WP-vondsten die niet als officiële kandidaat zijn gekozen (bv. afgewezen
    # door een hard gate) -- als ruwe indicatie tonen i.p.v. niets, zodat de reviewer
    # altijd een getal ziet zodra er iets gevonden is (het label/de kleur blijft het
    # vertrouwenssignaal, dit getal is uitdrukkelijk niet bevestigd).
    ruwe_wp_map: dict[str, int] = {}
    for ar in (db.query(AgentResult)
               .filter_by(batch_id=batch_id)
               .filter(AgentResult.wp_gevonden.isnot(None))
               .order_by(AgentResult.created_at)):
        ruwe_wp_map.setdefault(ar.company_id, ar.wp_gevonden)

    latest_runs, top_candidates, accepted_run_ids = _latest_research_maps(
        db, batch_id,
    )

    out = []
    for comp in db.query(Company).filter_by(batch_id=batch_id):
        cand = comp.candidate
        if label and (not cand or cand.confidence_label != label):
            continue
        heeft_kandidaat = cand is not None and cand.wp_kandidaat is not None
        research_run = latest_runs.get(comp.id)
        research_top = (
            top_candidates.get(research_run.id) if research_run else None
        )
        legacy_wp = cand.wp_kandidaat if cand else None
        research_wp_raw = research_top.wp_gevonden if research_top else None
        research_wp_bruikbaar = bool(
            research_top
            and research_top.eenheid == "werkzame_personen"
            and research_top.scope_class in {"vestiging", "limburg"}
        )
        research_wp = research_wp_raw if research_wp_bruikbaar else None
        verschil_abs = (
            research_wp - legacy_wp
            if research_wp is not None and legacy_wp is not None
            else None
        )
        if verschil_abs == 0:
            vergelijking = "gelijk"
        elif verschil_abs is not None:
            vergelijking = "afwijkend"
        elif research_wp is not None:
            vergelijking = "alleen_research"
        elif legacy_wp is not None:
            vergelijking = "alleen_legacy"
        else:
            vergelijking = "onvoldoende"
        out.append({
            "company_id": comp.id, "naam": comp.naam, "gemeente": comp.gemeente,
            "vestigingsnummer": comp.vestigingsnummer, "cb_er": comp.cb_er,
            "kvk_nummer": comp.kvk_nummer, "sbi_omschrijving": comp.sbi_omschrijving,
            "afgewerkt": comp.afgewerkt,
            "wp_kandidaat": cand.wp_kandidaat if cand else None,
            "wp_gevonden_ruw": None if heeft_kandidaat else ruwe_wp_map.get(comp.id),
            "is_schatting": cand.is_schatting if cand else None,
            "confidence_score": cand.confidence_score if cand else None,
            "confidence_label": cand.confidence_label if cand else None,
            "strategie": cand.strategie if cand else None,
            "status": cand.status if cand else None,
            "pipeline_error": fouten_map.get(comp.id),
            "legacy_wp": legacy_wp,
            "research_run_id": research_run.id if research_run else None,
            "research_status": research_run.status if research_run else "niet_gestart",
            "research_resultaat_status": (
                research_run.resultaat_status if research_run else None
            ),
            "research_top_id": research_top.id if research_top else None,
            "research_top_url": research_top.url if research_top else None,
            "research_top_titel": research_top.titel if research_top else None,
            "research_top_type": research_top.brontype if research_top else None,
            "research_top_wp": research_wp,
            "research_top_wp_raw": research_wp_raw,
            "research_top_wp_bruikbaar": research_wp_bruikbaar,
            "research_top_scope": research_top.scope_class if research_top else None,
            "research_top_score": (
                research_top.ranking_score if research_top else None
            ),
            "research_review_status": (
                "geaccepteerd"
                if research_run and research_run.id in accepted_run_ids
                else research_top.status if research_top else None
            ),
            "verschil_abs": verschil_abs,
            "vergelijking": vergelijking,
        })
    return out


@router.get("/{batch_id}/companies/{company_id}")
def company_detail(batch_id: str, company_id: str, db: Session = Depends(get_db)):
    comp = db.get(Company, company_id)
    if not comp or comp.batch_id != batch_id:
        raise HTTPException(404, "company niet gevonden")
    batch = db.get(Batch, batch_id)
    enr: Enrichment | None = comp.enrichment
    cand: Candidate | None = comp.candidate
    vorige = None
    if batch:
        prev_rec = (db.query(WPRecord)
                    .filter(WPRecord.company_id == company_id, WPRecord.wp_jaar < batch.jaar)
                    .order_by(WPRecord.wp_jaar.desc(), WPRecord.created_at.desc())
                    .first())
        if prev_rec:
            delta = cand.wp_kandidaat - prev_rec.wp_waarde if cand and cand.wp_kandidaat is not None else None
            pct_delta = (abs(delta) / prev_rec.wp_waarde) if delta is not None and prev_rec.wp_waarde else None
            vorige = {
                "wp_jaar": prev_rec.wp_jaar,
                "wp_waarde": prev_rec.wp_waarde,
                "bron_type": prev_rec.bron_type,
                "status": prev_rec.status,
                "bron_url": prev_rec.bron_url,
                "goedgekeurd_op": prev_rec.goedgekeurd_op.isoformat() + "Z" if prev_rec.goedgekeurd_op else None,
                "verschil_abs": delta,
                "verschil_pct": pct_delta,
                "signaal": "hoog" if pct_delta is not None and pct_delta > 0.25 else "normaal",
            }
    return {
        "company": {"id": comp.id, "naam": comp.naam, "adres": comp.adres,
                    "gemeente": comp.gemeente, "sbi_code": comp.sbi_code,
                    "cb_er": comp.cb_er, "kvk_nummer": comp.kvk_nummer,
                    "website_url": comp.website_url, "telefoonnummer": comp.telefoonnummer},
        "enrichment": enr and {
            "website_url": enr.website_url, "telefoonnummer": enr.telefoonnummer,
            "email": enr.email,
            "locatie_count_nl": enr.locatie_count_nl, "locatie_count_lb": enr.locatie_count_lb,
            "locatie_bron": enr.locatie_bron, "adres_validated": enr.adres_validated,
            "lookup_failed": enr.lookup_failed},
        "agent_results": [{
            "agent_type": ar.agent_type, "wp_gevonden": ar.wp_gevonden,
            "context": ar.wp_context, "bron_url": ar.bron_url, "bron_type": ar.bron_type,
            "is_limburg_specifiek": ar.is_limburg_specifiek, "is_fte": ar.is_fte,
            "peilmoment": ar.peilmoment, "llm_zekerheid": ar.llm_zekerheid,
            "eigen_personeel": ar.eigen_personeel, "uitzend": ar.uitzend,
            "detachering": ar.detachering, "wsw": ar.wsw,
            "man": ar.man, "vrouw": ar.vrouw,
            "voltijd": ar.voltijd, "deeltijd": ar.deeltijd,
            "pct_op_locatie": ar.pct_op_locatie, "bron_pagina": ar.bron_pagina,
            "identity_class": ar.identity_class, "scope_class": ar.scope_class,
        } for ar in comp.agent_results],
        "pipeline_fouten": [{
            "stap": pr.stap, "error": pr.error,
            "created_at": pr.created_at.isoformat() + "Z" if pr.created_at else None,
        } for pr in db.query(PipelineRun).filter_by(
            company_id=company_id, status="error").order_by(PipelineRun.created_at).all()],
        "candidate": cand and {
            "id": cand.id, "wp_kandidaat": cand.wp_kandidaat,
            "is_schatting": cand.is_schatting,
            "reconciliatie_reden": cand.reconciliatie_reden,
            "confidence_score": cand.confidence_score,
            "confidence_label": cand.confidence_label,
            "score_breakdown": cand.score_breakdown,
            "strategie": cand.strategie, "status": cand.status,
            "reviewer_signaal": cand.reviewer_signaal},
        "vorig_jaar": vorige,
        "wp_historie": [{
            "wp_jaar": r.wp_jaar, "wp_waarde": r.wp_waarde,
            "bron_type": r.bron_type, "status": r.status,
            "eigen_personeel": r.eigen_personeel, "uitzend": r.uitzend,
            "detachering": r.detachering, "wsw": r.wsw,
            "man": r.man, "vrouw": r.vrouw,
            "voltijd": r.voltijd, "deeltijd": r.deeltijd,
            "pct_op_locatie": r.pct_op_locatie,
            "goedgekeurd_op": r.goedgekeurd_op.isoformat() + "Z" if r.goedgekeurd_op else None,
        } for r in db.query(WPRecord).filter_by(company_id=company_id)
                       .order_by(WPRecord.wp_jaar.desc()).all()],
        "vastgoed": comp.vastgoed and {
            "perceel_opp": comp.vastgoed.perceel_opp,
            "winkel_opp": comp.vastgoed.winkel_opp,
            "kantoor_opp": comp.vastgoed.kantoor_opp,
            "bedrijfs_opp": comp.vastgoed.bedrijfs_opp,
            "uitbreidingsruimte": comp.vastgoed.uitbreidingsruimte,
            "seizoensverschillen": comp.vastgoed.seizoensverschillen,
            "seizoen_toelichting": comp.vastgoed.seizoen_toelichting,
            "correspondentieadres": comp.vastgoed.correspondentieadres,
            "bron": comp.vastgoed.bron,
            "updated_at": comp.vastgoed.updated_at.isoformat() + "Z" if comp.vastgoed.updated_at else None,
        },
    }


class CompanyUpdateBody(BaseModel):
    naam: str | None = None
    gemeente: str | None = None
    adres: str | None = None
    sbi_code: str | None = None
    cb_er: str | None = None
    kvk_nummer: str | None = None
    afgewerkt: bool | None = None
    website_url: str | None = None
    telefoonnummer: str | None = None
    email: str | None = None


_COMPANY_FIELDS = {"naam", "gemeente", "adres", "sbi_code", "cb_er", "kvk_nummer", "afgewerkt"}
_ENRICHMENT_FIELDS = {"website_url", "telefoonnummer", "email"}


@router.patch("/{batch_id}/companies/{company_id}")
def update_company(batch_id: str, company_id: str, body: CompanyUpdateBody,
                   db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    """Werkt vestigingsgegevens en contactvelden bij."""
    comp = db.get(Company, company_id)
    if not comp or comp.batch_id != batch_id:
        raise HTTPException(404, "company niet gevonden")
    data = body.model_dump(exclude_unset=True)
    for field in _COMPANY_FIELDS & data.keys():
        setattr(comp, field, data[field])
    contact = {f: data[f] for f in _ENRICHMENT_FIELDS if f in data}
    if contact:
        enr = comp.enrichment
        if enr is None:
            enr = Enrichment(company_id=company_id)
            db.add(enr)
        for field, value in contact.items():
            setattr(enr, field, value)
    db.commit()
    return {"company_id": company_id}


class WpUitsplitsingBody(BaseModel):
    man: int | None = None
    vrouw: int | None = None
    voltijd: int | None = None
    deeltijd: int | None = None
    eigen_personeel: int | None = None
    uitzend: int | None = None
    detachering: int | None = None
    wsw: int | None = None
    pct_op_locatie: float | None = None


@router.put("/{batch_id}/companies/{company_id}/wp-uitsplitsing")
def update_wp_uitsplitsing(batch_id: str, company_id: str, body: WpUitsplitsingBody,
                            db: Session = Depends(get_db),
                            current_user=Depends(get_current_user)):
    """Werkt de uitsplitsingsvelden bij op het meest recente WP-record van de vestiging."""
    comp = db.get(Company, company_id)
    if not comp or comp.batch_id != batch_id:
        raise HTTPException(404, "company niet gevonden")

    record = (db.query(WPRecord)
              .filter_by(company_id=company_id)
              .order_by(WPRecord.wp_jaar.desc())
              .first())
    if not record:
        raise HTTPException(404, "geen WP-record gevonden — bevestig eerst een WP-waarde")

    for field, value in body.model_dump(exclude_unset=False).items():
        setattr(record, field, value)
    db.commit()
    return {"company_id": company_id, "wp_jaar": record.wp_jaar}


class VastgoedBody(BaseModel):
    perceel_opp: int | None = None
    winkel_opp: int | None = None
    kantoor_opp: int | None = None
    bedrijfs_opp: int | None = None
    uitbreidingsruimte: bool | None = None
    seizoensverschillen: bool | None = None
    seizoen_toelichting: str | None = None
    correspondentieadres: str | None = None


@router.put("/{batch_id}/companies/{company_id}/vastgoed")
def upsert_vastgoed(batch_id: str, company_id: str, body: VastgoedBody,
                    db: Session = Depends(get_db),
                    current_user=Depends(get_current_user)):
    """Maakt een vastgoed-record aan of overschrijft het bestaande (upsert)."""
    comp = db.get(Company, company_id)
    if not comp or comp.batch_id != batch_id:
        raise HTTPException(404, "company niet gevonden")

    vg = comp.vastgoed
    if vg is None:
        vg = VastgoedRecord(company_id=company_id, bron="handmatig",
                            ingevoerd_door=current_user.id)
        db.add(vg)
    else:
        vg.bron = "handmatig"
        vg.ingevoerd_door = current_user.id

    for field, value in body.model_dump(exclude_unset=False).items():
        setattr(vg, field, value)
    vg.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"company_id": company_id, "bron": vg.bron,
            "updated_at": vg.updated_at.isoformat() + "Z"}
