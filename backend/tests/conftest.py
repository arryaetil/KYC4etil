"""Gedeelde fixtures: in-memory SQLite database + TestClient."""
import os

# Vóór élke app-import, want get_settings() is lru_cached: de eerste aanroep
# bevriest de configuratie voor de hele testsessie.
#
# De testsuite gaat uit van de deterministische mockproviders, maar `.env`
# staat op PROVIDER_MODE=live en die waarde won. Dat gaf geen foutmelding maar
# drie tests die stil over het netwerk gingen en daarop faalden — precies het
# soort verschil tussen "de code is stuk" en "de omgeving stond anders" dat
# uren kost om te herleiden. Tests mogen nooit afhangen van een .env die niet
# in de repository staat.
os.environ["PROVIDER_MODE"] = "mock"


import fitz  # noqa: E402  (PyMuPDF)
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlite3 import Connection as SQLite3Connection  # noqa: E402

from app.auth import get_current_user, get_current_user_of_querytoken
from app.database import get_db, Base
from app.main import app as fastapi_app
from app.models import User
import app.models  # Ensure all models are loaded

_TEST_USER = User(id="test-user-id", naam="Test User", email="test@etil.nl",
                  rol="admin", password_hash="")


def _override_auth():
    return _TEST_USER

# Use a single connection for in-memory SQLite to avoid multiple databases
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
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


class _GeenNetwerkInTests:
    """Een OpenAI-client die niet belt, maar het zegt.

    PROVIDER_MODE=mock hierboven is niet genoeg: niet elke modelcall kijkt
    ernaar. `_llm_classify_scope` bijvoorbeeld belt altijd, en dat gebeurde ook
    in de testsuite. De aanroeper vangt elke fout af en levert een lege
    uitkomst, dus dat kwam terug als een assertie die faalde op iets heel
    anders — of, met een geldige sleutel in `.env`, als een test die geld kost
    en per run een ander antwoord krijgt.

    Een `OPENAI_BASE_URL` naar een dode poort werkt ook, maar dan retryt de SDK
    eerst: dit bestand deed er 78 seconden over. Zo faalt het meteen, en staat
    er in de melding wat er echt aan de hand is.

    Een test die de client zélf vervangt (test_live_openai) overschrijft deze
    patch in zijn eigen body en merkt hier niets van.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, naam):
        raise RuntimeError(
            "Deze test roept een echt OpenAI-model aan. Vervang de modelcall "
            "(monkeypatch de betreffende functie) of laat de test hier niet "
            "langs komen."
        )


@pytest.fixture(autouse=True)
def _geen_echte_modelcalls(monkeypatch):
    import openai

    monkeypatch.setattr(openai, "AsyncOpenAI", _GeenNetwerkInTests)
    monkeypatch.setattr(openai, "AsyncAzureOpenAI", _GeenNetwerkInTests)


@pytest.fixture(autouse=True)
def _schone_temperature_cache():
    """`llm._ZONDER_TEMPERATURE` is state op moduleniveau en overleeft dus de
    test die hem vult.

    Een test in dit bestand die echt het netwerk op gaat krijgt van luna een
    400 op `temperature` terug, waarna het model in die set belandt. Elke
    latere test die luna gebruikt ziet dan geen temperature meer worden
    doorgegeven en faalt op iets wat niets met die test te maken heeft. Dat
    hing tot nu toe af van welk model er lokaal in `.env` stond.
    """
    from app.providers import llm
    llm._ZONDER_TEMPERATURE.clear()
    yield
    llm._ZONDER_TEMPERATURE.clear()


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def client():
    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[get_current_user] = _override_auth
    fastapi_app.dependency_overrides[get_current_user_of_querytoken] = _override_auth
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    """Directe toegang tot dezelfde testdatabase als de `client`-fixture, voor
    het opzetten van state die geen publieke endpoint heeft (bv. pipeline_runs,
    jaarverslag_monitoring-rijen)."""
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def pdf_bytes():
    """Minimale, geldige PDF met leesbare tekst."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Medewerkers: 138 werkzame personen in 2024.")
    return doc.tobytes()
