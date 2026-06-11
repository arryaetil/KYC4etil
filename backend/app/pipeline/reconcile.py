"""Reconciliatie (doc §7 stap 3) en multi-locatiestrategie (doc §10)."""
from dataclasses import dataclass
from enum import Enum

from ..providers.base import AgentFinding


class Strategie(str, Enum):
    DIRECT_VERWERKEN = "auto"
    GERICHTE_CHAT = "gerichte_chat"
    VOLLEDIGE_CHAT_OF_BELLIJST = "volledige_chat_of_bellijst"


def bepaal_strategie(lookup_failed: bool, count_nl: int | None, count_lb: int | None) -> Strategie:
    """Strategie o.b.v. locatiecount — vóór de agents draaien."""
    if lookup_failed or count_nl is None:
        return Strategie.VOLLEDIGE_CHAT_OF_BELLIJST
    if count_nl == 1 or count_lb == count_nl:  # alles in Limburg = eenduidig
        return Strategie.DIRECT_VERWERKEN
    if count_nl <= 5:
        return Strategie.GERICHTE_CHAT
    return Strategie.VOLLEDIGE_CHAT_OF_BELLIJST


def proportionele_schatting(wp_totaal: int | None, n_nl: int | None, n_lb: int | None) -> tuple[int | None, float]:
    """Alleen aanroepen als wp_totaal bekend is (na agents).
    Retourneert (schatting, confidence_penalty). Bekende beperking:
    veronderstelt gelijke vestigingsgrootte — daarom nooit 🟢."""
    if not wp_totaal or not n_nl or n_lb is None:
        return None, 0.0
    schatting = round(wp_totaal * (n_lb / n_nl))
    penalty = min(0.30, 0.10 + max(0, n_nl - 2) * 0.05)
    return schatting, penalty


@dataclass
class ReconciliatieResultaat:
    finding: AgentFinding | None
    wp_kandidaat: int | None
    is_schatting: bool
    schatting_penalty: float
    n_bronnen: int
    bronnen_consistent: bool
    reden: str


def reconcilieer(
    website: AgentFinding | None,
    jaarverslag: AgentFinding | None,
    count_nl: int | None,
    count_lb: int | None,
) -> ReconciliatieResultaat:
    """Beslisregels doc §7 stap 3."""
    w = website if website and website.wp_gevonden else None
    j = jaarverslag if jaarverslag and jaarverslag.wp_gevonden else None
    multi = count_nl is not None and count_nl > 1 and count_lb != count_nl

    if not w and not j:
        return ReconciliatieResultaat(None, None, False, 0.0, 0, False,
                                      "geen bron gevonden")

    if w and j:
        verschil = abs(w.wp_gevonden - j.wp_gevonden) / max(w.wp_gevonden, j.wp_gevonden)
        if verschil <= 0.10:
            return ReconciliatieResultaat(w, w.wp_gevonden, False, 0.0, 2, True,
                                          f"website en jaarverslag bevestigen elkaar ({verschil:.0%} verschil)")
        if not multi:
            return ReconciliatieResultaat(w, w.wp_gevonden, False, 0.0, 2, False,
                                          f"bronnen wijken {verschil:.0%} af; website wint bij single-locatie "
                                          f"(jaarverslag mogelijk groepscijfer: {j.wp_gevonden})")
        # multi-locatie: jaarverslag-totaal -> proportionele schatting
        schatting, penalty = proportionele_schatting(j.wp_gevonden, count_nl, count_lb)
        return ReconciliatieResultaat(j, schatting, True, penalty, 2, False,
                                      f"multi-locatie: jaarverslagtotaal {j.wp_gevonden} proportioneel verdeeld "
                                      f"({count_lb}/{count_nl} vestigingen); website-hint: {w.wp_gevonden}")

    bron = w or j
    # Eén bron met een niet-Limburg-totaal bij multi-locatie -> schatting
    if multi and bron.is_limburg_specifiek is False:
        schatting, penalty = proportionele_schatting(bron.wp_gevonden, count_nl, count_lb)
        return ReconciliatieResultaat(bron, schatting, True, penalty, 1, False,
                                      f"nationaal totaal {bron.wp_gevonden} proportioneel verdeeld "
                                      f"({count_lb}/{count_nl} vestigingen)")
    return ReconciliatieResultaat(bron, bron.wp_gevonden, False, 0.0, 1, False,
                                  f"enige bron: {bron.bron_type}")
