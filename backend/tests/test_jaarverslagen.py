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
