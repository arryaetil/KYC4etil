"""Beheer-endpoints voor chat-templates en chat-sessies — auth vereist."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Batch, Candidate, ChatSession, ChatTemplate, Company, User, VastgoedRecord, WPRecord


def _getal(antwoorden: dict, key: str) -> int | None:
    """Zet antwoord-waarde om naar int, of None als onbekend/'/'."""
    val = antwoorden.get(key)
    if val is None or val == "/" or val == "":
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _pct_fractie(antwoorden: dict, key: str) -> float | None:
    """Zet percentage (0-100) om naar fractie (0-1), of None."""
    val = antwoorden.get(key)
    if val is None or val == "/" or val == "":
        return None
    try:
        v = float(val)
        return v / 100 if v > 1 else v
    except (TypeError, ValueError):
        return None


def _bool_antwoord(antwoorden: dict, key: str) -> bool | None:
    """Zet tekst-antwoord ('ja'/'nee'/'/') om naar bool."""
    val = antwoorden.get(key)
    if val is None or val == "":
        return None
    if val == "/":
        return False
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("ja", "yes", "true", "1")

router = APIRouter(tags=["chat-admin"], dependencies=[Depends(get_current_user)])


# ── Templates ──────────────────────────────────────────────────────────────────

class TemplateBody(BaseModel):
    naam: str
    beschrijving: str | None = None
    veld_config: dict[str, bool] | None = None   # veld -> True (aan) | False (uit)
    intro_tekst: str | None = None
    extra_vragen: list[str] | None = None
    is_default: bool = False


def _template_config(body: TemplateBody) -> dict:
    return {
        "veld_config": body.veld_config or {},
        "intro_tekst": body.intro_tekst or "",
        "extra_vragen": [v for v in (body.extra_vragen or []) if v.strip()],
    }


def _template_response(t: ChatTemplate) -> dict:
    cfg = t.vragen if isinstance(t.vragen, dict) else {}
    vc = cfg.get("veld_config", {})
    n_actief = sum(
        1 for v in vc.values()
        if v is True or (isinstance(v, str) and v != "skip")
    )
    return {
        "id": t.id,
        "naam": t.naam,
        "beschrijving": t.beschrijving,
        "veld_config": vc,
        "intro_tekst": cfg.get("intro_tekst", ""),
        "extra_vragen": cfg.get("extra_vragen", []),
        "is_default": t.is_default,
        "aangemaakt_door": t.aangemaakt_door,
        "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
        "n_actief": n_actief,
    }


@router.get("/chat-templates")
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(ChatTemplate).order_by(ChatTemplate.created_at).all()
    return [_template_response(t) for t in templates]


@router.post("/chat-templates")
def create_template(body: TemplateBody, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    if body.is_default:
        for t in db.query(ChatTemplate).filter_by(is_default=True).all():
            t.is_default = False
    template = ChatTemplate(
        id=str(uuid.uuid4()),
        naam=body.naam,
        beschrijving=body.beschrijving,
        vragen=_template_config(body),
        is_default=body.is_default,
        aangemaakt_door=current_user.id,
    )
    db.add(template)
    db.commit()
    return _template_response(template)


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
    template.vragen = _template_config(body)
    template.is_default = body.is_default
    db.commit()
    return _template_response(template)


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
    """Doorvoeren van alle chat-antwoorden naar WPRecord en VastgoedRecord."""
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(404, "Chat-sessie niet gevonden")
    if session.status != "completed":
        raise HTTPException(422, "Sessie is nog niet ingevuld door het bedrijf")
    if session.verwerkt:
        raise HTTPException(409, "Sessie is al doorvoerd")

    antwoorden = session.antwoorden or {}
    wp_totaal = (antwoorden.get("wp_totaal") or antwoorden.get("wp_count")
                 or antwoorden.get("wp_opgegeven"))
    if not wp_totaal:
        raise HTTPException(422, "Geen WP-getal in antwoorden")

    comp = db.get(Company, session.company_id)
    if not comp:
        raise HTTPException(404, "Bedrijf niet gevonden")
    cand = comp.candidate
    if not cand:
        raise HTTPException(404, "Geen kandidaat gevonden voor dit bedrijf")

    b = db.get(Batch, cand.batch_id)
    wp_jaar = b.jaar if b else datetime.now(timezone.utc).replace(tzinfo=None).year
    nu = datetime.now(timezone.utc).replace(tzinfo=None)

    # --- WPRecord met volledige uitsplitsing ---
    cand.status = "corrected"
    cand.wp_kandidaat = int(float(wp_totaal))
    cand.reconciliatie_reden = (cand.reconciliatie_reden or "") + \
        f" | chat-antwoord ({current_user.naam}): {wp_totaal} WP"

    rec = WPRecord(
        company_id=comp.id,
        candidate_id=cand.id,
        wp_waarde=int(float(wp_totaal)),
        wp_jaar=wp_jaar,
        bron_type="chat",
        status="reviewed",
        goedgekeurd_door=current_user.id,
        goedgekeurd_op=nu,
        eigen_personeel=_getal(antwoorden, "eigen_personeel"),
        uitzend=_getal(antwoorden, "uitzend"),
        detachering=_getal(antwoorden, "detachering"),
        wsw=_getal(antwoorden, "wsw"),
        man=_getal(antwoorden, "man"),
        vrouw=_getal(antwoorden, "vrouw"),
        voltijd=_getal(antwoorden, "voltijd"),
        deeltijd=_getal(antwoorden, "deeltijd"),
        pct_op_locatie=_pct_fractie(antwoorden, "pct_op_locatie"),
    )
    db.add(rec)

    # --- VastgoedRecord aanmaken of bijwerken ---
    perceel = _getal(antwoorden, "perceeloppervlakte")
    winkel = _getal(antwoorden, "winkeloppervlakte")
    kantoor = _getal(antwoorden, "kantooroppervlakte")
    bedrijfs = _getal(antwoorden, "bedrijfsvloeroppervlakte")
    uitbreid = _bool_antwoord(antwoorden, "uitbreidingsruimte")
    seizoen = _bool_antwoord(antwoorden, "seizoensverschil")
    corresp = antwoorden.get("correspondentieadres") or None
    opmerking = antwoorden.get("opmerking") or None

    heeft_vastgoed = any(v is not None for v in [perceel, winkel, kantoor, bedrijfs, uitbreid, seizoen, corresp])
    if heeft_vastgoed:
        vg = comp.vastgoed
        if vg:
            vg.perceel_opp = perceel if perceel is not None else vg.perceel_opp
            vg.winkel_opp = winkel if winkel is not None else vg.winkel_opp
            vg.kantoor_opp = kantoor if kantoor is not None else vg.kantoor_opp
            vg.bedrijfs_opp = bedrijfs if bedrijfs is not None else vg.bedrijfs_opp
            vg.uitbreidingsruimte = uitbreid if uitbreid is not None else vg.uitbreidingsruimte
            vg.seizoensverschillen = seizoen if seizoen is not None else vg.seizoensverschillen
            vg.correspondentieadres = corresp or vg.correspondentieadres
            vg.seizoen_toelichting = opmerking or vg.seizoen_toelichting
            vg.bron = "chat"
            vg.updated_at = nu
        else:
            db.add(VastgoedRecord(
                company_id=comp.id,
                perceel_opp=perceel,
                winkel_opp=winkel,
                kantoor_opp=kantoor,
                bedrijfs_opp=bedrijfs,
                uitbreidingsruimte=uitbreid,
                seizoensverschillen=seizoen,
                correspondentieadres=corresp,
                seizoen_toelichting=opmerking,
                bron="chat",
                ingevoerd_door=current_user.id,
                updated_at=nu,
            ))

    # --- Adres bijwerken als het bedrijf een nieuw adres opgaf ---
    nieuw_adres = antwoorden.get("adres")
    if nieuw_adres and nieuw_adres != "/" and nieuw_adres != comp.adres:
        comp.adres = nieuw_adres

    session.verwerkt = True
    db.commit()
    return {"wp_record_id": rec.id, "wp_waarde": rec.wp_waarde}
