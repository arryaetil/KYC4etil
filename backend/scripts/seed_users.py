"""Seed demo-gebruikers voor de review-interface.

Gebruik vanuit backend/: python -m scripts.seed_users
"""
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import hash_password  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import User  # noqa: E402

USER_CONFIG = [
    ("Armina", "armina@etil.nl", "reviewer", "demo_armina_password"),
    ("Anita", "anita@etil.nl", "reviewer", "demo_anita_password"),
    ("Admin", "admin@etil.nl", "admin", "demo_admin_password"),
    ("R. van Zandvoort", "r.vanzandvoort@etil.nl", "reviewer", "demo_vanzandvoort_password"),
]


def _password(settings, field_name: str) -> str:
    return getattr(settings, field_name) or secrets.token_urlsafe(18)


def main() -> int:
    settings = get_settings()
    users = [(naam, email, rol, _password(settings, field_name))
             for naam, email, rol, field_name in USER_CONFIG]

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for naam, email, rol, password in users:
            user = db.query(User).filter(User.email == email).one_or_none()
            if user is None:
                db.add(User(naam=naam, email=email, rol=rol,
                            password_hash=hash_password(password)))
            else:
                user.naam = naam
                user.rol = rol
                user.password_hash = hash_password(password)
        db.commit()
    finally:
        db.close()

    print("Demo-gebruikers seeded:")
    for naam, email, rol, password in users:
        print(f"- {naam} ({rol}): {email} / {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
