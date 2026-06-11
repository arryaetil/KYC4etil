import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AgentResult, Batch, CallListItem, Candidate, Company, WPRecord

router = APIRouter(tags=["review"])


class CorrectieBody(BaseModel):
    wp_waarde: int
    reden: str | None = None


def _maak_wp_record(db: Session, cand: Candidate, wp: int, status: str) -> WPRecord:
    comp = db.get(Company, cand.company_id)
    batch = db.get(Batch, cand.batch_id)
    ar = db.get(AgentResult, cand.gekozen_agent_result) if cand.gekozen_agent_result else None
    rec = WPRecord(company_id=comp.id, candidate_id=cand.id, wp_waarde=wp,
                   wp_jaar=batch.jaar, bron_type=(ar.bron_type if ar else "handmatig"),
                   bron_url=(ar.bron_url if ar else None), status=status,
                   goedgekeurd_op=datetime.utcnow())
    db.add(rec)
    return rec


@router.post("/candidates/{candidate_id}/approve")
def approve(candidate_id: str, db: Session = Depends(get_db)):
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, "candidate niet gevonden")
    if cand.wp_kandidaat is None:
        raise HTTPException(422, "geen kandidaat-waarde om goed te keuren")
    cand.status = "approved"
    rec = _maak_wp_record(db, cand, cand.wp_kandidaat, "reviewed")
    db.commit()
    return {"wp_record_id": rec.id, "wp_waarde": rec.wp_waarde}


@router.post("/candidates/{candidate_id}/correct")
def correct(candidate_id: str, body: CorrectieBody, db: Session = Depends(get_db)):
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, "candidate niet gevonden")
    cand.status = "corrected"
    cand.reconciliatie_reden = (cand.reconciliatie_reden or "") + f" | correctie: {body.reden or 'handmatig'}"
    rec = _maak_wp_record(db, cand, body.wp_waarde, "corrected")
    db.commit()
    return {"wp_record_id": rec.id, "wp_waarde": rec.wp_waarde}


@router.post("/batches/{batch_id}/approve-all-green")
def bulk_approve(batch_id: str, db: Session = Depends(get_db)):
    """Bulk-goedkeuring van alle 🟢-records (doc §11)."""
    n = 0
    for cand in db.query(Candidate).filter_by(batch_id=batch_id, confidence_label="hoog",
                                              status="pending"):
        if cand.wp_kandidaat is not None:
            cand.status = "approved"
            _maak_wp_record(db, cand, cand.wp_kandidaat, "reviewed")
            n += 1
    db.commit()
    return {"goedgekeurd": n}


@router.get("/batches/{batch_id}/export.csv")
def export_csv(batch_id: str, db: Session = Depends(get_db)):
    """Export van goedgekeurde records voor het Vestigingsregister."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["vestigingsnummer", "naam", "wp_waarde", "wp_jaar", "bron_type",
                "bron_url", "status"])
    for rec in (db.query(WPRecord).join(Company, WPRecord.company_id == Company.id)
                .filter(Company.batch_id == batch_id)):
        comp = db.get(Company, rec.company_id)
        w.writerow([comp.vestigingsnummer, comp.naam, rec.wp_waarde, rec.wp_jaar,
                    rec.bron_type, rec.bron_url, rec.status])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=export_{batch_id}.csv"})


@router.get("/batches/{batch_id}/bellijst.csv")
def export_bellijst(batch_id: str, db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["naam", "gemeente", "telefoonnummer", "reden", "status"])
    for item in (db.query(CallListItem).join(Company, CallListItem.company_id == Company.id)
                 .filter(Company.batch_id == batch_id)):
        comp = db.get(Company, item.company_id)
        w.writerow([comp.naam, comp.gemeente, item.telefoonnummer, item.reden, item.status])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=bellijst_{batch_id}.csv"})
