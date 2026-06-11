from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import get_settings

settings = get_settings()

engine = create_engine(
    settings.effective_database_url,
    connect_args={"check_same_thread": False} if settings.effective_database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_lightweight_migrations() -> None:
    inspector = inspect(engine)
    if "companies" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("companies")}
    additions = {
        "website_url": "TEXT",
        "telefoonnummer": "VARCHAR(50)",
    }
    with engine.begin() as conn:
        for name, ddl_type in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE companies ADD COLUMN {name} {ddl_type}"))
