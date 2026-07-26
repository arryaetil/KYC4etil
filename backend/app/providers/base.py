"""Provider-interfaces (documentatie §5). Live én mock implementeren deze,
zodat de pipeline geen idee heeft welke modus draait."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class PlacesResult:
    website: str | None = None
    phone: str | None = None
    adres: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class LocationInfo:
    count_nl: int | None
    count_lb: int | None
    bron: str  # 'kvk' | 'places' | 'mock'


@dataclass
class AgentFinding:
    wp_gevonden: int | None
    context: str | None
    zekerheid: str          # hoog|middel|laag
    reden: str | None
    bron_url: str | None
    bron_type: str          # website|jaarverslag|media
    is_totaal_meerdere_vestigingen: bool = False
    is_limburg_specifiek: bool | None = None
    is_fte: bool = False
    peilmoment: str | None = None
    raw: dict = field(default_factory=dict)
    eigen_personeel: int | None = None
    uitzend: int | None = None
    detachering: int | None = None
    wsw: int | None = None
    man: int | None = None
    vrouw: int | None = None
    voltijd: int | None = None
    deeltijd: int | None = None
    pct_op_locatie: float | None = None
    bron_pagina: int | None = None  # 1-indexed PDF-paginanummer waar context vandaan komt
    identity_class: str | None = None  # gevuld door IdentityScopeClassifier, zie pipeline/identity_scope.py
    scope_class: str | None = None


class LookupProvider(Protocol):
    async def lookup(self, naam: str, gemeente: str | None) -> PlacesResult | None: ...
    async def locations(self, naam: str, kvk_nummer: str | None) -> LocationInfo: ...
    async def scrape_email(self, website_url: str | None) -> str | None: ...


class WebsiteAgent(Protocol):
    async def run(self, naam: str, adres: str | None, website_url: str | None,
                  gemeente: str | None = None) -> AgentFinding | None: ...
    async def extra_bronnen(self, naam: str, gemeente: str | None,
                            uitsluiten: set[str] | None = None) -> list[AgentFinding]: ...


class JaarverslagAgent(Protocol):
    async def run(
        self,
        naam: str,
        jaar: int,
        website_url: str | None = None,
        strict_identity: bool = False,
    ) -> AgentFinding | None: ...
    async def validate_source(
        self,
        naam: str,
        jaar: int,
        bron_url: str,
        website_url: str | None = None,
        strict_identity: bool = False,
    ) -> bool: ...


class IdentityScopeClassifier(Protocol):
    async def classify(
        self, naam: str, adres: str | None, gemeente: str | None,
        website_url: str | None, finding: AgentFinding | None,
    ) -> tuple[str, str]:
        """Retourneert (identity_class, scope_class) als string-waarden
        (zie pipeline/evidence.py voor de toegestane enum-waarden)."""
        ...
