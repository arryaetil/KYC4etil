"""Confidence scoring — uitgewerkte formule uit documentatie §9.
Gewogen som van 6 factoren + penalties; breakdown wordt opgeslagen
zodat reviewers zien wáárom een record 🟢/🟡/🔴 is."""
from dataclasses import dataclass

from ..config import get_settings
from ..providers.base import AgentFinding


@dataclass
class ScoreResult:
    score: float
    label: str          # hoog|middel|laag
    breakdown: dict


def _factor_locatie(count_nl: int | None, count_lb: int | None) -> float:
    """1 vestiging óf alle vestigingen in Limburg = eenduidig (nationaal totaal
    is dan ook het Limburg-totaal)."""
    if count_nl is None:
        return 0.0
    if count_nl == 1 or (count_lb is not None and count_lb == count_nl):
        return 1.0
    if count_nl <= 5:
        return 0.5
    return 0.0


def _factor_specificiteit(finding: AgentFinding, is_schatting: bool) -> float:
    if is_schatting:
        return 0.0
    if finding.is_limburg_specifiek and not finding.is_totaal_meerdere_vestigingen:
        return 1.0
    if finding.is_limburg_specifiek or finding.is_totaal_meerdere_vestigingen:
        return 0.5
    return 0.0


def _factor_bronkwaliteit(bron_type: str | None) -> float:
    return {"website": 1.0, "jaarverslag": 1.0, "media": 0.5}.get(bron_type or "", 0.0)


def _factor_consensus(n_bronnen: int, consistent: bool) -> float:
    if n_bronnen >= 2:
        return 1.0 if consistent else 0.0
    return 0.5


def _factor_actualiteit(peilmoment: str | None, peiljaar: int) -> float:
    if not peilmoment:
        return 0.0
    try:
        jaar = int(str(peilmoment)[:4])
    except ValueError:
        return 0.0
    if jaar >= peiljaar:
        return 1.0
    if jaar == peiljaar - 1:
        return 0.5
    return 0.0


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
    factors = {
        "locatie": (_factor_locatie(count_nl, count_lb), s.w_locatie),
        "specificiteit": (_factor_specificiteit(finding, is_schatting), s.w_specificiteit),
        "bronkwaliteit": (_factor_bronkwaliteit(finding.bron_type), s.w_bronkwaliteit),
        "consensus": (_factor_consensus(n_bronnen, bronnen_consistent), s.w_consensus),
        "adres": (1.0 if adres_validated else 0.0, s.w_adres),
        "actualiteit": (_factor_actualiteit(finding.peilmoment, peiljaar), s.w_actualiteit),
    }
    score = sum(f * w for f, w in factors.values())
    breakdown = {k: {"factor": f, "gewicht": w, "bijdrage": round(f * w, 4)}
                 for k, (f, w) in factors.items()}

    penalties = {}
    if locatie_bron == "places":  # fuzzy i.p.v. exact (KvK)
        penalties["places_fuzzy"] = s.penalty_places_fuzzy
    if finding.is_fte:
        penalties["fte_only"] = s.penalty_fte_only
    if is_schatting:
        penalties["proportionele_schatting"] = schatting_penalty
    score -= sum(penalties.values())
    breakdown["penalties"] = penalties

    # LLM-zekerheid kan een score alleen begrenzen, nooit verhogen
    if finding.zekerheid == "laag":
        score = min(score, s.cap_llm_laag)
        breakdown["cap_llm_laag"] = True

    score = max(0.0, min(1.0, round(score, 4)))
    label = "hoog" if score >= s.drempel_hoog else "middel" if score >= s.drempel_middel else "laag"
    return ScoreResult(score=score, label=label, breakdown=breakdown)
