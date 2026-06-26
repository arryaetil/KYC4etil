"""Gedeelde fixtures: in-memory SQLite database + TestClient."""
import fitz  # PyMuPDF
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlite3 import Connection as SQLite3Connection

from app.database import get_db, Base
from app.main import app as fastapi_app
import app.models  # Ensure all models are loaded

# Use a single connection for in-memory SQLite to avoid multiple databases
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=__import__('sqlalchemy.pool', fromlist=['StaticPool']).StaticPool
)

@event.listens_for(_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    if isinstance(dbapi_conn, SQLite3Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

_Session = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def _override_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def client(reset_db):
    fastapi_app.dependency_overrides[get_db] = _override_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def pdf_bytes():
    """Minimale, geldige PDF met leesbare tekst."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Medewerkers: 138 werkzame personen in 2024.")
    return doc.tobytes()
