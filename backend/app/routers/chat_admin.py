"""Beheer-endpoints voor chat-templates en chat-sessies — auth vereist."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Candidate, ChatSession, ChatTemplate, Company, User, WPRecord

router = APIRouter(tags=["chat-admin"], dependencies=[Depends(get_current_user)])


# ── Templates ──────────────────────────────────────────────────────────────────

class TemplateBody(BaseModel):
    naam: str
    beschrijving: str | None = None
    vragen: list
    is_default: bool = False


@router.get("/chat-templates")
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(ChatTemplate).order_by(ChatTemplate.created_at).all()
    return [
        {
            "id": t.id,
            "naam": t.naam,
            "beschrijving": t.beschrijving,
            "vragen": t.vragen or [],
            "is_default": t.is_default,
            "aangemaakt_door": t.aangemaakt_door,
            "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
        }
        for t in templates
    ]


@router.post("/chat-templates")
def create_template(body: TemplateBody, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    if body.is_default:
        # Verwijder is_default van alle andere templates
        for t in db.query(ChatTemplate).filter_by(is_default=True).all():
            t.is_default = False
    template = ChatTemplate(
        id=str(uuid.uuid4()),
        naam=body.naam,
        beschrijving=body.beschrijving,
        vragen=body.vragen,
        is_default=body.is_default,
        aangemaakt_door=current_user.id,
    )
    db.add(template)
    db.commit()
    return {"id": template.id, "naam": template.naam, "is_default": template.is_default}


@router.put("/chat-templates/{template_id}")
def update_template(template_id: str, body: TemplateBody, db: Session = Depends(get_db)):
    template = db.get(ChatTemplate, template_id)
    if not template:
        raise HTTPException(404, "Template niet gevonden")
    if body.is_default and not template.is_default:
        for t in db.query(ChatTemplate).filter_by(is_default=True).all():
            t.is_default = False
    template.naam = body.naam
    template.beschrijving = body.beschrijving
    template.vragen = body.vragen
    template.is_default = body.is_default
    db.commit()
    return {"id": template.id, "naam": template.naam}


@router.delete("/chat-templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    template = db.get(ChatTemplate, template_id)
    if not template:
        raise HTTPException(404, "Template niet gevonden")
    if template.is_default:
        raise HTTPException(422, "Kan standaard-template niet verwijderen")
    db.delete(template)
    db.commit()
    return {"deleted": True}


# ── Chat-sessies ───────────────────────────────────────────────────────────────

@router.get("/batches/{batch_id}/chat-sessies")
def get_chat_sessies(batch_id: str, db: Session = Depends(get_db)):
    """Alle chat-sessies voor een batch, met bedrijfsinfo en antwoorden."""
    sessions = (
        db.query(ChatSession)
        .join(Company, ChatSession.company_id == Company.id)
        .filter(Company.batch_id == batch_id)
        .order_by(ChatSession.sent_at.desc().nullsfirst(), ChatSession.id)
        .all()
    )
    result = []
    for s in sessions:
        comp = db.get(Company, s.company_id)
        cand = comp.candidate if comp else None

        antwoorden = s.antwoorden or {}
        wp_opgegeven = antwoorden.get("wp_count") or antwoorden.get("wp_opgegeven")

        result.append({
            "id": s.id,
            "company_id": s.company_id,
            "naam": comp.naam if comp else "?",
            "gemeente": comp.gemeente if comp else None,
            "candidate_id": cand.id if cand else None,
            "wp_kandidaat": cand.wp_kandidaat if cand else None,
            "candidate_status": cand.status if cand else None,
            "variant": s.variant,
            "status": s.status,
            "verwerkt": s.verwerkt,
            "pre_fill_wp": s.pre_fill_wp,
            "wp_opgegeven": wp_opgegeven,
            "antwoorden": antwoorden,
            "vragen": s.vragen or [],
            "sent_at": s.sent_at.isoformat() + "Z" if s.sent_at else None,
            "completed_at": s.completed_at.isoformat() + "Z" if s.completed_at else None,
        })
    return result


@router.post("/chat-sessies/{session_id}/doorvoeren")
def doorvoeren_chat(session_id: str, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """Doorvoeren van het opgegeven WP-getal naar WPRecord."""
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(404, "Chat-sessie niet gevonden")
    if session.status != "completed":
        raise HTTPException(422, "Sessie is nog niet ingevuld door het bedrijf")
    if session.verwerkt:
        raise HTTPException(409, "Sessie is al doorvoerd")

    antwoorden = session.antwoorden or {}
    wp = antwoorden.get("wp_count") or antwoorden.get("wp_opgegeven")
    if not wp:
        raise HTTPException(422, "Geen WP-getal in antwoorden")

    comp = db.get(Company, session.company_id)
    if not comp:
        raise HTTPException(404, "Bedrijf niet gevonden")
    cand = comp.candidate
    if not cand:
        raise HTTPException(404, "Geen kandidaat gevonden voor dit bedrijf")

    from ..models import Batch
    b = db.get(Batch, cand.batch_id)

    cand.status = "corrected"
    cand.reconciliatie_reden = (cand.reconciliatie_reden or "") + \
        f" | chat-antwoord ({current_user.naam}): {wp} WP"
    rec = WPRecord(
        company_id=comp.id,
        candidate_id=cand.id,
        wp_waarde=int(wp),
        wp_jaar=b.jaar if b else datetime.now(timezone.utc).replace(tzinfo=None).year,
        bron_type="chat",
        bron_url=None,
        status="reviewed",
        goedgekeurd_door=current_user.id,
        goedgekeurd_op=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(rec)
    session.verwerkt = True
    db.commit()
    return {"wp_record_id": rec.id, "wp_waarde": rec.wp_waarde}
