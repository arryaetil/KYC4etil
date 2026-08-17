"""Mappen-API: de ordeningslaag boven de onderzoekslijsten.

Bewust dun. Een map bevat lijsten en verder niets — geen rechten, geen
nesting, geen eigen status. Alles wat een reviewer over een lijst wil weten
staat al op de lijst zelf.

Verwijderen is het enige dat aandacht vraagt. Een map met lijsten erin mag
nooit stilzwijgend die lijsten meenemen: onderzoeksresultaten zijn duur om
opnieuw op te bouwen. Daarom weigert een DELETE op een gevulde map, tenzij de
aanroeper expliciet aangeeft de lijsten los te koppelen.
"""
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


def _lijsten_in_map(db: Session, map_id: str) -> int:
    return (
        db.query(Batch)
        .filter(Batch.map_id == map_id)
        .filter(Batch.is_monitoringlijst.isnot(True))
        .count()
    )


def _als_json(db: Session, map_obj: Map) -> dict:
    return {
        "id": map_obj.id,
        "naam": map_obj.naam,
        "created_at": (
            map_obj.created_at.isoformat() + "Z" if map_obj.created_at else None
        ),
        "aantal_lijsten": _lijsten_in_map(db, map_obj.id),
    }


@router.get("")
def list_mappen(db: Session = Depends(get_db)):
    mappen = db.query(Map).order_by(Map.created_at.asc()).all()
    return {
        "mappen": [_als_json(db, item) for item in mappen],
        # Lijsten zonder map horen zichtbaar te blijven. Zonder deze teller zou
        # een lijst die buiten een map is aangemaakt nergens opduiken.
        "losse_lijsten": (
            db.query(Batch)
            .filter(Batch.map_id.is_(None))
            .filter(Batch.is_monitoringlijst.isnot(True))
            .count()
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
    if db.query(Map).filter(Map.naam.ilike(naam)).first():
        raise HTTPException(409, f'Er bestaat al een map met de naam "{naam}"')
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
        raise HTTPException(409, f'Er bestaat al een map met de naam "{naam}"')
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
