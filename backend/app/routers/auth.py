from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
    vereis_admin,
)
from ..database import get_db
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user: User) -> dict:
    return {"id": user.id, "naam": user.naam, "email": user.email, "rol": user.rol}


@router.post("/login")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
):
    user = authenticate_user(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ongeldige gebruikersnaam of wachtwoord",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": _user_response(user),
    }


@router.get("/me")
def me(current_user: Annotated[User, Depends(get_current_user)]):
    return _user_response(current_user)


# Kort genoeg om te onthouden, lang genoeg om niet te raden. Bewust geen eisen
# over hoofdletters en tekens: die leveren in de praktijk Etil2026! op, en dat
# is zwakker dan een lange zin.
MINIMUM_WACHTWOORD = 10


class WachtwoordWijziging(BaseModel):
    huidig: str = Field(min_length=1, max_length=200)
    nieuw: str = Field(min_length=MINIMUM_WACHTWOORD, max_length=200)


class NieuweGebruiker(BaseModel):
    naam: str = Field(min_length=2, max_length=100)
    # Geen EmailStr: dat trekt een extra afhankelijkheid binnen voor een
    # controle die hier niets toevoegt. Een beheerder typt het adres van een
    # collega in; als dat niet klopt merkt die dat bij de eerste inlogpoging.
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    rol: str = Field(default="reviewer")
    wachtwoord: str = Field(min_length=MINIMUM_WACHTWOORD, max_length=200)


ROLLEN = {"admin", "reviewer"}


@router.post("/wachtwoord")
def wijzig_eigen_wachtwoord(
    payload: WachtwoordWijziging,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Je eigen wachtwoord wijzigen.

    Het huidige wachtwoord moet mee: anders kan iedereen die even achter een
    open laptop kruipt het account overnemen zonder iets te weten.
    """
    if not verify_password(payload.huidig, current_user.password_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "huidig wachtwoord klopt niet")
    if payload.nieuw == payload.huidig:
        raise HTTPException(422, "kies een ander wachtwoord dan het huidige")
    current_user.password_hash = hash_password(payload.nieuw)
    db.commit()
    return {"gewijzigd": True}


@router.get("/users")
def lees_gebruikers(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(vereis_admin)],
):
    return {
        "items": [
            {**_user_response(gebruiker),
             "created_at": gebruiker.created_at.isoformat() + "Z"}
            for gebruiker in db.query(User).order_by(User.naam)
        ],
    }


@router.post("/users")
def maak_gebruiker(
    payload: NieuweGebruiker,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(vereis_admin)],
):
    """Een nieuwe gebruiker aanmaken.

    Tot nu toe bestonden accounts alleen via `scripts/seed_users.py`, dat bij
    elke run een nieuw willekeurig wachtwoord genereert. Een collega toevoegen
    betekende dus een deploy en een script draaien.
    """
    if payload.rol not in ROLLEN:
        raise HTTPException(422, "kies een geldige rol")
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).one_or_none() is not None:
        raise HTTPException(409, "er bestaat al een account met dit e-mailadres")
    gebruiker = User(
        naam=payload.naam.strip(),
        email=email,
        rol=payload.rol,
        password_hash=hash_password(payload.wachtwoord),
    )
    db.add(gebruiker)
    db.commit()
    db.refresh(gebruiker)
    return _user_response(gebruiker)


@router.delete("/users/{user_id}")
def verwijder_gebruiker(
    user_id: str,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(vereis_admin)],
):
    """Toegang intrekken.

    Niet jezelf, en nooit de laatste beheerder: dan kan niemand er nog bij en is
    het alleen met een script te herstellen.
    """
    gebruiker = db.get(User, user_id)
    if gebruiker is None:
        raise HTTPException(404, "gebruiker niet gevonden")
    if gebruiker.id == admin.id:
        raise HTTPException(422, "je kunt je eigen account niet verwijderen")
    if gebruiker.rol == "admin" and db.query(User).filter(User.rol == "admin").count() <= 1:
        raise HTTPException(422, "dit is de laatste beheerder")
    db.delete(gebruiker)
    db.commit()
    return {"verwijderd": user_id}
