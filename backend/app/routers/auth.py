from datetime import datetime, timezone
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
from .. import handelingen
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
    handelingen.leg_vast(
        db, handelingen.WACHTWOORD_GEWIJZIGD,
        f"{current_user.naam} wijzigde het eigen wachtwoord",
        door=current_user, onderwerp_id=current_user.id,
    )
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
            for gebruiker in db.query(User)
            .filter(User.verwijderd_op.is_(None))
            .order_by(User.naam)
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
    bestaand = db.query(User).filter(User.email == email).one_or_none()
    if bestaand is not None and bestaand.verwijderd_op is None:
        raise HTTPException(409, "er bestaat al een account met dit e-mailadres")
    if bestaand is not None:
        # Het adres was eerder ingetrokken. Zonder deze tak is een e-mailadres
        # na een intrekking voorgoed onbruikbaar, terwijl dat juist het geval
        # is waarin je het opnieuw nodig hebt: iemand komt terug.
        bestaand.naam = payload.naam.strip()
        bestaand.rol = payload.rol
        bestaand.password_hash = hash_password(payload.wachtwoord)
        bestaand.verwijderd_op = None
        handelingen.leg_vast(
            db, handelingen.GEBRUIKER_AANGEMAAKT,
            f"Toegang van {bestaand.naam} ({bestaand.email}) hersteld "
            f"als {bestaand.rol}",
            door=_admin, onderwerp_id=bestaand.id,
        )
        db.commit()
        db.refresh(bestaand)
        return _user_response(bestaand)
    gebruiker = User(
        naam=payload.naam.strip(),
        email=email,
        rol=payload.rol,
        password_hash=hash_password(payload.wachtwoord),
    )
    db.add(gebruiker)
    db.flush()
    handelingen.leg_vast(
        db, handelingen.GEBRUIKER_AANGEMAAKT,
        f"Account voor {gebruiker.naam} ({gebruiker.email}) aangemaakt "
        f"als {gebruiker.rol}",
        door=_admin, onderwerp_id=gebruiker.id,
    )
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

    De rij blijft staan met een datum erin. Een echte DELETE liep stuk zodra de
    gebruiker ergens in het werk voorkwam — een toegewezen bellijstregel was al
    genoeg — en dat kwam in de interface aan als "Failed to fetch". Belangrijker
    dan die foutmelding: de verwijzingen horen te blijven kloppen. Wie deze bron
    accepteerde blijft leesbaar nadat het account weg is.
    """
    gebruiker = db.get(User, user_id)
    if gebruiker is None or gebruiker.verwijderd_op is not None:
        raise HTTPException(404, "gebruiker niet gevonden")
    if gebruiker.id == admin.id:
        raise HTTPException(422, "je kunt je eigen account niet verwijderen")
    actieve_admins = (
        db.query(User)
        .filter(User.rol == "admin", User.verwijderd_op.is_(None))
        .count()
    )
    if gebruiker.rol == "admin" and actieve_admins <= 1:
        raise HTTPException(422, "dit is de laatste beheerder")
    handelingen.leg_vast(
        db, handelingen.GEBRUIKER_VERWIJDERD,
        f"Toegang van {gebruiker.naam} ({gebruiker.email}) ingetrokken",
        door=admin, onderwerp_id=gebruiker.id,
    )
    gebruiker.verwijderd_op = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return {"verwijderd": user_id}


@router.get("/handelingen")
def lees_handelingen(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(vereis_admin)],
    limiet: int = 50,
):
    """Wie deed wat, nieuwste eerst.

    Alleen voor een beheerder: het is geen geheim, maar het is ook geen
    informatie waar een reviewer iets aan heeft tijdens haar werk.
    """
    from ..models import Handeling

    regels = (
        db.query(Handeling)
        .order_by(Handeling.created_at.desc())
        .limit(min(limiet, 200))
        .all()
    )
    return {
        "items": [
            {
                "id": regel.id,
                "soort": regel.soort,
                "omschrijving": regel.omschrijving,
                "door": regel.door_naam,
                "created_at": regel.created_at.isoformat() + "Z",
            }
            for regel in regels
        ],
    }
