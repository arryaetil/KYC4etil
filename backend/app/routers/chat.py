"""Publieke chat-endpoints — geen auth vereist. Bedrijven vullen hier hun WP-gegevens in."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..chat_service import get_chat_reply
from ..chat_utils import lookup_session
from ..database import get_db
from ..models import ChatSession, Company

router = APIRouter(prefix="/chat", tags=["chat"])

DEFAULT_VRAGEN = [
    {
        "id": "wp_count",
        "label": "Aantal werkzame personen",
        "type": "wp_count",
        "verplicht": True,
        "hint": "Headcount (niet FTE), peildatum 31 december vorig jaar",
    },
    {
        "id": "opmerking",
        "label": "Toelichting (optioneel)",
        "type": "text",
        "verplicht": False,
        "hint": "Bijv. deeltijdwerkers, seizoenspersoneel, uitzendkrachten…",
    },
]


@router.get("/{token}")
def get_chat_session(token: str, db: Session = Depends(get_db)):
    """Haalt chat-sessie op op basis van token. Geen auth vereist."""
    session = lookup_session(token, db)
    if session.status == "completed":
        return {"status": "completed"}
    if session.status in ("created", "sent"):
        session.status = "opened"
        db.commit()
    comp = db.get(Company, session.company_id)
    return {
        "bedrijfsnaam": comp.naam if comp else "Onbekend bedrijf",
        "gemeente": comp.gemeente if comp else None,
        "variant": session.variant,
        "pre_fill_wp": session.pre_fill_wp,
        "status": session.status,
        "vragen": session.vragen if session.vragen else DEFAULT_VRAGEN,
        "messages": session.messages or [],
    }


class ChatSubmit(BaseModel):
    antwoorden: dict  # {vraag_id: waarde}


@router.post("/{token}/submit")
def submit_chat(token: str, body: ChatSubmit, db: Session = Depends(get_db)):
    """Slaat antwoorden op en markeert de sessie als afgerond (fallback voor formulier)."""
    session = lookup_session(token, db)
    if session.status == "completed":
        raise HTTPException(409, "Deze link is al gebruikt")

    wp = body.antwoorden.get("wp_count") or body.antwoorden.get("wp_opgegeven")
    if wp is None:
        raise HTTPException(422, "Geen WP-getal ingevuld")
    try:
        wp = int(wp)
    except (TypeError, ValueError):
        raise HTTPException(422, "WP-getal moet een geheel getal zijn")
    if wp < 0:
        raise HTTPException(422, "WP-getal moet 0 of hoger zijn")

    session.antwoorden = body.antwoorden
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.commit()
    return {"status": "completed", "wp_opgegeven": wp}


class ChatMessageRequest(BaseModel):
    messages: list[dict]


@router.post("/{token}/message")
async def chat_message(token: str, body: ChatMessageRequest,
                       db: Session = Depends(get_db)):
    """Conversational chat endpoint — stuurt berichtgeschiedenis naar OpenAI."""
    session = lookup_session(token, db)
    if session.status == "completed":
        raise HTTPException(409, "Deze chat-sessie is al afgerond")

    if session.status in ("created", "sent"):
        session.status = "opened"

    comp = db.get(Company, session.company_id)
    enrichment = comp.enrichment if comp else None

    result = await get_chat_reply(body.messages, session, comp, enrichment)

    all_messages = list(body.messages)
    all_messages.append({"role": "assistant", "content": result["reply"]})
    session.messages = all_messages

    if result["done"]:
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        if result.get("antwoorden"):
            session.antwoorden = result["antwoorden"]

    db.commit()
    response_data = {"reply": result["reply"], "done": result["done"]}
    if result.get("gegevens") is not None:
        response_data["gegevens"] = result["gegevens"]
    return response_data
