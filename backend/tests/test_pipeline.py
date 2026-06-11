"""Unit tests voor de kernlogica: strategie, schatting, reconciliatie, confidence."""
import pytest

from app.pipeline.confidence import bereken_confidence
from app.pipeline.reconcile import (Strategie, bepaal_strategie,
                                    proportionele_schatting, reconcilieer)
from app.providers.base import AgentFinding


def finding(wp=10, bron="website", zekerheid="hoog", limburg=True, fte=False,
            totaal_meerdere=False, peilmoment="2026"):
    return AgentFinding(wp_gevonden=wp, context="ctx", zekerheid=zekerheid, reden="t",
                        bron_url="https://x", bron_type=bron,
                        is_totaal_meerdere_vestigingen=totaal_meerdere,
                        is_limburg_specifiek=limburg, is_fte=fte, peilmoment=peilmoment)


# --- strategie ---

def test_strategie_single_locatie():
    assert bepaal_strategie(False, 1, 1) == Strategie.DIRECT_VERWERKEN

def test_strategie_alles_in_limburg():
    assert bepaal_strategie(False, 25, 25) == Strategie.DIRECT_VERWERKEN

def test_strategie_klein_multi():
    assert bepaal_strategie(False, 3, 1) == Strategie.GERICHTE_CHAT

def test_strategie_groot_multi():
    assert bepaal_strategie(False, 60, 4) == Strategie.VOLLEDIGE_CHAT_OF_BELLIJST

def test_strategie_lookup_failed():
    assert bepaal_strategie(True, None, None) == Strategie.VOLLEDIGE_CHAT_OF_BELLIJST


# --- proportionele schatting (v1.0-bug: crash op None) ---

def test_schatting_none_crasht_niet():
    assert proportionele_schatting(None, 5, 2) == (None, 0.0)

def test_schatting_berekening():
    schatting, penalty = proportionele_schatting(17000, 400, 15)
    assert schatting == 638
    assert penalty == 0.30  # gemaximeerd

def test_schatting_kleine_n():
    _, penalty = proportionele_schatting(100, 2, 1)
    assert penalty == pytest.approx(0.10)


# --- reconciliatie ---

def test_reconciliatie_geen_bronnen():
    r = reconcilieer(None, None, 1, 1)
    assert r.wp_kandidaat is None and r.n_bronnen == 0

def test_reconciliatie_bronnen_bevestigen():
    r = reconcilieer(finding(wp=100), finding(wp=105, bron="jaarverslag"), 1, 1)
    assert r.bronnen_consistent and r.wp_kandidaat == 100

def test_reconciliatie_conflict_single_locatie_website_wint():
    r = reconcilieer(finding(wp=10), finding(wp=500, bron="jaarverslag"), 1, 1)
    assert r.wp_kandidaat == 10 and not r.bronnen_consistent

def test_reconciliatie_multi_locatie_schatting():
    r = reconcilieer(None, finding(wp=17000, bron="jaarverslag", limburg=False), 400, 15)
    assert r.is_schatting and r.wp_kandidaat == 638


# --- confidence ---

def kwargs(**over):
    base = dict(count_nl=1, count_lb=1, adres_validated=True, n_bronnen=1,
                bronnen_consistent=False, peiljaar=2026)
    base.update(over)
    return base

def test_confidence_single_locatie_website_is_groen():
    s = bereken_confidence(finding(), **kwargs())
    assert s.label == "hoog" and s.score >= 0.80

def test_confidence_schatting_nooit_groen():
    s = bereken_confidence(finding(bron="jaarverslag", limburg=False), **kwargs(
        count_nl=400, count_lb=15), is_schatting=True, schatting_penalty=0.30)
    assert s.label == "laag"

def test_confidence_llm_laag_capt():
    s = bereken_confidence(finding(zekerheid="laag"), **kwargs())
    assert s.score <= 0.49 and s.label == "laag"

def test_confidence_fte_penalty():
    met = bereken_confidence(finding(fte=True), **kwargs())
    zonder = bereken_confidence(finding(fte=False), **kwargs())
    assert zonder.score - met.score == pytest.approx(0.10)

def test_confidence_breakdown_aanwezig():
    s = bereken_confidence(finding(), **kwargs())
    assert set(s.breakdown) >= {"locatie", "specificiteit", "bronkwaliteit",
                                "consensus", "adres", "actualiteit", "penalties"}
