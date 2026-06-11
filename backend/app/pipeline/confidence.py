"""Confidence scoring — zekerheid van de LLM als primair signaal.
Harde domeinregels (schatting, FTE) als correctie; geen MCDA-formule meer.
Breakdown bevat voldoende info voor uitlegbaarheid in de review-UI."""
from dataclasses import dataclass

from ..config import get_settings
from ..providers.base import AgentFinding

ZEKERHEID_BASE = {"hoog": 0.90, "middel": 0.65, "laag": 0.35}


@dataclass
class ScoreResult:
    score: float
    label: str          # hoog|middel|laag
    breakdown: dict


def bereken_confidence(
    finding: AgentFinding,
    count_nl: int | None,
    count_lb: int | None,
    adres_validated: bool,
    n_bronnen: int,
    bronnen_consistent: bool,
    peiljaar: int,
    is_schatting: bool = False,
    schatting_penalty: float = 0.0,
    locatie_bron: str = "mock",
) -> ScoreResult:
    s = get_settings()
    zekerheid = finding.zekerheid or "laag"
    score = ZEKERHEID_BASE.get(zekerheid, 0.35)

    penalties: dict[str, float] = {}
    bonuses: dict[str, float] = {}

    # Twee bronnen die elkaar bevestigen — extra vertrouwen
    if n_bronnen >= 2 and bronnen_consistent:
        bonuses["consensus"] = 0.08

    # FTE is niet hetzelfde als WP — kleine penalty
    if finding.is_fte:
        penalties["fte_only"] = s.penalty_fte_only

    # Proportionele schatting — nooit groen (harde domeinregel doc §9)
    if is_schatting:
        penalties["proportionele_schatting"] = schatting_penalty

    # Places-locatiecount is fuzzy i.p.v. KvK-exact
    if locatie_bron == "places":
        penalties["places_fuzzy"] = s.penalty_places_fuzzy

    score = score + sum(bonuses.values()) - sum(penalties.values())
    score = max(0.0, min(1.0, round(score, 4)))

    # Harde domeinregel: schatting nooit label 🟢 (doc §9)
    if is_schatting:
        score = min(score, s.drempel_middel - 0.01)

    label = "hoog" if score >= s.drempel_hoog else "middel" if score >= s.drempel_middel else "laag"

    breakdown = {
        "zekerheid_llm": zekerheid,
        "base_score": round(ZEKERHEID_BASE.get(zekerheid, 0.35), 4),
        "bonuses": bonuses,
        "penalties": penalties,
        "bron_type": finding.bron_type or "onbekend",
        "n_bronnen": n_bronnen,
    }

    return ScoreResult(score=score, label=label, breakdown=breakdown)
