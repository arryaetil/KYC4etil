"""Reconciliatie (doc §7 stap 3) en multi-locatiestrategie (doc §10)."""
from dataclasses import dataclass
from enum import Enum
import re
from urllib.parse import urlparse

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


def _is_vacature_of_jobs_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url.lower())
    haystack = f"{parsed.netloc} {parsed.path} {parsed.query}"
    markers = (
        "job", "jobs", "vacature", "vacatures", "career", "careers",
        "werken-bij", "werkenbij", "recruitment",
    )
    return any(marker in haystack for marker in markers)


def _is_onwaarschijnlijke_jaarverslag_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url.lower())
    haystack = f"{parsed.netloc} {parsed.path} {parsed.query}"
    negatieve_markers = (
        "avg", "privacy", "cookie", "voorwaarden", "disclaimer", "klachten",
        "reglement", "protocol", "brochure", "flyer", "vacature", "job",
    )
    if any(marker in haystack for marker in negatieve_markers):
        return True
    # Veel echte jaarverslagen hebben opaque CDN/PDF-URLs. Alleen duidelijke negatieve
    # documenttypen afwijzen; document-identiteit blijft verder bij de bronvalidatie.
    return False


_GENERIEKE_CONTEXT_PATROON = re.compile(
    r"^\s*aantal\b[^.]{0,60}\b(werkzame personen|medewerkers)\b[^.]{0,20}\bbij\b",
    re.IGNORECASE,
)


def _is_generieke_vraagherhaling(context: str) -> bool:
    """Herkent een 'context' die feitelijk gewoon de extractievraag herhaalt
    (bv. "Aantal werkzame personen bij Koninklijke BAM Groep N.V.") zonder een
    echt citaat te zijn — geen getal, geen namen, geen inhoud. Dit is precies het
    patroon dat bij Zuyderland en Koninklijke BAM een niet-onderbouwd getal liet
    doorglippen."""
    return bool(_GENERIEKE_CONTEXT_PATROON.match(context.strip()))


def _vereist_context_steun(finding: AgentFinding) -> bool:
    """Context-steun is altijd verplicht voor risicovollere bron_types (media,
    jaarverslag), én voor ELK bron_type zodra de context een kale herhaling van de
    extractievraag blijkt te zijn i.p.v. een echt citaat.

    Website/team-pagina's blijven verder vrijgesteld: veel legitieme vondsten (bv.
    een naamlijst als "Anne, Maral, Heidi, Monique") noemen het getal zelf niet
    letterlijk, en dat mag niet worden afgestraft — alleen een context die duidelijk
    géén echt citaat is (de vraag herhaalt) wordt alsnog geblokkeerd.
    """
    context = (finding.context or "").strip()
    if finding.bron_type in {"media", "jaarverslag"}:
        return True
    return bool(context) and _is_generieke_vraagherhaling(context)


def _is_juridische_holding_shell(finding: AgentFinding) -> bool:
    if finding.bron_type != "jaarverslag" or not finding.wp_gevonden:
        return False
    haystack = " ".join(filter(None, [
        finding.bron_url or "",
        finding.context or "",
        finding.reden or "",
    ])).lower()
    holding_marker = "holding" in haystack
    legal_shell_marker = (
        "outside the netherlands" in haystack
        or "employed outside the netherlands" in haystack
        or "buiten nederland" in haystack
    )
    return finding.wp_gevonden <= 10 and finding.is_fte and (holding_marker or legal_shell_marker)


def _context_ondersteunt_wp_getal(finding: AgentFinding) -> bool:
    """Voorkomt dat een LLM een getal kiest dat niet in de geciteerde context staat.

    Dit vangt zoekresultaten af waar een vacatureaantal of verkeerd gelezen
    deeltal als totaal aantal werkzame personen wordt gebruikt.
    """
    if not finding.wp_gevonden:
        return True
    context = (finding.context or "").lower()
    if not context:
        return False
    wp = str(finding.wp_gevonden)
    variants = {
        wp,
        f"{finding.wp_gevonden:,}".replace(",", "."),
        f"{finding.wp_gevonden:,}".replace(",", " "),
    }
    if any(variant in context for variant in variants):
        return True
    # Sta compacte duizendtallen toe als de context "2.235" bevat en het model 2235 retourneert.
    digits_only = re.sub(r"\D", "", context)
    if wp in digits_only:
        return True
    aantallen = [
        int(match)
        for match in re.findall(r"\b\d{1,3}\b", context)
        if int(match) < 100
    ]
    return bool(aantallen) and sum(aantallen) == finding.wp_gevonden


def _candidate_hard_gate(finding: AgentFinding) -> str | None:
    if _is_vacature_of_jobs_url(finding.bron_url):
        return "bron is een vacature/jobs-pagina en telt vacatures, niet werkzame personen"
    if finding.bron_type == "jaarverslag" and _is_onwaarschijnlijke_jaarverslag_url(finding.bron_url):
        return "bron lijkt geen jaarverslag/jaarrekening maar een ander documenttype"
    if _is_juridische_holding_shell(finding):
        return "jaarverslag lijkt een juridische holding/shell te beschrijven, niet de vestiging"
    if _vereist_context_steun(finding) and not _context_ondersteunt_wp_getal(finding):
        return (
            f"context ondersteunt gekozen WP-getal {finding.wp_gevonden} niet letterlijk; "
            "niet veilig als kandidaat"
        )
    return None


def reconcilieer(
    website: AgentFinding | None,
    jaarverslag: AgentFinding | None,
    count_nl: int | None,
    count_lb: int | None,
) -> ReconciliatieResultaat:
    """Beslisregels doc §7 stap 3."""
    w = website if website and website.wp_gevonden else None
    j = jaarverslag if jaarverslag and jaarverslag.wp_gevonden else None
    afgewezen: list[str] = []
    for label, finding in (("website", w), ("jaarverslag", j)):
        if finding:
            reden = _candidate_hard_gate(finding)
            if reden:
                afgewezen.append(f"{label}: {reden}")
                if label == "website":
                    w = None
                else:
                    j = None
    multi = count_nl is not None and count_nl > 1 and count_lb != count_nl

    if not w and not j:
        if afgewezen:
            return ReconciliatieResultaat(None, None, False, 0.0, 0, False,
                                          "bronnen afgewezen door hard gate: " + "; ".join(afgewezen))
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
    # Eén bron met een niet-Limburg-specifiek getal (bv. landelijk concerntotaal) mag NOOIT
    # zomaar als kandidaat voor déze vestiging gelden — dat getal is per definitie te hoog.
    if bron.is_limburg_specifiek is False:
        if count_nl:
            schatting, penalty = proportionele_schatting(bron.wp_gevonden, count_nl, count_lb)
            return ReconciliatieResultaat(bron, schatting, True, penalty, 1, False,
                                          f"nationaal totaal {bron.wp_gevonden} proportioneel verdeeld "
                                          f"({count_lb}/{count_nl} vestigingen)")
        # Geen vestigingscount bekend -> geen enkele manier om het landelijke getal te
        # herleiden naar déze locatie (doc §7); dan liever geen kandidaat dan een vals-
        # betrouwbaar landelijk getal (kan anders zelfs 🟢 hoog worden, zoals bij een
        # generieke jaarverslag-zoekopdracht die het cijfer van een heel ander bedrijf
        # oppikt — precies het scenario waar deze regel tegen beschermt).
        return ReconciliatieResultaat(None, None, False, 0.0, 1, False,
                                      f"enige bron ({bron.bron_type}) is niet-Limburg-specifiek "
                                      f"en aantal vestigingen onbekend — niet herleidbaar naar deze locatie")
    return ReconciliatieResultaat(bron, bron.wp_gevonden, False, 0.0, 1, False,
                                  f"enige bron: {bron.bron_type}")


def signaleer_afwijkende_extra_bronnen(
    wp_kandidaat: int | None, extra_bronnen: list[AgentFinding], drempel: float = 0.20,
) -> str | None:
    """Zuiver informatief signaal voor de reviewer — verandert NOOIT de confidence-
    score of het label. Extra bronnen kunnen immers een andere, gelijknamige entiteit
    betreffen (bv. 'Huisartsenpraktijk Centrum X' vs 'Huisartsenpraktijk X') zonder dat
    de gekozen kandidaat daarmee fout is; dat verifiëren hoort bij de reviewer, niet bij
    een automatische score-aanpassing."""
    if not wp_kandidaat or not extra_bronnen:
        return None
    afwijkend = [
        (bron, abs(bron.wp_gevonden - wp_kandidaat) / max(bron.wp_gevonden, wp_kandidaat))
        for bron in extra_bronnen
        if bron.wp_gevonden and abs(bron.wp_gevonden - wp_kandidaat) / max(bron.wp_gevonden, wp_kandidaat) > drempel
    ]
    if not afwijkend:
        return None
    details = "; ".join(f"{bron.bron_url} noemt {bron.wp_gevonden} ({verschil:.0%} afwijking)"
                        for bron, verschil in afwijkend)
    return (
        f"Let op: extra bron(nen) wijken sterk af van de gekozen kandidaat ({wp_kandidaat}): {details}. "
        "Controleer adres/telefoonnummer voordat je goedkeurt — dit kan een gelijknamige "
        "maar andere vestiging/entiteit betreffen."
    )
