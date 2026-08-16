"""URL-normalisatie voor deduplicatie zonder broninformatie kwijt te raken."""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_PARAMETERS = {
    "fbclid", "gclid", "gclsrc", "dclid", "msclkid", "yclid", "twclid",
    "igshid", "mc_cid", "mc_eid", "ref", "source", "srsltid",
}

# Eén taalvariant van dezelfde pagina is bewijsmatig dezelfde bronroute (zie
# docs/OPENSTAANDE_OBSERVATIES_RESEARCH_EN_UI.md §4): een Engelse en een
# Nederlandse contactpagina van hetzelfde domein leveren geen twee losse
# kandidaten op. Beperkt tot een vaste lijst taalcodes (i.p.v. elk
# tweeletterig padsegment) om een echt landen-/productpad als "/us/..." niet
# per ongeluk als taalvariant te behandelen.
_TAALCODES = {
    "nl", "en", "de", "fr", "es", "it", "pt", "pl", "sv", "da", "no", "fi",
    "cs", "ro", "hu", "el", "tr", "ru", "zh", "ja", "ko", "ar",
}
_TAALPREFIX = re.compile(
    r"^/(" + "|".join(_TAALCODES) + r")(-[a-z]{2})?(?=/|$)"
)


def canonicaliseer_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = (
        "https"
        if parts.scheme.lower() in {"http", "https"}
        else parts.scheme.lower()
    )
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in _TRACKING_PARAMETERS
    ])
    path = parts.path.rstrip("/") or "/"
    path = _TAALPREFIX.sub("", path, count=1) or "/"
    return urlunsplit((
        scheme,
        parts.netloc.lower().removeprefix("www."),
        path,
        query,
        "",
    ))


# Domeinen die per definitie geen primair WP-bewijs kunnen leveren en die nu
# eerst worden opgehaald en door de review-LLM gelezen voordat ze alsnog
# worden afgewezen. Gemeten op 1.095 gelogde afwijzingen in productie is dat
# 27% van alle afwijzingen: Instagram 147, LinkedIn 73, Facebook 68, YouTube
# 11, plus 26 vacaturesites. De bronreview is 72% van de OpenAI-calls per run,
# dus dit is verspilling die vóór het ophalen te voorkomen is.
#
# Bewust géén nieuwsdomeinen hierin: media leverde in de metingen 3 van de
# 5 keer een waarde binnen 10% van de waarheid en is dus een echte bron.
_GEEN_PRIMAIRE_WP_BRON = {
    # sociale profielen — tonen volgersaantallen, geen personeelsbestand
    "linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com",
    "youtube.com", "tiktok.com", "pinterest.com",
    # vacatureplatforms — vacatures zijn geen personeelsomvang
    "indeed.com", "nationalevacaturebank.nl", "monsterboard.nl",
    "werkzoeken.nl", "jobbird.com", "glassdoor.com", "glassdoor.nl",
}


def is_geen_primaire_wp_bron(url: str) -> bool:
    """True als het domein nooit een bruikbaar WP-cijfer kan opleveren.

    Vergelijkt op registreerbaar domein inclusief subdomeinen, zodat
    `nl.linkedin.com` en `be.jobs.jumbo.com`-achtige varianten meetellen.
    """
    domein = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    if not domein:
        return False
    return any(
        domein == geblokkeerd or domein.endswith(f".{geblokkeerd}")
        for geblokkeerd in _GEEN_PRIMAIRE_WP_BRON
    )
