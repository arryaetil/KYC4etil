"""Goedkope, deterministische bronvalidatie vóór semantische verdieping."""
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date
from urllib.parse import urlsplit

from ..config import get_settings
from ..pipeline.identity_scope import (
    domain_matches_company,
    heuristic_identity_class,
)

# Een bestuurs-, directie- of MT-pagina toont de leidinglaag van een
# organisatie, niet het personeelsbestand. Zes namen op zo'n pagina zijn geen
# zes werkzame personen — dat is precies hoe de Poolse moedergroep van
# Okechamp met zes bestuurders als vestiging van 138 WP in het register kwam.
_LEIDINGGEVENDENPAGINA = {
    "aandeelhouders", "akcjonariusze", "bestuur", "bestuurders", "board",
    "directie", "directieteam", "leadership", "management", "managementteam",
    "raad-van-bestuur", "raad-van-toezicht", "toezicht", "zarzad",
}
# Scopes waarbij een uit namen afgeleide telling aantoonbaar niet over déze
# vestiging gaat. "unknown"/"onbekend" horen hier bewust NIET bij: gemeten op
# de productieruns staan Poulissen en Dreessen — waar de telling juist klopt —
# allebei op unknown, en alleen Hallux op vestiging.
_SCOPE_BUITEN_VESTIGING = {"concern", "nederland"}


def _normaliseer(waarde: str) -> str:
    return unicodedata.normalize("NFKD", waarde).encode(
        "ascii", "ignore",
    ).decode("ascii").lower()


def is_leidinggevendenlijst(document: "SourceDocument") -> bool:
    pad_en_titel = _normaliseer(
        f"{urlsplit(document.url).path} {document.titel or ''}"
    )
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", pad_en_titel)
        for term in _LEIDINGGEVENDENPAGINA
    )


# Sleutel op `validaties`. Onderscheidt "we hebben gezocht en er staat geen
# getal in" van "hier is nog niet naar gekeken" — twee dingen die er voor de
# reviewer hetzelfde uitzagen, namelijk een lege Bewijs-regel, en die bepalen of
# hij het document zelf nog moet openen.
WP_EXTRACTIE = "wp_extractie"
WP_GEZOCHT_NIETS_GEVONDEN = "gezocht_niets_gevonden"
WP_GEVONDEN = "gevonden"


@dataclass(frozen=True)
class SourceDocument:
    naam: str
    company_website_url: str | None
    url: str
    titel: str = ""
    tekst: str = ""
    brontype: str = "overig"
    documenttype: str | None = None
    gevraagd_jaar: int | None = None
    verslagjaar: int | None = None
    publicatiedatum: date | None = None
    informatie_peilmoment: str | None = None
    wp_gevonden: int | None = None
    eenheid: str | None = None
    bewijsfragment: str | None = None
    bron_pagina: int | None = None
    scope_class: str | None = None
    research_route: str | None = None
    # Is er daadwerkelijk in dit document naar een personeelsgetal gezocht?
    # Alleen de plekken die de extractie uitvoeren zetten dit op True; zo blijft
    # "nog niet uitgelezen" een eerlijke mededeling in plaats van een aanname.
    wp_extractie_gedaan: bool = False
    raw_data: dict | None = None


@dataclass
class BronValidatie:
    document: SourceDocument
    identity_class: str
    is_officieel: bool | None
    is_afgewezen: bool
    afwijsredenen: list[str] = field(default_factory=list)
    validaties: dict = field(default_factory=dict)
    waarschuwingen: list[str] = field(default_factory=list)


def draag_naamlijsttelling_over_aan_reviewer(
    validatie: BronValidatie, scope_class: str | None = None,
) -> BronValidatie:
    """Zet een onbetrouwbare namenlijst-telling om in een telopdracht.

    De agent mag namen op een teampagina tellen (dat is bij kleine bedrijven
    het juiste antwoord), maar niet wanneer die lijst aantoonbaar niet het
    personeelsbestand van déze vestiging is. In dat geval verdwijnt het getal
    als WP-voorstel en houdt de reviewer de namenlijst over om zelf te tellen.

    Idempotent: draait zowel vóór als ná de scope-bepaling van de reviewer,
    en doet niets zodra het getal al is ingetrokken.
    """
    document = validatie.document
    if document.wp_gevonden is None:
        return validatie
    if not (document.raw_data or {}).get("wp_afgeleid_uit_naamlijst"):
        return validatie

    scope = scope_class or document.scope_class
    if is_leidinggevendenlijst(document):
        reden = "leidinggevendenlijst"
    elif scope in _SCOPE_BUITEN_VESTIGING:
        reden = "scope_buiten_vestiging"
    else:
        return validatie

    validatie.document = replace(document, wp_gevonden=None, eenheid=None)
    # Houd de afgeleide validatievlaggen gelijk aan het document, anders
    # blijft de UI "heeft WP-getal" tonen voor een ingetrokken voorstel.
    if "heeft_wp" in validatie.validaties:
        validatie.validaties["heeft_wp"] = False
    if "eenheid_is_wp" in validatie.validaties:
        validatie.validaties["eenheid_is_wp"] = False
    validatie.validaties["naamlijst_telling_aan_reviewer"] = {
        "reden": reden,
        "afgeleid_aantal": document.wp_gevonden,
        "genoemde_namen": (document.raw_data or {}).get("genoemde_namen") or [],
    }
    if "naamlijst_telling_aan_reviewer" not in validatie.waarschuwingen:
        validatie.waarschuwingen.append("naamlijst_telling_aan_reviewer")
    return validatie


def _duo_jaar_is_aanvaardbaar_ouder(document: SourceDocument) -> bool:
    """Mag deze DUO-bron met een ouder meetjaar tóch beoordeeld worden?

    Alleen DUO, en alleen binnen `peilmoment_max_leeftijd_jaren` — dezelfde
    grens die de confidence gebruikt voor "een jaar verschil is normaal".
    Twee jaar achter blijft een afwijzing: dan is er inmiddels nieuwere DUO-data
    en kijkt de reviewer naar een achterhaald bestand.

    `duo.lees_personeelswaarden` pakt zelf al het nieuwste jaar dat niet ná het
    gevraagde jaar ligt, en `_relevance_score` beloont een gelijk jaar. Het
    gevraagde jaar wint dus vanzelf zodra DUO het publiceert.
    """
    if document.documenttype != "duo_personeel_personen":
        return False
    grens = get_settings().peilmoment_max_leeftijd_jaren
    return 0 < (document.gevraagd_jaar - document.verslagjaar) <= grens


def valideer_bron(document: SourceDocument) -> BronValidatie:
    context = " ".join(filter(None, [
        document.titel,
        document.bewijsfragment,
        document.tekst[:10000],
    ]))
    identity = heuristic_identity_class(
        document.naam,
        context,
        document.url,
        document.company_website_url,
    )
    domein_match = domain_matches_company(
        document.url, document.company_website_url
    )
    is_officieel = True if domein_match is True else (
        False if document.brontype in {"media", "directory", "sociaal_profiel"} else None
    )

    afwijsredenen: list[str] = []
    waarschuwingen: list[str] = []
    if identity == "mismatch":
        afwijsredenen.append("verkeerde organisatie")
    if not document.url.startswith(("http://", "https://")):
        afwijsredenen.append("ongeldige of niet-herleidbare URL")
    if (
        document.gevraagd_jaar is not None
        and document.verslagjaar is not None
        and document.gevraagd_jaar != document.verslagjaar
    ):
        if _duo_jaar_is_aanvaardbaar_ouder(document):
            # DUO meet op 1 oktober en publiceert met vertraging, dus voor het
            # lopende peiljaar bestaat er per definitie nog niets. De harde
            # afwijzing liet zo'n bron helemaal niet op de kaart komen, terwijl
            # het cijfer wel beoordeelbaar is. Het jaartal staat op de kaart, dus
            # de reviewer ziet waar hij naar kijkt.
            waarschuwingen.append("duo_jaar_achter")
        else:
            afwijsredenen.append("verkeerd verslagjaar")
    if document.eenheid == "fte":
        waarschuwingen.append("fte_geen_wp")
    if document.documenttype == "duo_personeel_personen":
        waarschuwingen.append("duo_definitie_wijkt_af_van_wp")
    if document.brontype == "media" and document.publicatiedatum:
        waarschuwingen.append("recent_actualiteitssignaal")
    if document.scope_class in {"nederland", "concern"}:
        waarschuwingen.append("scope_breder_dan_vestiging")
    if not document.bewijsfragment and document.wp_gevonden is not None:
        waarschuwingen.append("getal_zonder_bewijsfragment")
    if (document.raw_data or {}).get("wp_afgeleid_uit_naamlijst"):
        waarschuwingen.append("wp_afgeleid_uit_naamlijst")

    validaties = {
        **(
            {
                WP_EXTRACTIE: (
                    WP_GEVONDEN if document.wp_gevonden is not None
                    else WP_GEZOCHT_NIETS_GEVONDEN
                ),
            }
            if document.wp_extractie_gedaan else {}
        ),
        "domein_match": domein_match,
        "verslagjaar_match": (
            document.gevraagd_jaar == document.verslagjaar
            if document.gevraagd_jaar is not None and document.verslagjaar is not None
            else None
        ),
        "publicatie_in_n_plus_1": (
            document.publicatiedatum.year == document.verslagjaar + 1
            if document.publicatiedatum and document.verslagjaar is not None
            else None
        ),
        "heeft_bewijsfragment": bool(document.bewijsfragment),
        "heeft_wp": document.wp_gevonden is not None,
        "eenheid_is_wp": document.eenheid == "werkzame_personen",
        "scope_is_bruikbaar": document.scope_class in {"vestiging", "limburg"},
    }
    return draag_naamlijsttelling_over_aan_reviewer(BronValidatie(
        document=document,
        identity_class=identity,
        is_officieel=is_officieel,
        is_afgewezen=bool(afwijsredenen),
        afwijsredenen=afwijsredenen,
        validaties=validaties,
        waarschuwingen=waarschuwingen,
    ))
