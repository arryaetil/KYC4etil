"""URL-normalisatie voor deduplicatie zonder broninformatie kwijt te raken."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_TRACKING_PARAMETERS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source",
}


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
    return urlunsplit((
        scheme,
        parts.netloc.lower().removeprefix("www."),
        path,
        query,
        "",
    ))
