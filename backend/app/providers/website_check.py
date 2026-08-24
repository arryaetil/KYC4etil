"""Controleert of een aangeleverde website-URL nog naar de organisatie leidt."""
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from .live import USER_AGENT

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebsiteControle:
    """Uitkomst van één controle, met de reden erbij voor de diagnostiek."""

    bruikbaar: bool
    url: str | None
    reden: str


def _domein(url: str | None) -> str:
    return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")


async def controleer_website(url: str | None) -> WebsiteControle:
    """Leeft deze URL nog, en staat er nog hetzelfde domein?

    Drie uitkomsten die er in de praktijk toe doen:

    - De site antwoordt normaal → bruikbaar, met de URL na redirects. Een
      redirect binnen hetzelfde domein (http→https, /nl/) is geen verhuizing.
    - De site stuurt door naar een ánder domein → bruikbaar, maar met het
      nieuwe adres. Zo wordt een naams- of overnamewijziging vanzelf gevolgd.
    - Fout of foutstatus → niet bruikbaar; de aanroeper zoekt een nieuw adres.

    Bewust geen inhoudelijke controle op geparkeerde domeinen: "te koop"-pagina's
    antwoorden met 200 en zijn niet betrouwbaar aan tekst te herkennen. Die
    komen verderop in de keten alsnog boven water, want er valt geen enkele
    organisatiebron op te vinden.
    """
    if not url:
        return WebsiteControle(False, None, "geen_url")
    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(url)
    except Exception as exc:
        logger.info("websitecontrole mislukt voor %s: %s", url, type(exc).__name__)
        return WebsiteControle(False, None, f"onbereikbaar:{type(exc).__name__}")

    if response.status_code >= 400:
        return WebsiteControle(False, None, f"status:{response.status_code}")

    eind_url = str(response.url)
    if _domein(eind_url) != _domein(url):
        return WebsiteControle(True, eind_url, "verhuisd")
    return WebsiteControle(True, eind_url, "bereikbaar")
