"""Zoekindexen: DuckDuckGo, Serper en OpenAI's hosted web_search.

De ketting is bewust getrapt op kosten: Serper ($1/1000) en DuckDuckGo (gratis)
lopen parallel, de veel duurdere hosted search van OpenAI ($10/1000) is alleen
een laatste redmiddel. Valt Serper uit, dan wordt dat luid gelogd — zie
_log_zoekprovider_fout."""
import asyncio
import logging
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from ..config import get_settings
from ..research.usage import record_provider_call
from . import llm

logger = logging.getLogger(__name__)

settings = get_settings()

# Statuscodes waarbij de sleutel of het tegoed het probleem is, niet de zoekopdracht.
# Die moeten luid zijn: zonder Serper valt de zoekketen terug op DuckDuckGo-scraping
# (zwakkere index, meer gemiste jaarverslagen) en Google Places (32x duurder).
#
# 400 hoort er nadrukkelijk bij: Serper meldt een leeg tegoed met
# {"message":"Not enough credits","statusCode":400} en niet met 401/402/403.
# Een guard op statuscodes alléén mist daarom precies het geval waarvoor hij bedoeld
# is; de body is hier de betrouwbaardere bron.
_SLEUTEL_OF_TEGOED_STATUS = {400, 401, 402, 403, 429}
_TEGOED_MARKERS = ("credit", "quota", "insufficient", "limit exceeded")


def _log_zoekprovider_fout(provider: str, fout: Exception) -> None:
    respons = getattr(fout, "response", None)
    status = getattr(respons, "status_code", None)
    body = ""
    if respons is not None:
        try:
            body = respons.text[:200]
        except Exception:
            body = ""
    tegoed_op = any(m in body.lower() for m in _TEGOED_MARKERS)
    if tegoed_op or status in _SLEUTEL_OF_TEGOED_STATUS:
        logger.warning(
            "%s onbruikbaar (HTTP %s): %s. De zoekketen valt nu terug op DuckDuckGo "
            "en de duurdere OpenAI-websearch — zwakkere resultaten en hogere kosten. "
            "Antwoord: %s", provider, status,
            "tegoed op" if tegoed_op else "sleutel ongeldig of tegoed op",
            body or "(geen body)",
        )
    else:
        logger.info("%s gaf geen resultaat (%s)", provider, fout)


def _normaliseer_duckduckgo_url(href: str) -> str:
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [None])[0]
        return unquote(target) if target else href
    return href


async def _serper_places(query: str) -> dict | None:
    """Lokale Google Maps-achtige resultaten voor contactgegevens — veel
    goedkoper dan Google Places Text Search ($1/1000 i.p.v. $32-35/1000).
    NB: dit endpoint geeft alleen resultaten bij een plaatsnaam in de query
    en is daarom ONGESCHIKT voor de landelijke locatie-telling in
    LivePlacesProvider.locations() (doc §7); daar blijft Google Places nodig
    totdat de KvK-koppeling er is."""
    if not settings.serper_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                "https://google.serper.dev/places",
                headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                json={"q": query, "gl": "nl", "hl": "nl", "num": 1},
            )
            r.raise_for_status()
            places = r.json().get("places") or []
    except httpx.HTTPError as fout:
        _log_zoekprovider_fout("serper_places", fout)
        return None
    record_provider_call("serper_places", kosten_micro_usd=1_000)
    return places[0] if places else None


async def _duckduckgo_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Zoek publieke bronnen via DuckDuckGo HTML en parse resultaten met BeautifulSoup."""
    from bs4 import BeautifulSoup

    from .fetch import DUCKDUCKGO_USER_AGENT

    record_provider_call("duckduckgo_search")
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                     headers={"User-Agent": DUCKDUCKGO_USER_AGENT}) as client:
            response = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": "nl-nl"},
            )
            response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(".result"):
        link = item.select_one("a.result__a")
        if not link or not link.get("href"):
            continue
        url = _normaliseer_duckduckgo_url(link["href"])
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        snippet = item.select_one(".result__snippet")
        results.append({
            "title": link.get_text(" ", strip=True),
            "url": url,
            "snippet": snippet.get_text(" ", strip=True) if snippet else "",
            "bron": "duckduckgo",
        })
        if len(results) >= max_results:
            break
    return results


async def _serper_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Betrouwbare fallback op DuckDuckGo (doc §7): Serper's Google-index is
    stabieler dan het scrapen van een niet-officiele HTML-pagina, en veel
    goedkoper dan OpenAI's ingebouwde web_search-tool."""
    if not settings.serper_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                json={"q": query, "gl": "nl", "hl": "nl", "num": max_results},
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as fout:
        # Pas registreren na een geslaagde call: een mislukte call kost niets en
        # mag de kostenrapportage niet vullen met calls die nooit gelukt zijn.
        _log_zoekprovider_fout("serper_search", fout)
        return []
    record_provider_call("serper_search", kosten_micro_usd=1_000)
    results: list[dict[str, str]] = []
    for item in (data.get("organic") or [])[:max_results]:
        url = item.get("link")
        if not url:
            continue
        results.append({
            "title": item.get("title", ""),
            "url": url,
            "snippet": item.get("snippet", ""),
            "bron": "serper",
        })
    return results


async def _web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Combineer beschikbare zoekindexen en dedupliceer per canonieke URL.

    DuckDuckGo en Serper vullen elkaar aan: een matig DuckDuckGo-resultaat mag
    niet langer verhinderen dat sterkere Google/Serper-resultaten worden gezien.
    Eén falende provider blokkeert de andere niet.
    """
    from ..research.urls import canonicaliseer_url

    provider_results = await asyncio.gather(
        _duckduckgo_search(query, max_results=max_results),
        _serper_search(query, max_results=max_results),
        return_exceptions=True,
    )
    combined: dict[str, dict] = {}
    for results in provider_results:
        if isinstance(results, BaseException):
            continue
        for result in results:
            canonical = canonicaliseer_url(result["url"])
            bestaand = combined.get(canonical)
            bron = result.get("bron", "web_search")
            if bestaand is None:
                combined[canonical] = {
                    **result,
                    "bronnen": [bron],
                    "snippets": [result.get("snippet", "")] if result.get("snippet") else [],
                }
                continue
            if bron not in bestaand["bronnen"]:
                bestaand["bronnen"].append(bron)
            snippet = result.get("snippet", "")
            if snippet and snippet not in bestaand["snippets"]:
                bestaand["snippets"].append(snippet)
            bestaand["bron"] = "+".join(bestaand["bronnen"])
            bestaand["snippet"] = " ".join(bestaand["snippets"])
    return list(combined.values())[:max_results]


async def _openai_web_search(
    query: str,
    max_results: int = 5,
) -> list[dict[str, str]]:
    """Begrensde hosted-searchfallback wanneer beide klassieke indexen leeg zijn."""
    if not settings.openai_api_key:
        return []
    from openai import AsyncOpenAI

    record_provider_call("openai_web_search", kosten_micro_usd=10_000)
    try:
        response = await llm._create_response(
            AsyncOpenAI(api_key=settings.openai_api_key),
            model=settings.openai_web_search_model,
            input=(
                "Zoek de meest relevante primaire en officiële bronnen voor "
                f"deze zoekopdracht. Geef directe bron-URL's: {query}"
            ),
            tools=[{"type": "web_search"}],
            tool_choice="required",
            max_output_tokens=800,
        )
    except Exception:
        return []

    data = response.model_dump()
    gevonden: list[dict[str, str]] = []
    gezien: set[str] = set()

    def voeg_toe(url: str | None, title: str | None) -> None:
        if not url or url in gezien or len(gevonden) >= max_results:
            return
        gezien.add(url)
        gevonden.append({
            "title": title or "",
            "url": url,
            "snippet": "",
            "bron": "openai_web_search",
        })

    for item in data.get("output", []):
        for source in (item.get("action") or {}).get("sources") or []:
            voeg_toe(source.get("url"), source.get("title"))
        for content in item.get("content") or []:
            for annotation in content.get("annotations") or []:
                if annotation.get("type") == "url_citation":
                    voeg_toe(annotation.get("url"), annotation.get("title"))
    return gevonden
