"""Eenmalig backfill-script: kent het admin-account toe als geupload_door voor
alle bestaande batches die dat veld nog niet hebben (aangemaakt vóór dit
sub-project). Los van ensure_lightweight_migrations(), want die draait al bij
de allereerste deploy, vóórdat het admin-account via seed_users bestaat.

Gebruik vanuit backend/: python -m scripts.backfill_geupload_door
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Batch, User  # noqa: E402


def backfill_geupload_door(db: Session, admin_email: str = "admin@etil.nl") -> int:
    admin = db.query(User).filter_by(email=admin_email).one_or_none()
    if admin is None:
        print(f"Geen gebruiker gevonden met e-mailadres {admin_email} — niets gedaan.")
        return 0
    batches = db.query(Batch).filter(Batch.geupload_door.is_(None)).all()
    for batch in batches:
        batch.geupload_door = admin.id
    db.commit()
    return len(batches)


def main() -> int:
    db = SessionLocal()
    try:
        aantal = backfill_geupload_door(db)
    finally:
        db.close()
    print(f"Backfill geupload_door: {aantal} batch(es) toegewezen aan admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
