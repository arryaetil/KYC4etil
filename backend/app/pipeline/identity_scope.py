"""Cheap, deterministische identiteits-/scope-heuristieken (doc: bronnen-first
UI-project). Dienen als eerste, gratis check vóór een eventuele LLM-classificatie
(zie providers/live.py::LiveIdentityScopeClassifier) — en als volledige,
deterministische mock-classificatie in testmodus."""
import re
import unicodedata
from urllib.parse import urlparse

from .evidence import IdentityClass, ScopeClass

_STOPWOORDEN = {
    "bv", "b", "v", "nv", "n", "stichting", "groep", "holding", "the",
    "de", "het", "en", "van", "der", "den", "te", "in", "op", "aan",
    "filiaal", "koninklijke",
}


def _naam_tokens(naam: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", naam).encode("ascii", "ignore").decode("ascii")
    tokens = re.findall(r"[a-z0-9]+", normalized.lower())
    return [token for token in tokens if len(token) >= 3 and token not in _STOPWOORDEN]


def _normalize_domain(url: str | None) -> str | None:
    if not url:
        return None
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc or None


def domain_matches_company(bron_url: str | None, website_url: str | None) -> bool | None:
    """True/False als beide domeinen bekend zijn, anders None (onbeslisbaar)."""
    bron_domein = _normalize_domain(bron_url)
    company_domein = _normalize_domain(website_url)
    if not bron_domein or not company_domein:
        return None
    return bron_domein == company_domein


def heuristic_identity_class(
    naam: str, context: str | None, bron_url: str | None, website_url: str | None,
) -> str:
    """Gratis eerste-check: domeinmatch wint; anders naam-tokenmatch tegen het citaat."""
    if domain_matches_company(bron_url, website_url) is True:
        return IdentityClass.EXACT_ENTITY.value

    tokens = _naam_tokens(naam)
    if not tokens or not context:
        return IdentityClass.UNKNOWN.value

    normalized = unicodedata.normalize("NFKD", context).encode("ascii", "ignore").decode("ascii").lower()
    matches = sum(1 for token in tokens if re.search(rf"\b{re.escape(token)}\b", normalized))
    minimum = 1 if len(tokens) == 1 else min(2, len(tokens))
    if matches >= minimum:
        return IdentityClass.EXACT_ENTITY.value
    if matches >= 1:
        return IdentityClass.SAME_BRAND_OR_GROUP.value
    return IdentityClass.MISMATCH.value


def heuristic_scope_class(is_limburg_specifiek: bool | None, bron_type: str | None) -> str:
    """Zelfde conservatieve afleiding als evidence.py::_scope_from_finding, maar
    los aanroepbaar met alleen de twee benodigde velden (geen AgentFinding nodig)."""
    if is_limburg_specifiek is True:
        return ScopeClass.VESTIGING.value if bron_type == "website" else ScopeClass.LIMBURG.value
    if is_limburg_specifiek is False:
        return ScopeClass.NEDERLAND.value
    return ScopeClass.UNKNOWN.value
