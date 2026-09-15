"""Mappen-API: de ordeningslaag boven de onderzoekslijsten.

Bewust dun. Een map bevat lijsten en verder niets — geen rechten, geen
nesting, geen eigen status. Alles wat een reviewer over een lijst wil weten
staat al op de lijst zelf.

Opruimen kan op twee manieren. Archiveren is de gewone: de map verdwijnt uit
het overzicht, alles blijft staan, en herstellen geeft precies terug wat er
was. Verwijderen is definitief en dus de uitzondering.

Een map met lijsten erin mag nooit stilzwijgend die lijsten meenemen —
onderzoeksresultaten zijn duur om opnieuw op te bouwen. Daarom weigert een
DELETE op een gevulde map, tenzij de aanroeper expliciet aangeeft de lijsten
los te koppelen.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Batch, Map, User

router = APIRouter(
    prefix="/mappen", tags=["mappen"], dependencies=[Depends(get_current_user)],
)


class MapInvoer(BaseModel):
    naam: str = Field(min_length=1, max_length=120)


def _naamconflict(naam: str, botsing: Map) -> str:
    """Zonder deze toevoeging verwijst de melding naar een map die nergens in
    het overzicht te vinden is, omdat ze gearchiveerd staat."""
    if botsing.gearchiveerd_op is not None:
        return (
            f'Er staat al een gearchiveerde map met de naam "{naam}". '
            "Herstel die map of kies een andere naam."
        )
    return f'Er bestaat al een map met de naam "{naam}"'


def _telbare_lijsten(db: Session):
    """De lijsten die een teller in dit scherm hoort mee te tellen.

    Eén plek, want de twee tellers hieronder gaan over hetzelfde begrip en
    liepen uit elkaar: ze telden wel de monitoringlijsten weg maar niet de
    prullenbak, terwijl het lijstoverzicht (batches.py) dat wel doet. Een map
    bleef daardoor "1 lijst" melden die er niet meer was, en bij "Zonder map"
    was dat erger dan cosmetisch: die tegel verschijnt alleen zolang de teller
    boven nul staat, dus hij bleef staan en leidde naar een leeg scherm,
    zonder iets dat je kon weghalen.
    """
    return (
        db.query(Batch)
        .filter(Batch.is_monitoringlijst.isnot(True))
        .filter(Batch.verwijderd_op.is_(None))
    )


def _lijsten_in_map(db: Session, map_id: str) -> int:
    return _telbare_lijsten(db).filter(Batch.map_id == map_id).count()


def _als_json(db: Session, map_obj: Map) -> dict:
    return {
        "id": map_obj.id,
        "naam": map_obj.naam,
        "created_at": (
            map_obj.created_at.isoformat() + "Z" if map_obj.created_at else None
        ),
        "aantal_lijsten": _lijsten_in_map(db, map_obj.id),
        "gearchiveerd_op": (
            map_obj.gearchiveerd_op.isoformat() + "Z"
            if map_obj.gearchiveerd_op else None
        ),
    }


@router.get("")
def list_mappen(gearchiveerd: bool = False, db: Session = Depends(get_db)):
    """Actieve mappen, of juist alleen het archief.

    Standaard blijft het archief buiten beeld — dat is het hele punt van
    archiveren. Het aantal komt wel altijd mee, zodat de interface kan laten
    zien dát er iets in het archief staat zonder ernaartoe te hoeven.
    """
    query = db.query(Map)
    query = (
        query.filter(Map.gearchiveerd_op.isnot(None)) if gearchiveerd
        else query.filter(Map.gearchiveerd_op.is_(None))
    )
    mappen = query.order_by(Map.created_at.asc()).all()
    return {
        "mappen": [_als_json(db, item) for item in mappen],
        "aantal_gearchiveerd": (
            db.query(Map).filter(Map.gearchiveerd_op.isnot(None)).count()
        ),
        # Lijsten zonder map horen zichtbaar te blijven. Zonder deze teller zou
        # een lijst die buiten een map is aangemaakt nergens opduiken.
        "losse_lijsten": (
            _telbare_lijsten(db).filter(Batch.map_id.is_(None)).count()
        ),
    }


@router.post("", status_code=201)
def maak_map(
    invoer: MapInvoer,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    naam = invoer.naam.strip()
    if not naam:
        raise HTTPException(422, "Geef de map een naam")
    # Uniciteit geldt ook tegen gearchiveerde mappen: anders levert het
    # herstellen van een archiefmap ineens twee mappen met dezelfde naam op.
    botsing = db.query(Map).filter(Map.naam.ilike(naam)).first()
    if botsing is not None:
        raise HTTPException(409, _naamconflict(naam, botsing))
    map_obj = Map(naam=naam, aangemaakt_door=current_user.id)
    db.add(map_obj)
    db.commit()
    db.refresh(map_obj)
    return _als_json(db, map_obj)


@router.patch("/{map_id}")
def hernoem_map(
    map_id: str, invoer: MapInvoer, db: Session = Depends(get_db),
):
    map_obj = db.get(Map, map_id)
    if map_obj is None:
        raise HTTPException(404, "Map bestaat niet")
    naam = invoer.naam.strip()
    if not naam:
        raise HTTPException(422, "Geef de map een naam")
    bestaand = db.query(Map).filter(Map.naam.ilike(naam)).first()
    if bestaand is not None and bestaand.id != map_id:
        raise HTTPException(409, _naamconflict(naam, bestaand))
    map_obj.naam = naam
    db.commit()
    db.refresh(map_obj)
    return _als_json(db, map_obj)


@router.delete("/{map_id}")
def verwijder_map(
    map_id: str,
    ontkoppel_lijsten: bool = False,
    db: Session = Depends(get_db),
):
    """Verwijder een map. Lijsten erin worden nooit mee verwijderd.

    Zonder `ontkoppel_lijsten` weigert dit op een gevulde map, met het aantal
    in het antwoord zodat de interface kan vertellen waar het om gaat. Met de
    vlag blijven de lijsten bestaan en komen ze buiten elke map te staan.
    """
    map_obj = db.get(Map, map_id)
    if map_obj is None:
        raise HTTPException(404, "Map bestaat niet")

    aantal = _lijsten_in_map(db, map_id)
    if aantal and not ontkoppel_lijsten:
        raise HTTPException(
            409,
            f"Deze map bevat {aantal} "
            f"{'lijst' if aantal == 1 else 'lijsten'}.",
        )

    db.query(Batch).filter(Batch.map_id == map_id).update(
        {"map_id": None}, synchronize_session=False,
    )
    db.delete(map_obj)
    db.commit()
    return {"verwijderd": map_id, "lijsten_ontkoppeld": aantal}


@router.post("/{map_id}/archiveren")
def archiveer_map(map_id: str, db: Session = Depends(get_db)):
    """Leg een map weg zonder iets weg te gooien.

    De lijsten erin blijven ongemoeid en houden hun map_id, zodat herstellen
    precies teruggeeft wat er stond. Dit is bedoeld als de gewone manier van
    opruimen; verwijderen blijft bestaan voor wie echt van iets af wil.
    """
    map_obj = db.get(Map, map_id)
    if map_obj is None:
        raise HTTPException(404, "Map bestaat niet")
    if map_obj.gearchiveerd_op is None:
        map_obj.gearchiveerd_op = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(map_obj)
    return _als_json(db, map_obj)


@router.post("/{map_id}/herstellen")
def herstel_map(map_id: str, db: Session = Depends(get_db)):
    map_obj = db.get(Map, map_id)
    if map_obj is None:
        raise HTTPException(404, "Map bestaat niet")
    map_obj.gearchiveerd_op = None
    db.commit()
    db.refresh(map_obj)
    return _als_json(db, map_obj)
