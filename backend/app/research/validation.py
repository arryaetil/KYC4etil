"""Goedkope, deterministische bronvalidatie vóór semantische verdieping."""
from dataclasses import dataclass, field
from datetime import date

from ..pipeline.identity_scope import (
    domain_matches_company,
    heuristic_identity_class,
)


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
    return BronValidatie(
        document=document,
        identity_class=identity,
        is_officieel=is_officieel,
        is_afgewezen=bool(afwijsredenen),
        afwijsredenen=afwijsredenen,
        validaties=validaties,
        waarschuwingen=waarschuwingen,
    )
