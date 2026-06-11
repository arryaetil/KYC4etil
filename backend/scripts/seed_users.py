"""Seed demo-gebruikers voor de review-interface.

Gebruik vanuit backend/: python -m scripts.seed_users
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import User  # noqa: E402

USERS = [
    ("Armina", "armina@etil.nl", "reviewer", "ArminaDemo2026!"),
    ("Anita", "anita@etil.nl", "reviewer", "AnitaDemo2026!"),
    ("Admin", "admin@etil.nl", "admin", "AdminDemo2026!"),
]


def main() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for naam, email, rol, password in USERS:
            user = db.query(User).filter(User.email == email).one_or_none()
            if user is None:
                db.add(User(naam=naam, email=email, rol=rol,
                            password_hash=hash_password(password)))
            else:
                user.naam = naam
                user.rol = rol
                if not user.password_hash:
                    user.password_hash = hash_password(password)
        db.commit()
    finally:
        db.close()

    print("Demo-gebruikers seeded:")
    for naam, email, rol, password in USERS:
        print(f"- {naam} ({rol}): {email} / {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
