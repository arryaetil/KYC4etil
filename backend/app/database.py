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
    tables = set(inspector.get_table_names())
    if "companies" not in tables:
        return

    existing_companies = {col["name"] for col in inspector.get_columns("companies")}
    with engine.begin() as conn:
        for name, ddl_type in [("website_url", "TEXT"), ("telefoonnummer", "VARCHAR(50)")]:
            if name not in existing_companies:
                conn.execute(text(f"ALTER TABLE companies ADD COLUMN {name} {ddl_type}"))

    if "enrichments" in tables:
        existing_enr = {col["name"] for col in inspector.get_columns("enrichments")}
        with engine.begin() as conn:
            if "email" not in existing_enr:
                conn.execute(text("ALTER TABLE enrichments ADD COLUMN email VARCHAR(255)"))

    if "batches" in tables:
        existing_batches = {col["name"] for col in inspector.get_columns("batches")}
        with engine.begin() as conn:
            if "created_at" not in existing_batches:
                conn.execute(text("ALTER TABLE batches ADD COLUMN created_at TIMESTAMP"))
                conn.execute(text(
                    "UPDATE batches SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
                ))
            if "completed_at" not in existing_batches:
                conn.execute(text("ALTER TABLE batches ADD COLUMN completed_at TIMESTAMP"))

    if "chat_sessions" in tables:
        existing_cs = {col["name"] for col in inspector.get_columns("chat_sessions")}
        with engine.begin() as conn:
            if "verwerkt" not in existing_cs:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN verwerkt BOOLEAN DEFAULT FALSE"))
            if "vragen" not in existing_cs:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN vragen JSON"))
            if "antwoorden" not in existing_cs:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN antwoorden JSON"))
            if "messages" not in existing_cs:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN messages JSON"))
            if "expires_at" not in existing_cs:
                conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN expires_at TIMESTAMP"))
