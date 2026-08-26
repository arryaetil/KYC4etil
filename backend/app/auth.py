from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import User

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 12 * 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# Variant zonder automatische 401: nodig voor endpoints die het token ook
# uit de query mogen halen (zie get_current_user_of_querytoken).
oauth2_scheme_optioneel = OAuth2PasswordBearer(
    tokenUrl="/auth/login", auto_error=False,
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """False bij een onbruikbare hash, geen uitzondering.

    Een account zonder wachtwoord bestaat: `seed_users` maakt er een aan met een
    lege hash zodra de omgevingsvariabele ontbreekt. Daar liep `pwd_context`
    stuk op een UnknownHashError, en dan krijgt de gebruiker een 500 terwijl het
    antwoord gewoon "dit wachtwoord klopt niet" is.
    """
    if not password_hash:
        return False
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.lower()).one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "rol": user.rol,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    secret = get_settings().jwt_secret or "change-me"
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ongeldige of verlopen login",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        secret = get_settings().jwt_secret or "change-me"
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise credentials_error from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise credentials_error
    user = db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


def get_current_user_of_querytoken(
    db: Annotated[Session, Depends(get_db)],
    header_token: Annotated[str | None, Depends(oauth2_scheme_optioneel)] = None,
    token: str | None = None,
) -> User:
    """Zelfde controle als get_current_user, maar accepteert het token ook als
    queryparameter.

    De meegeleverde PDF-viewer haalt een document op met een gewone fetch en
    kan daar geen Authorization-header aan meegeven; het token staat immers in
    localStorage en niet in een cookie. Zonder deze variant zou een
    ingesloten document altijd op een 401 stuklopen.
    """
    return get_current_user(header_token or token or "", db)


def vereis_admin(gebruiker: "User" = Depends(get_current_user)) -> "User":
    """Alleen een beheerder mag hier langs.

    De rol stond al in het token en op de gebruiker, maar werd nergens
    gecontroleerd: iedere reviewer kon lijsten uploaden, verwijderen en
    exporteren. Voor drie collega's die elkaar vertrouwen valt dat mee, maar
    accounts aanmaken is precies het soort handeling waar dat niet meer opgaat.
    """
    if gebruiker.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="hiervoor heb je beheerdersrechten nodig",
        )
    return gebruiker
