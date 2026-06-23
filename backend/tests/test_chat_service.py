"""Tests for chat_service response parsing and gegevens extraction."""
import json
import pytest
from app.chat_service import _parse_response


def test_parse_response_with_gegevens():
    raw = json.dumps({
        "reply": "Dank u. Hoeveel uitzendkrachten?",
        "done": False,
        "gegevens": {"wp_totaal": 25, "eigen_personeel": 20, "uitzend": None}
    })
    result = _parse_response(raw)
    assert result["reply"] == "Dank u. Hoeveel uitzendkrachten?"
    assert result["done"] is False
    assert result["gegevens"]["wp_totaal"] == 25
    assert result["gegevens"]["uitzend"] is None


def test_parse_response_without_gegevens():
    raw = json.dumps({"reply": "Hallo!", "done": False})
    result = _parse_response(raw)
    assert result["reply"] == "Hallo!"
    assert "gegevens" not in result


def test_parse_response_done_with_antwoorden_and_gegevens():
    raw = json.dumps({
        "reply": "Bedankt!",
        "done": True,
        "gegevens": {"wp_totaal": 25, "uitzend": 5},
        "antwoorden": {"wp_totaal": 25, "uitzend": 5}
    })
    result = _parse_response(raw)
    assert result["done"] is True
    assert result["gegevens"]["wp_totaal"] == 25
    assert result["antwoorden"]["wp_totaal"] == 25


def test_parse_response_code_fence_with_gegevens():
    raw = '```json\n' + json.dumps({
        "reply": "Test",
        "done": False,
        "gegevens": {"wp_totaal": 10}
    }) + '\n```'
    result = _parse_response(raw)
    assert result["gegevens"]["wp_totaal"] == 10


def test_parse_response_fallback_regex_no_gegevens():
    raw = '{"reply": "broken json", "done": false, extra'
    result = _parse_response(raw)
    assert "broken json" in result["reply"]
    assert result["done"] is False
