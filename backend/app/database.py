from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
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


def _add_column_if_missing(conn, table: str, existing: set[str], name: str, ddl_type: str) -> None:
    if name in existing:
        return
    try:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))
    except (OperationalError, ProgrammingError) as exc:
        message = str(exc).lower()
        if "duplicate column" in message or "already exists" in message:
            return
        raise


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
            _add_column_if_missing(conn, "companies", existing_companies, name, ddl_type)

    if "enrichments" in tables:
        existing_enr = {col["name"] for col in inspector.get_columns("enrichments")}
        with engine.begin() as conn:
            _add_column_if_missing(conn, "enrichments", existing_enr, "email", "VARCHAR(255)")

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
            if "is_monitoringlijst" not in existing_batches:
                conn.execute(text(
                    "ALTER TABLE batches ADD COLUMN is_monitoringlijst BOOLEAN DEFAULT FALSE"
                ))

    if "agent_results" in tables:
        existing_ar = {col["name"] for col in inspector.get_columns("agent_results")}
        with engine.begin() as conn:
            for name, ddl_type in [
                ("eigen_personeel", "INTEGER"), ("uitzend", "INTEGER"),
                ("detachering", "INTEGER"), ("wsw", "INTEGER"),
                ("man", "INTEGER"), ("vrouw", "INTEGER"),
                ("voltijd", "INTEGER"), ("deeltijd", "INTEGER"),
                ("pct_op_locatie", "FLOAT"),
            ]:
                _add_column_if_missing(conn, "agent_results", existing_ar, name, ddl_type)

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
