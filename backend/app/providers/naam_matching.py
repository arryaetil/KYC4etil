"""Naamvergelijking tegen cross-company hits.

Een generieke zoekopdracht vindt regelmatig een bron van een ander bedrijf met
een gelijkende naam. Deze helpers bepalen of een gevonden tekst plausibel over
de gevraagde organisatie gaat — bewust conservatief, want een verkeerde bron is
de duurste foutklasse in de pipeline."""
import re
import unicodedata


def _naam_tokens(naam: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", naam).encode("ascii", "ignore").decode("ascii")
    tokens = re.findall(r"[a-z0-9]+", normalized.lower())
    stopwoorden = {
        "bv", "b", "v", "nv", "n", "v", "stichting", "groep", "holding", "the",
        "de", "het", "en", "van", "der", "den", "te", "in", "op", "aan",
        "filiaal", "koninklijke",
    }
    return [token for token in tokens if len(token) >= 3 and token not in stopwoorden]


def _tekst_lijkt_bij_bedrijf_te_horen(naam: str, tekst: str) -> bool:
    """Conservatieve naam-check tegen cross-company hits.

    Een bron hoeft niet exact dezelfde juridische naam te gebruiken, maar bij twee
    of meer betekenisvolle naamdelen moeten er minstens twee terugkomen. Bij een
    eenwoordnaam volstaat dat ene token.
    """
    tokens = _naam_tokens(naam)
    if not tokens:
        return True
    haystack = unicodedata.normalize("NFKD", tekst).encode("ascii", "ignore").decode("ascii").lower()
    matches = sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", haystack))
    minimum = 1 if len(tokens) == 1 else min(2, len(tokens))
    return matches >= minimum


def _is_vacature_of_jobs_url(url: str | None) -> bool:
    if not url:
        return False
    lowered = url.lower()
    markers = (
        "/job", "/jobs", "vacature", "vacatures", "career", "careers",
        "werken-bij", "werkenbij", "recruitment",
    )
    return any(marker in lowered for marker in markers)
