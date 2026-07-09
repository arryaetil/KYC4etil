"""Unit tests voor de kernlogica: strategie, schatting, reconciliatie, confidence."""
import pytest

from app.pipeline.confidence import bereken_confidence
from app.pipeline.reconcile import (Strategie, bepaal_strategie,
                                    proportionele_schatting, reconcilieer)
from app.providers.base import AgentFinding


def finding(wp=10, bron="website", zekerheid="hoog", limburg=True, fte=False,
            totaal_meerdere=False, peilmoment="2026", context=None, url="https://x"):
    return AgentFinding(wp_gevonden=wp, context=context or f"{wp} medewerkers",
                        zekerheid=zekerheid, reden="t",
                        bron_url=url, bron_type=bron,
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

def test_reconciliatie_landelijk_totaal_zonder_vestigingscount_geen_kandidaat():
    r = reconcilieer(None, finding(wp=6158, bron="jaarverslag", limburg=False), None, None)
    assert r.finding is None
    assert r.wp_kandidaat is None
    assert not r.is_schatting

def test_reconciliatie_weigert_vacaturepagina_als_wp_kandidaat():
    r = reconcilieer(
        finding(wp=4, bron="media", url="https://jobs.ikea.com/nl/plaats/heerlen-jobs/4",
                context="Heerlen: 4"),
        None, 1, 1,
    )
    assert r.finding is None
    assert r.wp_kandidaat is None
    assert "vacature/jobs-pagina" in r.reden

def test_reconciliatie_weigert_context_die_wp_getal_niet_ondersteunt():
    r = reconcilieer(
        finding(wp=6500, bron="media", context="650 voltijdsbanen bij BAM"),
        None, 1, 1,
    )
    assert r.finding is None
    assert r.wp_kandidaat is None
    assert "context ondersteunt gekozen WP-getal" in r.reden

def test_reconciliatie_accepteert_website_zonder_gepersistenteerde_context():
    r = reconcilieer(
        AgentFinding(
            wp_gevonden=5, context=None, zekerheid="hoog", reden="team-pagina",
            bron_url="https://example.test/over-ons", bron_type="website",
            is_limburg_specifiek=True,
        ),
        None, 1, 1,
    )
    assert r.wp_kandidaat == 5

def test_reconciliatie_weigert_media_zonder_gepersistenteerde_context():
    r = reconcilieer(
        AgentFinding(
            wp_gevonden=5, context=None, zekerheid="hoog", reden="zoekresultaat",
            bron_url="https://example.test/over-ons", bron_type="media",
            is_limburg_specifiek=True,
        ),
        None, 1, 1,
    )
    assert r.wp_kandidaat is None

def test_reconciliatie_weigert_onwaarschijnlijk_jaarverslag_documenttype():
    r = reconcilieer(
        finding(
            wp=5, bron="jaarverslag",
            url="https://example.test/uploads/AVG-verklaring-2025.pdf",
            context="5 medewerkers",
        ),
        None, 1, 1,
    )
    assert r.wp_kandidaat is None
    assert "ander documenttype" in r.reden

def test_reconciliatie_weigert_juridische_holding_shell_als_vestiging():
    r = reconcilieer(
        finding(
            wp=2, bron="jaarverslag", fte=True,
            url="https://example.test/holding-bv-annual-report-fy25.pdf",
            context="The average number of staff employed by the Company, converted into full-time equivalents, amounted to 2, of which 0 were employed outside the Netherlands.",
        ),
        None, 1, 1,
    )
    assert r.wp_kandidaat is None
    assert "holding/shell" in r.reden

def test_reconciliatie_accepteert_context_met_aantoonbare_optelsom():
    r = reconcilieer(
        finding(wp=13, context="Ons team: 3 huisartsen, 6 assistentes, 2 praktijkondersteuners en 2 POH-GGZ."),
        None, 1, 1,
    )
    assert r.wp_kandidaat == 13


# --- confidence ---

def kwargs(**over):
    base = dict(count_nl=1, count_lb=1, adres_validated=True, n_bronnen=1,
                bronnen_consistent=False, peiljaar=2026)
    base.update(over)
    return base

def test_confidence_single_locatie_website_is_groen():
    s = bereken_confidence(finding(), **kwargs())
    assert s.label == "hoog" and s.score >= 0.80

def test_confidence_media_bron_wordt_niet_groen():
    s = bereken_confidence(finding(bron="media", zekerheid="hoog"), **kwargs())
    assert s.label != "hoog"
    assert s.score < 0.80

def test_confidence_schatting_nooit_groen():
    s = bereken_confidence(finding(bron="jaarverslag", limburg=False), **kwargs(
        count_nl=400, count_lb=15), is_schatting=True, schatting_penalty=0.30)
    assert s.label != "hoog" and s.score < 0.50

def test_confidence_llm_laag_is_rood():
    s = bereken_confidence(finding(zekerheid="laag"), **kwargs())
    assert s.label == "laag"

def test_confidence_llm_middel_is_geel():
    s = bereken_confidence(finding(zekerheid="middel"), **kwargs())
    assert s.label == "middel"

def test_confidence_fte_penalty():
    met = bereken_confidence(finding(fte=True), **kwargs())
    zonder = bereken_confidence(finding(fte=False), **kwargs())
    assert zonder.score > met.score

def test_confidence_breakdown_aanwezig():
    s = bereken_confidence(finding(), **kwargs())
    assert set(s.breakdown) >= {"zekerheid_llm", "base_score", "penalties", "bonuses"}
