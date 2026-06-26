"""Tests voor de Jaarverslag Chat Module."""
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.models import Base


def test_settings_heeft_openai_key():
    s = Settings(openai_api_key="sk-test", openai_model="gpt-4o-mini")
    assert s.openai_api_key == "sk-test"
    assert s.openai_model == "gpt-4o-mini"


def test_jaarverslag_tabellen_bestaan():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    namen = inspect(engine).get_table_names()
    assert "jaarverslag_uploads" in namen
    assert "jaarverslag_chat_messages" in namen


def test_upload_pdf_gelukt(client, pdf_bytes):
    resp = client.post(
        "/jaarverslagen/upload",
        files={"file": ("rapport.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "upload_id" in data
    assert data["bestandsnaam"] == "rapport.pdf"
    assert data["paginas"] == 1


def test_upload_geen_pdf_geeft_422(client):
    resp = client.post(
        "/jaarverslagen/upload",
        files={"file": ("data.csv", b"naam,wp\ntest,10", "text/csv")},
    )
    assert resp.status_code == 422


def test_upload_met_company_id(client, pdf_bytes):
    resp = client.post(
        "/jaarverslagen/upload",
        files={"file": ("rapport.pdf", pdf_bytes, "application/pdf")},
        data={"jaar": "2024"},
    )
    assert resp.status_code == 200
