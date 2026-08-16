"""Verklaarbare bronranking, bewust gescheiden van WP-confidence."""
from dataclasses import dataclass
from datetime import date

from ..config import get_settings
from .validation import BronValidatie


@dataclass
class RankedBron:
    document: object
    ranking_score: float
    score_breakdown: dict[str, float]
    identity_class: str
    validaties: dict
    waarschuwingen: list[str]


def _identity_score(identity_class: str) -> float:
    return {
        "exact_entity": 1.0,
        "same_brand_or_group": 0.65,
        "possible_match": 0.4,
        "unknown": 0.25,
        "mismatch": 0.0,
    }.get(identity_class, 0.25)


def _authority_score(bron: BronValidatie) -> float:
    if bron.is_officieel is True:
        return 1.0
    return {
        "overheid": 0.9,
        "sectorportaal": 0.85,
        "media": 0.65,
        "directory": 0.25,
        "sociaal_profiel": 0.2,
    }.get(bron.document.brontype, 0.45)


def _relevance_score(bron: BronValidatie) -> float:
    document = bron.document
    score = 0.35
    if document.documenttype in {
        "jaarverslag", "jaarrekening", "bestuursverslag",
        "teampagina", "organisatiepagina", "nieuwsartikel",
        "duo_personeel_personen",
    }:
        score += 0.25
    if document.gevraagd_jaar is not None and document.verslagjaar == document.gevraagd_jaar:
        score += 0.25
    if document.wp_gevonden is not None:
        score += 0.15
    return min(score, 1.0)


def _freshness_score(bron: BronValidatie, referentiedatum: date) -> float:
    """Actualiteit uit publicatiedatum, en anders uit het verslagjaar.

    Deze component was in productie volledig dood: `publicatiedatum` is bij
    0 van de 929 opgeslagen kandidaten gevuld, dus de functie gaf altijd 0,45
    terug. Standaarddeviatie 0,000 over alle kandidaten — het gewicht van 0,15
    verlaagde elke score met exact hetzelfde bedrag en onderscheidde niets.

    `verslagjaar` is bij 34,8% wél gevuld en zegt precies wat we willen weten.
    Een jaarverslag over jaar X verschijnt pas in X+1, dus één jaar verschil is
    normaal en geen reden voor een penalty (zie
    `peilmoment_max_leeftijd_jaren`). Een onbekend peilmoment blijft neutraal.
    """
    publication = bron.document.publicatiedatum
    if publication is not None:
        maanden = max(
            0,
            (referentiedatum.year - publication.year) * 12
            + referentiedatum.month - publication.month,
        )
        if maanden <= 6:
            return 1.0
        if maanden <= 18:
            return 0.8
        if maanden <= 36:
            return 0.55
        return 0.25

    verslagjaar = bron.document.verslagjaar
    if verslagjaar is None:
        return 0.45
    jaren = max(0, referentiedatum.year - verslagjaar)
    if jaren <= 1:
        return 1.0
    if jaren == 2:
        return 0.8
    if jaren == 3:
        return 0.55
    return 0.25


def _evidence_score(bron: BronValidatie) -> float:
    document = bron.document
    if document.eenheid != "werkzame_personen":
        return 0.0
    if document.wp_gevonden is None:
        return 0.0
    return 1.0 if document.bewijsfragment else 0.4


def _menselijke_waarde(bron: BronValidatie) -> dict[str, str]:
    document = bron.document
    heeft_wp_bewijs = (
        document.wp_gevonden is not None
        and document.eenheid == "werkzame_personen"
        and bool(document.bewijsfragment)
    )
    telopdracht = bron.validaties.get("naamlijst_telling_aan_reviewer")
    if telopdracht:
        namen = telopdracht.get("genoemde_namen") or []
        return {
            "rol": "telopdracht",
            "label": "Tel de medewerkers zelf",
            "actie": (
                "Deze pagina toont de leidinglaag, niet het personeelsbestand — "
                "tel de medewerkers op de bron zelf."
                if telopdracht.get("reden") == "leidinggevendenlijst"
                else "Deze namenlijst gaat breder dan deze vestiging — tel op de "
                "bron zelf hoeveel personen bij déze vestiging horen."
            ),
            "aantal_namen": len(namen),
        }
    if heeft_wp_bewijs and document.scope_class in {"vestiging", "limburg"}:
        return {
            "rol": "direct_wp_bewijs",
            "label": "Direct WP-bewijs",
            "actie": "Controleer het citaat en de scope; het personeelsgetal staat al in de bron.",
        }
    if heeft_wp_bewijs and document.brontype == "media":
        return {
            "rol": "actuele_context",
            "label": "Actuele indicatie organisatieomvang",
            "actie": "Gebruik het recente personeelscijfer om groei of krimp sinds de formele bron te beoordelen.",
        }
    if heeft_wp_bewijs:
        return {
            "rol": "organisatieomvang",
            "label": "Indicatie organisatieomvang",
            "actie": "Gebruik dit groeps- of organisatiecijfer als context en zoek in de bron naar een vestigingsuitsplitsing.",
        }
    if document.documenttype == "teampagina":
        return {
            "rol": "teamoverzicht",
            "label": "Teamoverzicht",
            "actie": "Bekijk of tel de genoemde teamleden en controleer of alle functies en locaties zijn opgenomen.",
        }
    if document.documenttype in {
        "jaarverslag", "jaarrekening", "bestuursverslag", "pdf_document",
    }:
        return {
            "rol": "formeel_document",
            "label": "Formeel document",
            "actie": "Doorzoek het document op medewerkers, personeel, werknemers, fte en vestigingsnamen.",
        }
    if bron.is_officieel is True:
        return {
            "rol": "officiele_route",
            "label": "Officiële onderzoeksroute",
            "actie": "Open team-, over-ons-, contact- en locatiepagina’s om de personeelsomvang te herleiden.",
        }
    if document.brontype in {"overheid", "sectorportaal"}:
        return {
            "rol": "register_of_sectorbron",
            "label": "Register- of sectorbron",
            "actie": "Controleer organisatie-identiteit, vestigingsscope en eventuele personeelsklasse.",
        }
    if document.brontype == "media":
        return {
            "rol": "actuele_context",
            "label": "Actuele context",
            "actie": "Gebruik recente groei, krimp, overname of reorganisatie om formele cijfers te actualiseren.",
        }
    return {
        "rol": "aanvullende_context",
        "label": "Aanvullende onderzoeksroute",
        "actie": "Controleer de bron op namen, locaties of verwijzingen naar een sterkere primaire bron.",
    }


def rank_bronnen(
    bronnen: list[BronValidatie],
    referentiedatum: date | None = None,
) -> list[RankedBron]:
    settings = get_settings()
    referentiedatum = referentiedatum or date.today()
    ranked: list[RankedBron] = []

    for bron in bronnen:
        if bron.is_afgewezen:
            continue
        breakdown = {
            "identiteit": _identity_score(bron.identity_class),
            "autoriteit": _authority_score(bron),
            "relevantie": _relevance_score(bron),
            "actualiteit": _freshness_score(bron, referentiedatum),
            "bewijs": _evidence_score(bron),
        }
        score = (
            settings.rank_w_identiteit * breakdown["identiteit"]
            + settings.rank_w_autoriteit * breakdown["autoriteit"]
            + settings.rank_w_relevantie * breakdown["relevantie"]
            + settings.rank_w_actualiteit * breakdown["actualiteit"]
            + settings.rank_w_bewijs * breakdown["bewijs"]
        )
        ranked.append(RankedBron(
            document=bron.document,
            ranking_score=round(score, 4),
            score_breakdown=breakdown,
            identity_class=bron.identity_class,
            validaties={
                **bron.validaties,
                "menselijke_waarde": _menselijke_waarde(bron),
            },
            waarschuwingen=list(bron.waarschuwingen),
        ))

    return sorted(ranked, key=lambda item: item.ranking_score, reverse=True)


def _is_vestigingsanker(kandidaat: RankedBron) -> bool:
    document = kandidaat.document
    return (
        document.scope_class == "vestiging"
        and document.wp_gevonden is not None
        and bool(document.bewijsfragment)
    )


def behoud_vestigingsanker(
    ranked: list[RankedBron], maximum: int,
) -> list[RankedBron]:
    """Verdringt nooit een bevestigde vestigingsbron door een zwakkere,
    algemenere kandidaat bij het afkappen op `maximum`.

    Regressie: de researchflow vond bij Hallux Podotherapie de juiste
    vestigingspagina (vier met naam genoemde medewerkers), maar de
    uiteindelijke top-3 bevatte toch de algemene teampagina in plaats daarvan
    — de ranking beloont autoriteit/actualiteit/bewijs, maar niet of een
    kandidaat expliciet over déze vestiging gaat. Zodra een kandidaat met
    vestigingsscope én concreet WP-bewijs bestaat, blijft die in de top ook
    als de kale score lager uitvalt dan een generieke concernpagina.
    """
    top = ranked[:maximum]
    if not top or any(_is_vestigingsanker(kandidaat) for kandidaat in top):
        return top
    for kandidaat in ranked[maximum:]:
        if _is_vestigingsanker(kandidaat):
            return top[:-1] + [kandidaat]
    return top


def selecteer_bronportfolio(
    ranked: list[RankedBron],
    maximum: int,
    maximum_per_rol: int = 2,
) -> list[RankedBron]:
    """Behoud sterke complementaire routes zonder een rij rol-duplicaten."""
    if maximum <= 0 or maximum_per_rol <= 0 or not ranked:
        return []
    gekozen = [ranked[0]]
    gekozen_ids = {id(ranked[0])}
    eerste_rol = ranked[0].validaties["menselijke_waarde"]["rol"]
    rol_aantallen = {eerste_rol: 1}
    for kandidaat in ranked[1:]:
        rol = kandidaat.validaties["menselijke_waarde"]["rol"]
        if rol in rol_aantallen:
            continue
        gekozen.append(kandidaat)
        gekozen_ids.add(id(kandidaat))
        rol_aantallen[rol] = 1
        if len(gekozen) >= maximum:
            return gekozen
    for kandidaat in ranked:
        if id(kandidaat) in gekozen_ids:
            continue
        rol = kandidaat.validaties["menselijke_waarde"]["rol"]
        if rol_aantallen.get(rol, 0) >= maximum_per_rol:
            continue
        gekozen.append(kandidaat)
        gekozen_ids.add(id(kandidaat))
        rol_aantallen[rol] = rol_aantallen.get(rol, 0) + 1
        if len(gekozen) >= maximum:
            break

    # Vul aan tot het maximum met de hoogst gerangschikte overgeblevenen.
    # Zonder deze stap kan de rollimiet de lijst kleiner maken dan hij mag
    # zijn: acht kandidaten in dezelfde rol leverden er dan twee op. Dat was
    # de reden om deze functie niet aan te sluiten. Diversiteit hoort de
    # vólgorde te bepalen, niet het aantal — de reviewer verliest liever geen
    # bron.
    if len(gekozen) < maximum:
        for kandidaat in ranked:
            if id(kandidaat) in gekozen_ids:
                continue
            gekozen.append(kandidaat)
            gekozen_ids.add(id(kandidaat))
            if len(gekozen) >= maximum:
                break
    return gekozen
