from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..auth import authenticate_user, create_access_token, get_current_user
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
