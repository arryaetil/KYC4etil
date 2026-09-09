"""Wat er gebeurt als de database achterloopt op de modellen.

Lokaal merk je daar niets van: `create_all` maakt de tabellen daar vers aan.
Op Railway bestaat de tabel al, en dan is de vraag of `ensure_lightweight_migrations`
de ontbrekende kolommen erbij zet — zonder de rijen aan te raken die er staan.
"""
import sqlite3

import pytest
from sqlalchemy import create_engine, inspect

import app.database as database
from app.database import Base
import app.models  # noqa: F401  (zorgt dat elk model geladen is)


# Het schema zoals het eruitzag vóór de mappen-, prullenbak- en
# organisatielaag: precies het geval dat in productie voorkomt.
_OUD_SCHEMA = """
CREATE TABLE batches (id VARCHAR(36) PRIMARY KEY, naam VARCHAR(255), jaar INTEGER,
                      status VARCHAR(50), totaal INTEGER, verwerkt INTEGER);
CREATE TABLE companies (id VARCHAR(36) PRIMARY KEY, batch_id VARCHAR(36), naam VARCHAR(255),
                        vestigingsnummer VARCHAR(20), created_at TIMESTAMP);
CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, naam VARCHAR(100), email VARCHAR(255),
                    rol VARCHAR(50), password_hash VARCHAR(255), created_at TIMESTAMP);
INSERT INTO batches VALUES ('b1','Oude lijst',2025,'review',3,3);
INSERT INTO companies VALUES ('c1','b1','Mondriaan','V001','2025-01-01');
"""


@pytest.fixture
def oude_database(tmp_path, monkeypatch):
    pad = tmp_path / "oud.db"
    verbinding = sqlite3.connect(pad)
    verbinding.executescript(_OUD_SCHEMA)
    verbinding.commit()
    verbinding.close()

    engine = create_engine(f"sqlite:///{pad.as_posix()}")
    monkeypatch.setattr(database, "engine", engine)
    Base.metadata.create_all(bind=engine)
    yield pad, engine
    engine.dispose()


def test_ontbrekende_modelkolommen_worden_toegevoegd(oude_database):
    _, engine = oude_database

    database.ensure_lightweight_migrations()

    inspector = inspect(engine)
    for tabel in Base.metadata.sorted_tables:
        aanwezig = {kolom["name"] for kolom in inspector.get_columns(tabel.name)}
        ontbreekt = {kolom.name for kolom in tabel.columns} - aanwezig
        assert not ontbreekt, f"{tabel.name} mist {sorted(ontbreekt)}"


def test_bestaande_rijen_blijven_en_krijgen_hun_standaardwaarde(oude_database):
    pad, _ = oude_database

    database.ensure_lightweight_migrations()

    verbinding = sqlite3.connect(pad)
    try:
        naam, map_id, gemaakt, monitoring = verbinding.execute(
            "SELECT naam, map_id, created_at, is_monitoringlijst FROM batches"
        ).fetchone()
        assert naam == "Oude lijst"
        # Geen enkele lijst mag buiten beeld raken doordat de mappenlaag erbij kwam.
        assert map_id is not None
        assert gemaakt is not None
        # Niet NULL: het model belooft False, dus dat hoort er ook te staan.
        assert monitoring == 0
        assert verbinding.execute(
            "SELECT afgewerkt FROM companies"
        ).fetchone()[0] == 0
    finally:
        verbinding.close()


def test_tweede_keer_draaien_verandert_niets(oude_database):
    pad, engine = oude_database
    database.ensure_lightweight_migrations()
    voor = inspect(engine).get_columns("batches")

    database.ensure_lightweight_migrations()

    assert [kolom["name"] for kolom in inspect(engine).get_columns("batches")] == [
        kolom["name"] for kolom in voor
    ]
    verbinding = sqlite3.connect(pad)
    try:
        # Eén demomap, niet één per herstart.
        assert verbinding.execute("SELECT COUNT(*) FROM mappen").fetchone()[0] == 1
    finally:
        verbinding.close()
