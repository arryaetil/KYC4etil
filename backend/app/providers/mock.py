"""Mock-providers: deterministische antwoorden voor de 20 testbedrijven.
Onbekende bedrijven leveren een mislukte lookup op (-> chat/bellijst-strategie)."""
import json
from pathlib import Path

from .base import AgentFinding, LocationInfo, PlacesResult

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "mock_data.json"


def _load() -> dict:
    with open(DATA_PATH, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


class MockLookupProvider:
    def __init__(self):
        self.data = _load()

    async def lookup(self, naam: str, gemeente: str | None) -> PlacesResult | None:
        entry = self.data.get(naam)
        if not entry:
            return None
        p = entry["places"]
        return PlacesResult(website=p.get("website"), phone=p.get("phone"),
                            adres="match" if p.get("adres_match") else "geen match",
                            raw={"adres_match": p.get("adres_match", False)})

    async def locations(self, naam: str, kvk_nummer: str | None) -> LocationInfo:
        entry = self.data.get(naam)
        if not entry:
            return LocationInfo(count_nl=None, count_lb=None, bron="mock")
        loc = entry["locaties"]
        return LocationInfo(count_nl=loc["nl"], count_lb=loc["lb"], bron="mock")

    async def scrape_email(self, website_url: str | None) -> str | None:
        return None


class MockWebsiteAgent:
    def __init__(self):
        self.data = _load()

    async def run(self, naam: str, adres: str | None, website_url: str | None,
                  gemeente: str | None = None) -> AgentFinding | None:
        entry = self.data.get(naam, {})
        # Nieuws-fallback (bron_type 'media') als website niets oplevert
        finding = entry.get("website") or entry.get("media")
        if not finding:
            return None
        bron_type = "media" if "media" in entry and "website" not in entry else "website"
        return AgentFinding(
            wp_gevonden=finding["wp"], context=finding["context"],
            zekerheid=finding["zekerheid"], reden="mock",
            bron_url=finding["url"], bron_type=bron_type,
            is_totaal_meerdere_vestigingen=finding.get("totaal_meerdere_vestigingen", False),
            is_limburg_specifiek=finding.get("limburg_specifiek", True),
            peilmoment=finding.get("peilmoment"),
        )


class MockJaarverslagAgent:
    def __init__(self):
        self.data = _load()

    async def run(self, naam: str, jaar: int) -> AgentFinding | None:
        finding = self.data.get(naam, {}).get("jaarverslag")
        if not finding:
            return None
        return AgentFinding(
            wp_gevonden=finding["wp"], context=finding["context"],
            zekerheid=finding["zekerheid"], reden="mock",
            bron_url=finding["url"], bron_type="jaarverslag",
            is_limburg_specifiek=finding.get("limburg_specifiek", False),
            is_fte=finding.get("is_fte", False),
            peilmoment=finding.get("peilmoment"),
        )
