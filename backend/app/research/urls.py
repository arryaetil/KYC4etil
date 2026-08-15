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
