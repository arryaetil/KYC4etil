"""HTTP-laag: pagina's, PDF's en URL-normalisatie.

Alles wat het net op gaat om ruwe tekst op te halen staat hier; de interpretatie
van die tekst hoort in de agent-modules. Web scraping respecteert robots.txt,
gebruikt een identificerende user-agent en max 1 request/sec per domein (doc §7)."""
from urllib.parse import parse_qs, urlparse

import httpx

from ..config import get_settings

settings = get_settings()

USER_AGENT = "EtilVestigingsregisterBot/1.0 (contact: info@etil.nl)"
# DuckDuckGo's HTML-endpoint blokkeert onze eerlijke bot-UA sinds kort met een
# 202-uitdagingspagina zonder resultaten. Alleen voor déze zoekaanvraag een
# browser-achtige UA gebruiken; overal elders (website-scraping) blijft de
# transparante bot-identiteit staan.
DUCKDUCKGO_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Domeinen die nooit de website van de organisatie zelf zijn: bedrijvengidsen,
# vergelijkers en registers. Ze belanden in website_url doordat een zoekresultaat
# als "officiële website" is overgenomen. site:-scoping daarop levert gegarandeerd
# niets op, terwijl de open zoekopdracht dat wél doet.
_GIDS_DOMEINEN = (
    "allebiz.", "companyinfo.", "zorgkiezer.", "belastingadviseur-info.",
    "drimble.", "oozo.", "bedrijvenpagina.", "openingstijden.", "telefoonboek.",
    "eur-lex.europa.eu", "kvk.nl", "opencompanies.", "bedrijvengids.",
)

# Subdomeinen met een eigen functie; een jaarverslag staat op de hoofdsite.
_HULPSUBDOMEINEN = {
    "support", "help", "helpdesk", "werkenbij", "werken-bij", "jobs", "careers",
    "vacatures", "shop", "webshop", "store", "my", "mijn", "portal", "login",
    "nu", "nieuws", "news", "blog", "docs", "api", "cdn", "media", "static",
}

# Meerdelige publieke achtervoegsels waar het registreerbare domein drie labels
# telt in plaats van twee.
_SAMENGESTELDE_TLDS = {"co.uk", "org.uk", "com.au", "co.nz", "com.br"}


def _unwrap_safelink(url: str) -> str:
    parsed = urlparse(url)
    if "safelinks.protection.outlook.com" not in parsed.netloc.lower():
        return url
    target = parse_qs(parsed.query).get("url")
    return target[0] if target else url


def _domein_van_url(website_url: str | None) -> str | None:
    """Het domein voor site:-scoping, of None als scopen zinloos is.

    Valt terug op het registreerbare hoofddomein: een jaarverslag staat op de
    hoofdsite en niet op support./werkenbij./shop.-subdomeinen."""
    if not website_url:
        return None
    host = urlparse(website_url).netloc.lower().split(":")[0].removeprefix("www.")
    if not host:
        return None
    if any(gids in host for gids in _GIDS_DOMEINEN):
        return None
    labels = host.split(".")
    kern = 3 if ".".join(labels[-2:]) in _SAMENGESTELDE_TLDS else 2
    while len(labels) > kern and labels[0] in _HULPSUBDOMEINEN:
        labels = labels[1:]
    return ".".join(labels) or None


def _heeft_landdomein_conflict(
    bron_url: str | None,
    website_url: str | None,
) -> bool:
    bron_host = (urlparse(bron_url or "").hostname or "").lower()
    website_host = (urlparse(website_url or "").hostname or "").lower()
    return website_host.endswith(".nl") and bron_host.endswith(".be")


async def _scrape_email(website_url: str) -> str | None:
    """Zoek e-mailadres op bedrijfswebsite: eerst mailto:-links, dan regex."""
    import re
    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    SKIP = {"example", "test", "noreply", "no-reply", ".png", ".jpg", ".gif"}

    from bs4 import BeautifulSoup

    base = website_url.rstrip("/")
    for path in ("", "/contact", "/contact-us", "/contacteer-ons"):
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                         headers={"User-Agent": USER_AGENT}) as client:
                r = await client.get(base + path)
                r.raise_for_status()
        except Exception:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href: str = a["href"]
            if href.startswith("mailto:"):
                addr = href[7:].split("?")[0].strip().lower()
                if "@" in addr and not any(s in addr for s in SKIP):
                    return addr
        for m in EMAIL_RE.findall(r.text):
            addr = m.lower()
            if not any(s in addr for s in SKIP):
                return addr
    return None


async def _fetch_text(url: str) -> str:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                 headers={"User-Agent": USER_AGENT}) as client:
        r = await client.get(url)
        r.raise_for_status()
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)


async def _eerste_pdf_paginas(pdf_url: str) -> str:
    import fitz  # PyMuPDF

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = await client.get(pdf_url)
        response.raise_for_status()
    doc = fitz.open(stream=response.content, filetype="pdf")
    return "\n".join(
        doc.load_page(index).get_text()
        for index in range(min(5, len(doc)))
    )


async def _haal_pagina_op_crawl4ai(url: str) -> dict:
    """Rendert de pagina met een echte browser (Crawl4AI, op Playwright) en levert
    schone, ruisvrije markdown + links terug — same-domein, net als de platte
    HTTP-poging. Crawl4AI's PruningContentFilter verwijdert boilerplate (herhaalde
    navigatie, sidebars) al vóórdat de tekst bij de extractie-LLM komt.

    Duurder (echte browser opstarten) dan de platte HTTP-poging, daarom alleen
    ingezet als fallback bij te weinig tekst (JS-zware sites: React/Vue/Angular)."""
    from urllib.parse import urlparse

    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    browser_conf = BrowserConfig(headless=True, user_agent=USER_AGENT)
    run_conf = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(content_filter=PruningContentFilter()),
    )
    async with AsyncWebCrawler(config=browser_conf) as crawler:
        result = await crawler.arun(url=url, config=run_conf)

    tekst = ""
    if result.markdown:
        tekst = result.markdown.fit_markdown or result.markdown.raw_markdown or ""

    eigen_domein = urlparse(url).netloc
    links: list[dict] = []
    seen: set[str] = set()
    for link in (result.links or {}).get("internal", []):
        href = link.get("href")
        if not href or href in seen or urlparse(href).netloc != eigen_domein:
            continue
        seen.add(href)
        links.append({"tekst": link.get("text") or "", "url": href})

    return {"tekst": tekst, "links": links}


def _pagina_data_uit_html(html: str, url: str) -> dict:
    from urllib.parse import urljoin, urlparse

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    eigen_domein = urlparse(url).netloc
    links: list[dict] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        if a.find_parent(["nav", "footer"]) is not None:
            continue
        absolute = urljoin(url, a["href"])
        if urlparse(absolute).netloc != eigen_domein:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append({"tekst": a.get_text(strip=True), "url": absolute})

    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    tekst = soup.get_text(separator="\n", strip=True)
    return {"tekst": tekst, "links": links}


async def _haal_pagina_op(url: str) -> dict:
    """Haalt een pagina op en geeft zowel de opgeschoonde tekst als de links terug
    die het model kan gebruiken om zelf verder te navigeren. Alleen links binnen
    hetzelfde domein worden meegegeven; nav/footer/script/style zijn al verwijderd."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                 headers={"User-Agent": USER_AGENT}) as client:
        r = await client.get(url)
        r.raise_for_status()
        pagina = _pagina_data_uit_html(r.text, url)

    if settings.playwright_enabled and len(pagina["tekst"]) < 500:
        try:
            rendered = await _haal_pagina_op_crawl4ai(url)
            if len(rendered["tekst"]) > len(pagina["tekst"]):
                return rendered
        except Exception:
            pass
    return pagina
