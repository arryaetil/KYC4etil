"""Publieke chat-endpoints — geen auth vereist. Bedrijven vullen hier hun WP-gegevens in."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ChatSession, Company

router = APIRouter(prefix="/chat", tags=["chat"])

# Volledige vragenlijst conform ADO #1413 (Roger Vaessens)
VRAGEN_VOLLEDIG = [
    # --- Adresgegevens ---
    {
        "id": "adres",
        "label": "Adres vestiging",
        "type": "text",
        "verplicht": True,
        "hint": "Straat, huisnummer, postcode, plaats",
    },
    {
        "id": "correspondentie_adres",
        "label": "Correspondentieadres",
        "type": "text",
        "verplicht": False,
        "hint": "Alleen invullen als dit afwijkt van het vestigingsadres",
    },
    # --- Werkzame personen ---
    {
        "id": "wp_totaal",
        "label": "Aantal werkzame personen (totaal)",
        "type": "number",
        "verplicht": True,
        "hint": "Headcount (niet FTE), peildatum 31 december vorig jaar",
    },
    {
        "id": "wp_eigen",
        "label": "Waarvan eigen personeel",
        "type": "number",
        "verplicht": False,
        "hint": "Medewerkers direct in dienst bij uw organisatie",
    },
    {
        "id": "wp_uitzend",
        "label": "Waarvan uitzendkrachten",
        "type": "number",
        "verplicht": False,
        "hint": "",
    },
    {
        "id": "wp_detachering",
        "label": "Waarvan gedetacheerd personeel",
        "type": "number",
        "verplicht": False,
        "hint": "",
    },
    {
        "id": "wp_wsw",
        "label": "Waarvan WSW-medewerkers",
        "type": "number",
        "verplicht": False,
        "hint": "Wet Sociale Werkvoorziening",
    },
    {
        "id": "wp_man",
        "label": "Waarvan man",
        "type": "number",
        "verplicht": False,
        "hint": "",
    },
    {
        "id": "wp_vrouw",
        "label": "Waarvan vrouw",
        "type": "number",
        "verplicht": False,
        "hint": "",
    },
    {
        "id": "wp_voltijd",
        "label": "Waarvan voltijd (≥12 uur per week)",
        "type": "number",
        "verplicht": False,
        "hint": "",
    },
    {
        "id": "wp_deeltijd",
        "label": "Waarvan deeltijd (<12 uur per week)",
        "type": "number",
        "verplicht": False,
        "hint": "",
    },
    {
        "id": "wp_op_locatie",
        "label": "Werkzame personen ≥60% op locatie",
        "type": "number",
        "verplicht": False,
        "hint": "Aantal medewerkers dat minimaal 60% van de werktijd fysiek aanwezig is op deze vestiging",
    },
    # --- Bedrijfsvastgoed ---
    {
        "id": "opp_perceel",
        "label": "Perceeloppervlakte (m²)",
        "type": "number",
        "verplicht": False,
        "hint": "",
    },
    {
        "id": "opp_winkel",
        "label": "Winkelvloeroppervlakte (m²)",
        "type": "number",
        "verplicht": False,
        "hint": "Alleen invullen indien van toepassing",
    },
    {
        "id": "opp_kantoor",
        "label": "Kantoorvloeroppervlakte (m²)",
        "type": "number",
        "verplicht": False,
        "hint": "Alleen invullen indien van toepassing",
    },
    {
        "id": "opp_bedrijf",
        "label": "Bedrijfsvloeroppervlakte (m²)",
        "type": "number",
        "verplicht": False,
        "hint": "Alleen invullen indien van toepassing",
    },
    {
        "id": "uitbreidingsruimte",
        "label": "Gewenste uitbreidingsruimte (m²)",
        "type": "number",
        "verplicht": False,
        "hint": "Hoeveel extra ruimte heeft u nodig als u zou willen uitbreiden?",
    },
    # --- Seizoen ---
    {
        "id": "seizoen_verschil",
        "label": "Verschil hoog- en laagseizoen",
        "type": "text",
        "verplicht": False,
        "hint": "Bijv. 'In de zomer 20 extra medewerkers' of 'geen seizoensverschil'",
    },
    # --- Toelichting ---
    {
        "id": "opmerking",
        "label": "Overige toelichting",
        "type": "text",
        "verplicht": False,
        "hint": "",
    },
]

# Gerichte variant (🟡): alleen WP-bevestiging + opmerkingen
VRAGEN_GERICHT = [
    {
        "id": "wp_totaal",
        "label": "Aantal werkzame personen (totaal)",
        "type": "number",
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

# Fallback voor sessies zonder expliciete variant
DEFAULT_VRAGEN = VRAGEN_VOLLEDIG


@router.get("/{token}")
def get_chat_session(token: str, db: Session = Depends(get_db)):
    """Haalt chat-sessie op op basis van token. Geen auth vereist."""
    session = db.query(ChatSession).filter_by(token_hash=token).first()
    if not session:
        raise HTTPException(404, "Chat-sessie niet gevonden of verlopen")
    if session.status == "completed":
        return {"status": "completed"}
    comp = db.get(Company, session.company_id)
    return {
        "bedrijfsnaam": comp.naam if comp else "Onbekend bedrijf",
        "gemeente": comp.gemeente if comp else None,
        "variant": session.variant,
        "pre_fill_wp": session.pre_fill_wp,
        "status": session.status,
        "vragen": session.vragen if session.vragen else (
            VRAGEN_GERICHT if session.variant == "gericht" else VRAGEN_VOLLEDIG
        ),
    }


class ChatSubmit(BaseModel):
    antwoorden: dict  # {vraag_id: waarde}


@router.post("/{token}/submit")
def submit_chat(token: str, body: ChatSubmit, db: Session = Depends(get_db)):
    """Slaat antwoorden op en markeert de sessie als afgerond."""
    session = db.query(ChatSession).filter_by(token_hash=token).first()
    if not session:
        raise HTTPException(404, "Chat-sessie niet gevonden of verlopen")
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
