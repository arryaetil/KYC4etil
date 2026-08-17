from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import get_settings

settings = get_settings()
database_url = settings.effective_database_url
engine_options = {
    "connect_args": (
        {"check_same_thread": False}
        if database_url.startswith("sqlite")
        else {}
    ),
}
if not database_url.startswith("sqlite"):
    # Houd de API responsief tijdens langlopende research. Een korte timeout
    # voorkomt dat honderden webrequests elk 30 seconden op een volle pool
    # blijven wachten; pre-ping ruimt verbroken Railway-connecties op.
    engine_options.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 5,
        "pool_pre_ping": True,
        "pool_recycle": 300,
    })

engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


DEMOMAP_NAAM = "Demo runs"


def _vul_demomap(conn) -> None:
    """Zet elke bestaande lijst in één map, zodat er niets verdwijnt.

    De mappenlaag is later toegevoegd dan de lijsten. Zonder deze stap zou de
    nieuwe pagina leeg openen terwijl er tientallen batches in de database
    staan — die zouden dan alleen nog via een directe URL bereikbaar zijn.
    De monitoringlijst blijft er bewust buiten: die heeft een eigen module.
    """
    import uuid as _uuid_mod
    from datetime import datetime, timezone

    map_id = str(_uuid_mod.uuid4())
    conn.execute(
        text(
            "INSERT INTO mappen (id, naam, created_at) "
            "VALUES (:id, :naam, :created_at)"
        ),
        {
            "id": map_id,
            "naam": DEMOMAP_NAAM,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        },
    )
    conn.execute(
        text(
            "UPDATE batches SET map_id = :map_id "
            "WHERE map_id IS NULL "
            "AND (is_monitoringlijst IS NULL OR is_monitoringlijst = FALSE)"
        ),
        {"map_id": map_id},
    )


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
        for name, ddl_type in [
            ("website_url", "TEXT"), ("telefoonnummer", "VARCHAR(50)"),
            ("afgewerkt", "BOOLEAN DEFAULT FALSE"),
            ("organization_id", "VARCHAR(36)"),
        ]:
            _add_column_if_missing(conn, "companies", existing_companies, name, ddl_type)
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_companies_organization_id "
            "ON companies (organization_id)"
        ))

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
            if "geupload_door" not in existing_batches:
                conn.execute(text("ALTER TABLE batches ADD COLUMN geupload_door VARCHAR(36)"))
            if "map_id" not in existing_batches:
                conn.execute(text("ALTER TABLE batches ADD COLUMN map_id VARCHAR(36)"))
                # Alles wat er al stond bij elkaar in één map, zodat de nieuwe
                # mappenpagina niet leeg opent en geen enkele bestaande lijst
                # buiten beeld raakt. Alleen bij het aanmaken van de kolom:
                # daarna bepaalt de gebruiker zelf waar een lijst hoort.
                _vul_demomap(conn)
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_batches_map_id ON batches (map_id)"
            ))

    if "agent_results" in tables:
        existing_ar = {col["name"] for col in inspector.get_columns("agent_results")}
        with engine.begin() as conn:
            for name, ddl_type in [
                ("eigen_personeel", "INTEGER"), ("uitzend", "INTEGER"),
                ("detachering", "INTEGER"), ("wsw", "INTEGER"),
                ("man", "INTEGER"), ("vrouw", "INTEGER"),
                ("voltijd", "INTEGER"), ("deeltijd", "INTEGER"),
                ("pct_op_locatie", "FLOAT"), ("bron_pagina", "INTEGER"),
                ("identity_class", "VARCHAR(30)"), ("scope_class", "VARCHAR(30)"),
            ]:
                _add_column_if_missing(conn, "agent_results", existing_ar, name, ddl_type)

    if "candidates" in tables:
        existing_cand = {col["name"] for col in inspector.get_columns("candidates")}
        with engine.begin() as conn:
            _add_column_if_missing(conn, "candidates", existing_cand, "reviewer_signaal", "TEXT")

    if "bron_kandidaten" in tables:
        existing_bronnen = {
            col["name"] for col in inspector.get_columns("bron_kandidaten")
        }
        with engine.begin() as conn:
            for name, ddl_type in [
                ("review_reason_code", "VARCHAR(50)"),
                ("bron_relevant", "BOOLEAN"),
                ("bron_volledig_ingelezen", "BOOLEAN"),
                ("wp_oordeel", "VARCHAR(30)"),
                ("gecorrigeerd_wp", "INTEGER"),
                ("extractie_reason_code", "VARCHAR(50)"),
                ("extractie_toelichting", "TEXT"),
            ]:
                _add_column_if_missing(
                    conn, "bron_kandidaten", existing_bronnen, name, ddl_type,
                )

    if "jaarverslag_monitoring" in tables:
        existing_monitoring = {
            col["name"] for col in inspector.get_columns("jaarverslag_monitoring")
        }
        with engine.begin() as conn:
            _add_column_if_missing(
                conn,
                "jaarverslag_monitoring",
                existing_monitoring,
                "laatste_verslagjaar",
                "INTEGER",
            )

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
