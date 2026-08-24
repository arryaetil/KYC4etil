"""Contactgegevens en locatietelling.

Serper Places gaat voor op Google Places (20-32x duurder); levert geen van beide
een bruikbare site op, dan volgt een zoekfallback. De landelijke locatietelling
blijft op Google Places aangewezen totdat de KvK-koppeling er is (doc §3)."""
import re
from urllib.parse import quote, urlparse

import httpx

from ..config import get_settings
from ..research.usage import record_provider_call
from .dienststatus import meld_storing
from . import fetch, search
from .base import LocationInfo, PlacesResult
from .naam_matching import _naam_tokens, _tekst_lijkt_bij_bedrijf_te_horen

settings = get_settings()

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places"


def _is_directory_result(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    blocked = (
        "google.", "facebook.", "linkedin.", "instagram.", "x.com",
        "twitter.", "yelp.", "tripadvisor.", "drimble.", "oozo.",
        "bedrijvenpagina.", "openingstijden.", "telefoonboek.",
    )
    return any(part in host for part in blocked)


async def _web_search_contact(naam: str, gemeente: str | None) -> PlacesResult | None:
    query_texts = [
        f"{naam} {gemeente or ''} officiele website telefoon contact".strip(),
    ]
    if gemeente:
        query_texts.append(f'"{naam}" officiele website contact')

    geziene_urls: set[str] = set()
    for query_text in query_texts:
        results = await search._web_search(query_text, max_results=6)
        for result in results:
            url = result["url"]
            if url in geziene_urls or _is_directory_result(url):
                continue
            geziene_urls.add(url)
            phone = None
            tekst = ""
            try:
                tekst = await fetch._fetch_text(url)
                phone_match = re.search(
                    r"(?:\+31|0)\s?(?:\d[\s\-().]?){8,12}",
                    tekst,
                )
                phone = phone_match.group(0).strip() if phone_match else None
            except Exception:
                pass
            bron_context = " ".join(filter(None, [
                result.get("title"),
                result.get("snippet"),
                tekst[:10000],
            ]))
            if not _tekst_lijkt_bij_bedrijf_te_horen(naam, bron_context):
                continue
            naam_tokens = _naam_tokens(naam)
            host_labels = [
                label for label in urlparse(url).netloc.lower().split(".")
                if label not in {"www", "nl", "com", "eu", "org", "net"}
            ]
            exact_uniek_merkdomein = (
                len(naam_tokens) == 1
                and naam_tokens[0] in host_labels
            )
            if (
                gemeente
                and gemeente.lower() not in bron_context.lower()
                and len(naam_tokens) <= 1
                and not exact_uniek_merkdomein
            ):
                # Bij een ambigue éénwoordnaam zonder exact merkdomein
                # voorkomt de gemeentecheck dat een naamgenoot als officiële
                # site wordt opgeslagen. Een exact domein als okechamp.eu
                # blijft bruikbaar bij verouderde regiogegevens.
                continue
            return PlacesResult(
                website=url,
                phone=phone,
                adres=None,
                raw={
                    "bron": result.get("bron", "web_search"),
                    "query_result": result,
                    "query": query_text,
                },
            )
    return None


async def _openai_contact_fallback(
    naam: str,
    gemeente: str | None,
) -> PlacesResult | None:
    results = await search._openai_web_search(
        f'"{naam}" {gemeente or ""} officiële website contact'.strip(),
        max_results=6,
    )
    for result in results:
        url = result["url"]
        if _is_directory_result(url) or ".pdf" in urlparse(url).path.lower():
            continue
        context = " ".join(filter(None, [
            result.get("title"),
            result.get("snippet"),
            url,
        ]))
        if not _tekst_lijkt_bij_bedrijf_te_horen(naam, context):
            continue
        return PlacesResult(
            website=url,
            phone=None,
            adres=None,
            raw={"bron": "openai_web_search", "query_result": result},
        )
    return None


async def _contact_fallback(
    naam: str,
    gemeente: str | None,
) -> PlacesResult | None:
    return (
        await _web_search_contact(naam, gemeente)
        or await _openai_contact_fallback(naam, gemeente)
    )


class LivePlacesProvider:
    async def lookup(self, naam: str, gemeente: str | None) -> PlacesResult | None:
        place = await search._serper_places(f"{naam} {gemeente or ''}".strip())
        if place and place.get("website"):
            return PlacesResult(
                website=place.get("website"),
                phone=place.get("phoneNumber"),
                adres=place.get("address"),
                raw={"bron": "serper_places", **place},
            )
        if not settings.google_places_api_key:
            return await _contact_fallback(naam, gemeente)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                zoekrespons = await client.post(
                    PLACES_SEARCH_URL,
                    headers={
                        "X-Goog-Api-Key": settings.google_places_api_key,
                        # IDs-only is gratis; de gerangschikte eerste match
                        # blijft gelijk aan de oude Enterprise Text Search.
                        "X-Goog-FieldMask": "places.id",
                    },
                    json={"textQuery": f"{naam} {gemeente or ''}".strip(), "languageCode": "nl"},
                )
                zoekrespons.raise_for_status()
                record_provider_call("google_places_text_search_ids_only")
                gevonden = zoekrespons.json().get("places") or []
                place_id = gevonden[0].get("id") if gevonden else None
                if not place_id:
                    return await _contact_fallback(naam, gemeente)
                detailrespons = await client.get(
                    f"{PLACES_DETAILS_URL}/{quote(place_id, safe='')}",
                    headers={
                        "X-Goog-Api-Key": settings.google_places_api_key,
                        "X-Goog-FieldMask": (
                            "websiteUri,nationalPhoneNumber,formattedAddress"
                        ),
                    },
                    params={"languageCode": "nl"},
                )
                detailrespons.raise_for_status()
                record_provider_call(
                    "google_places_details_enterprise",
                    kosten_micro_usd=20_000,
                )
                p = detailrespons.json()
        except httpx.HTTPError as fout:
            # Viel stil terug op de contactfallback, dus een leeg tegoed zag er
            # precies zo uit als een bedrijf dat Google niet kent.
            meld_storing("google_places", fout)
            return await _contact_fallback(naam, gemeente)
        if not p.get("websiteUri"):
            return await _contact_fallback(naam, gemeente)
        return PlacesResult(website=p.get("websiteUri"), phone=p.get("nationalPhoneNumber"),
                            adres=p.get("formattedAddress"),
                            raw={"bron": "google_places_details", **p})

    async def scrape_email(self, website_url: str | None) -> str | None:
        if not website_url:
            return None
        try:
            return await fetch._scrape_email(website_url)
        except Exception:
            return None

    async def locations(self, naam: str, kvk_nummer: str | None) -> LocationInfo:
        if not settings.google_places_api_key:
            return LocationInfo(count_nl=None, count_lb=None, bron="web_search")
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    PLACES_SEARCH_URL,
                    headers={
                        "X-Goog-Api-Key": settings.google_places_api_key,
                        "X-Goog-FieldMask": "places.formattedAddress",
                    },
                    json={"textQuery": f"{naam} Nederland", "languageCode": "nl",
                          "pageSize": settings.places_max_resultaten},
                )
                r.raise_for_status()
                places = r.json().get("places") or []
                record_provider_call(
                    "google_places_text_search", kosten_micro_usd=32_000,
                )
        except httpx.HTTPError as fout:
            meld_storing("google_places", fout)
            return LocationInfo(count_nl=None, count_lb=None, bron="web_search")
        lb = sum(1 for p in places if "Limburg" in (p.get("formattedAddress") or ""))
        return LocationInfo(
            count_nl=len(places) or None, count_lb=lb, bron="places",
            # Places pagineert hier niet: precies de limiet betekent "minstens
            # zoveel", niet "exact zoveel".
            count_nl_is_ondergrens=len(places) >= settings.places_max_resultaten,
        )
