"""Live-providers: Google Places + OpenAI API. Zelfde interfaces als mock.
KvK-provider volgt zodra API-toegang er is (kritieke afhankelijkheid, doc §3).

Dit bestand is sinds de opsplitsing een façade. De implementatie staat in:

- `prompts.py`        alle promptteksten en tool-definities
- `fetch.py`          HTTP, PDF-tekst, scraping en URL-normalisatie
- `search.py`         DuckDuckGo, Serper en OpenAI's hosted web_search
- `llm.py`            OpenAI Responses-calls en JSON-parsing
- `naam_matching.py`  naamvergelijking tegen cross-company hits
- `identity.py`       identiteit- en scopeclassificatie van een bron
- `places.py`         contactgegevens en locatietelling
- `wp_extractie.py`   zoekresultaat → AgentFinding
- `website_agent.py`  de tool-use-loop over de eigen website
- `jaarverslag_zoeken.py`     fase A: een jaarverslag vinden en herkennen
- `jaarverslag_validatie.py`  fase B: klopt de bron, is hij breed en recent
- `jaarverslag.py`            fase C: de agent die A+B regisseert en uitleest

Nieuwe code importeert rechtstreeks uit die modules. De re-exports hieronder
houden bestaande imports werkend; ze zijn géén plek om nieuwe functies aan toe
te voegen.

NB: web scraping respecteert robots.txt, gebruikt een identificerende
user-agent en max 1 request/sec per domein (doc §7)."""
from ..config import get_settings
from ..pipeline.evidence import IdentityClass, ScopeClass
from .base import AgentFinding, LocationInfo, PlacesResult
from .fetch import (
    DUCKDUCKGO_USER_AGENT,
    USER_AGENT,
    _domein_van_url,
    _eerste_pdf_paginas,
    _fetch_text,
    _haal_pagina_op,
    _haal_pagina_op_crawl4ai,
    _heeft_landdomein_conflict,
    _pagina_data_uit_html,
    _scrape_email,
    _unwrap_safelink,
)
from .identity import (
    LiveIdentityScopeClassifier,
    _llm_classify_identity_and_scope,
    _llm_classify_scope,
)
from .jaarverslag import (
    JaarverslagResearchState,
    LiveJaarverslagAgent,
    _baseline_jaarverslag_finding,
    _deterministische_wp_uit_pdf,
    _run_jaarverslag_research_graph,
    _vind_paginanummer,
    _web_search_jaarverslag_wp,
)
from .jaarverslag_validatie import (
    _classificeer_jaarverslag_bron_identiteit,
    _is_organisatiebreed_jaarverslag,
    _pdf_is_recent_jaarverslag,
)
from .jaarverslag_zoeken import (
    _eerste_pdf_uit_resultaten,
    _lijkt_jaarverslag,
    _scrape_pdf_van_pagina,
    _verslagjaar_uit_pdftekst,
    _verslagjaren_uit,
    _zoek_jaarverslag_pdf,
)
from .llm import (
    _create_response,
    _extraction_model,
    _llm_extract,
    _parse_json_met_herstel,
    _pct_op_locatie_fractie,
)
from .naam_matching import (
    _is_vacature_of_jobs_url,
    _naam_tokens,
    _tekst_lijkt_bij_bedrijf_te_horen,
)
from .places import (
    PLACES_SEARCH_URL,
    LivePlacesProvider,
    _contact_fallback,
    _is_directory_result,
    _openai_contact_fallback,
    _web_search_contact,
)
from .prompts import (
    AGENT_PROMPT,
    EXTRACT_PROMPT,
    IDENTITY_EN_SCOPE_PROMPT,
    JAARVERSLAG_SCOPE_PROMPT,
    SCOPE_PROMPT,
    TOOLS,
)
from .search import (
    _duckduckgo_search,
    _log_zoekprovider_fout,
    _normaliseer_duckduckgo_url,
    _openai_web_search,
    _serper_places,
    _serper_search,
    _web_search,
)
from .website_agent import (
    LiveWebsiteAgent,
    WebsiteResearchState,
    _finding_from_website_data,
    _tool_use_loop,
)
from .wp_extractie import (
    _extract_wp_from_search_results,
    _extract_wp_van_zoekresultaten,
    _finding_van_zoekresultaat,
    _web_search_wp,
    verzamel_extra_media_bronnen,
)

settings = get_settings()

__all__ = [
    "ScopeClass",
    "IdentityClass",
    "PlacesResult",
    "LocationInfo",
    "AgentFinding",
    "AGENT_PROMPT",
    "DUCKDUCKGO_USER_AGENT",
    "EXTRACT_PROMPT",
    "IDENTITY_EN_SCOPE_PROMPT",
    "JAARVERSLAG_SCOPE_PROMPT",
    "JaarverslagResearchState",
    "LiveIdentityScopeClassifier",
    "LiveJaarverslagAgent",
    "LivePlacesProvider",
    "LiveWebsiteAgent",
    "PLACES_SEARCH_URL",
    "SCOPE_PROMPT",
    "TOOLS",
    "USER_AGENT",
    "WebsiteResearchState",
    "_baseline_jaarverslag_finding",
    "_run_jaarverslag_research_graph",
    "_classificeer_jaarverslag_bron_identiteit",
    "_contact_fallback",
    "_create_response",
    "_deterministische_wp_uit_pdf",
    "_domein_van_url",
    "_duckduckgo_search",
    "_eerste_pdf_paginas",
    "_eerste_pdf_uit_resultaten",
    "_extract_wp_from_search_results",
    "_extract_wp_van_zoekresultaten",
    "_extraction_model",
    "_fetch_text",
    "_finding_from_website_data",
    "_finding_van_zoekresultaat",
    "_haal_pagina_op",
    "_haal_pagina_op_crawl4ai",
    "_heeft_landdomein_conflict",
    "_is_directory_result",
    "_is_organisatiebreed_jaarverslag",
    "_is_vacature_of_jobs_url",
    "_lijkt_jaarverslag",
    "_llm_classify_identity_and_scope",
    "_llm_classify_scope",
    "_llm_extract",
    "_log_zoekprovider_fout",
    "_naam_tokens",
    "_normaliseer_duckduckgo_url",
    "_openai_contact_fallback",
    "_openai_web_search",
    "_pagina_data_uit_html",
    "_parse_json_met_herstel",
    "_pct_op_locatie_fractie",
    "_pdf_is_recent_jaarverslag",
    "_scrape_email",
    "_scrape_pdf_van_pagina",
    "_serper_places",
    "_serper_search",
    "_tekst_lijkt_bij_bedrijf_te_horen",
    "_tool_use_loop",
    "_unwrap_safelink",
    "_verslagjaar_uit_pdftekst",
    "_verslagjaren_uit",
    "_vind_paginanummer",
    "_web_search",
    "_web_search_contact",
    "_web_search_jaarverslag_wp",
    "_web_search_wp",
    "_zoek_jaarverslag_pdf",
    "settings",
    "verzamel_extra_media_bronnen",
]
