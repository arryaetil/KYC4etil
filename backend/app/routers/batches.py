import csv
import io
import asyncio
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import SessionLocal, get_db
from ..models import (AgentResult, Batch, CallListItem, Candidate, ChatSession,
                      Company, Enrichment, PipelineRun, WPRecord)
from ..pipeline.runner import run_batch, verwerk_company

router = APIRouter(prefix="/batches", tags=["batches"], dependencies=[Depends(get_current_user)])

CSV_VELDEN = {"naam"}  # minimaal vereist


def run_batch_background(batch_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(run_batch(db, batch_id))
    finally:
        db.close()


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
                       jaar: int | None = None, db: Session = Depends(get_db)):
    """CSV-upload -> batch + companies. Verwachte kolommen (flexibel):
    vestigingsnummer, naam, gemeente, adres, sbi_code, cb_er, kvk_nummer."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows or not CSV_VELDEN.issubset({k.strip().lower() for k in rows[0]}):
        raise HTTPException(422, "CSV mist verplichte kolom 'naam'")

    batch = Batch(naam=naam or file.filename, jaar=jaar or datetime.utcnow().year,
                  totaal=len(rows))
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
    """Start de pipeline als achtergrondtaak; voortgang staat op GET /batches/{id}."""
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
    background_tasks.add_task(run_batch_background, batch.id)
    return {"batch_id": batch.id, "status": batch.status, "verwerkt": batch.verwerkt,
            "totaal": batch.totaal}


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

    db.query(PipelineRun).filter_by(batch_id=batch_id).delete(synchronize_session=False)
    db.query(Company).filter_by(batch_id=batch_id).delete(synchronize_session=False)
    db.delete(batch)
    db.commit()
    return {"deleted": batch_id}


@router.get("")
def list_batches(db: Session = Depends(get_db)):
    return [{"id": b.id, "naam": b.naam, "jaar": b.jaar, "status": b.status,
             "totaal": b.totaal, "verwerkt": b.verwerkt,
             "created_at": b.created_at.isoformat() + "Z" if b.created_at else None,
             "completed_at": b.completed_at.isoformat() + "Z" if b.completed_at else None}
            for b in db.query(Batch).order_by(Batch.created_at.desc()).all()]


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
    return {"id": b.id, "naam": b.naam, "jaar": b.jaar, "status": b.status,
            "totaal": b.totaal, "verwerkt": b.verwerkt, "labels": labels, "fouten": fouten,
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

    out = []
    for comp in db.query(Company).filter_by(batch_id=batch_id):
        cand = comp.candidate
        if label and (not cand or cand.confidence_label != label):
            continue
        out.append({
            "company_id": comp.id, "naam": comp.naam, "gemeente": comp.gemeente,
            "wp_kandidaat": cand.wp_kandidaat if cand else None,
            "is_schatting": cand.is_schatting if cand else None,
            "confidence_score": cand.confidence_score if cand else None,
            "confidence_label": cand.confidence_label if cand else None,
            "strategie": cand.strategie if cand else None,
            "status": cand.status if cand else None,
            "pipeline_error": fouten_map.get(comp.id),
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
            "strategie": cand.strategie, "status": cand.status},
        "vorig_jaar": vorige,
    }
