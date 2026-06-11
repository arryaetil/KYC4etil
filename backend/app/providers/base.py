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


class LookupProvider(Protocol):
    async def lookup(self, naam: str, gemeente: str | None) -> PlacesResult | None: ...
    async def locations(self, naam: str, kvk_nummer: str | None) -> LocationInfo: ...


class WebsiteAgent(Protocol):
    async def run(self, naam: str, adres: str | None, website_url: str | None) -> AgentFinding | None: ...


class JaarverslagAgent(Protocol):
    async def run(self, naam: str, jaar: int) -> AgentFinding | None: ...
