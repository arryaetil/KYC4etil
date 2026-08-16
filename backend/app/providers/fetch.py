"""HTTP-laag: pagina's, PDF's en URL-normalisatie.

Alles wat het net op gaat om ruwe tekst op te halen staat hier; de interpretatie
van die tekst hoort in de agent-modules. Web scraping respecteert robots.txt,
gebruikt een identificerende user-agent en max 1 request/sec per domein (doc §7)."""
import asyncio
import logging
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


# Crawl4AI draait op een echte browser. Eén gedeelde instantie per proces is
# fors goedkoper dan een browser per pagina, en de semafoor voorkomt dat het
# parallelle inspecteren in de supervisor (tot research_max_pages pagina's in
# één asyncio.gather) evenveel Chromium-instanties tegelijk openzet.
_crawler = None
_crawler_lock: asyncio.Lock | None = None
_crawler_semafoor: asyncio.Semaphore | None = None
# Onder deze lengte gaan we ervan uit dat het renderen niets bruikbaars opleverde
# en valt de platte HTTP-tekst terug in beeld.
_MIN_MARKDOWN_TEKST = 200


def _crawler_primitieven() -> tuple[asyncio.Lock, asyncio.Semaphore]:
    """Lui aanmaken: asyncio-primitieven horen bij de draaiende event loop, en
    die bestaat bij import nog niet."""
    global _crawler_lock, _crawler_semafoor
    if _crawler_lock is None:
        _crawler_lock = asyncio.Lock()
    if _crawler_semafoor is None:
        _crawler_semafoor = asyncio.Semaphore(settings.crawl4ai_max_parallel)
    return _crawler_lock, _crawler_semafoor


async def _gedeelde_crawler():
    global _crawler
    lock, _ = _crawler_primitieven()
    if _crawler is None:
        async with lock:
            if _crawler is None:
                from crawl4ai import AsyncWebCrawler, BrowserConfig

                crawler = AsyncWebCrawler(
                    config=BrowserConfig(headless=True, user_agent=USER_AGENT),
                )
                await crawler.start()
                _crawler = crawler
    return _crawler


async def sluit_crawler() -> None:
    """Sluit de gedeelde browser af. Aangeroepen bij shutdown en in tests;
    een volgende aanroep start hem vanzelf opnieuw."""
    global _crawler
    if _crawler is None:
        return
    crawler, _crawler = _crawler, None
    try:
        await crawler.close()
    except Exception:
        pass


async def _haal_pagina_op_crawl4ai(url: str) -> dict:
    """Rendert de pagina met een echte browser (Crawl4AI, op Playwright) en levert
    schone, ruisvrije markdown + links terug — same-domein, net als de platte
    HTTP-poging. Crawl4AI's PruningContentFilter verwijdert boilerplate (herhaalde
    navigatie, sidebars) al vóórdat de tekst bij de extractie-LLM komt, en de
    markdown behoudt koppen, lijsten en tabellen die soup.get_text() platslaat.

    Gebruikt één gedeelde browser (zie _gedeelde_crawler) in plaats van er per
    pagina een op te starten."""
    from urllib.parse import urlparse

    from crawl4ai import CacheMode, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    run_conf = CrawlerRunConfig(
        # Monitoring moet wijzigingen kunnen zien; een cache zou een nieuw
        # jaarverslag kunnen maskeren. Daarom bewust geen hergebruik.
        cache_mode=CacheMode.BYPASS,
        # Expliciet op 1 (= de library-default) vastgezet: elk blok telt mee.
        # Een teamkaart ("Thera Hurkmans — wijkverpleegkundige") is vier
        # woorden, dus elke drempel hierboven filtert precies de namenlijsten
        # weg waar we op tellen.
        word_count_threshold=1,
        # GEEN excluded_tags. Ze leken onschuldig (navigatie eruit scheelt
        # tokens), maar ze halveren de linkoogst: op vier gemeten pagina's
        # vielen de interne links van 34 naar 2 (pergamijn), 30 naar 2
        # (fysiosittard) en 21 naar 2 (l1). De documentroute vindt
        # jaarverslagen door <a href="*.pdf"> te oogsten, en sites zetten hun
        # downloads juist vaak in een <aside> of <footer>.
        #
        # GEEN remove_overlay_elements. Dit was de werkelijke oorzaak van de
        # regressie van 15/16 augustus — niet het pruningfilter. Op sites waar
        # de pagina-inhoud in een element staat dat de heuristiek als overlay
        # ziet, verwijdert hij de héle pagina: mondriaan.eu ging van 11.273
        # naar 1 teken, fysiosittard van 9.774 naar 12.
        exclude_external_links=False,
        # Laadt lazy-loaded teamlijsten volledig ("toon meer", infinite scroll)
        # in plaats van alleen het eerste scherm. Aantoonbare winst: hallux
        # 27.481 → 41.232 tekens, l1 6.422 → 15.033.
        scan_full_page=True,
        # domcontentloaded, niet networkidle: sites met analytics-pings of een
        # chatwidget worden nooit stil. pergamijn.org liep daardoor structureel
        # in de timeout — totaal verlies in plaats van een tragere pagina.
        wait_until="domcontentloaded",
        # Krapper dan de default (60s): met research_max_pages=15 en drie
        # renders tegelijk zijn dat vijf golven. Bij 60s zou één trage site de
        # research_company_timeout_seconds (300s) alleen al met renderen
        # kunnen opmaken.
        page_timeout=30000,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                # Library-default (0.48 fixed). Bij parameter-isolatie bleek
                # het filter juist het onschuldigste onderdeel: het snijdt naar
                # 50-83% van de ruwe markdown en heeft op geen enkele geteste
                # pagina inhoud vernietigd. De losser gezette 0.30/dynamic
                # leverde geen meetbaar betere namenlijsten op en maakte het
                # gedrag alleen minder voorspelbaar per paginatype.
                # min_word_threshold blijft None (library-default): elke
                # drempel daar snijdt teamkaarten van een paar woorden weg.
                threshold=0.48,
                threshold_type="fixed",
            ),
        ),
    )
    _, semafoor = _crawler_primitieven()
    crawler = await _gedeelde_crawler()
    async with semafoor:
        result = await crawler.arun(url=url, config=run_conf)

    tekst = ""
    if result.markdown:
        tekst = result.markdown.fit_markdown or result.markdown.raw_markdown or ""

    eigen_domein = urlparse(url).netloc
    links: list[dict] = []
    seen: set[str] = set()
    alle_links = (
        list((result.links or {}).get("internal", []))
        + list((result.links or {}).get("external", []))
    )
    for link in alle_links:
        href = link.get("href")
        if not href or href in seen:
            continue
        if not _is_bruikbare_link(href, eigen_domein):
            continue
        seen.add(href)
        links.append({"tekst": link.get("text") or "", "url": href})

    return {"tekst": tekst, "links": links}


def _is_bruikbare_link(href: str, eigen_domein: str) -> bool:
    """Same-domein links, plus PDF's waar ze ook staan.

    Alleen same-domein toelaten kost precies de bronnen waar de documentroute
    op draait: veel organisaties hosten hun jaarverslag op een CDN of een apart
    rapportagedomein (jumborapportage.com, *.cloudfront.net). Die link staat
    dan wél op de eigen site maar wijst naar buiten.
    """
    from urllib.parse import urlparse

    if urlparse(href).netloc == eigen_domein:
        return True
    return href.lower().split("?")[0].endswith(".pdf")


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
        if not _is_bruikbare_link(absolute, eigen_domein):
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

    if not settings.playwright_enabled:
        return pagina
    if not (settings.crawl4ai_altijd or len(pagina["tekst"]) < 500):
        return pagina
    try:
        rendered = await _haal_pagina_op_crawl4ai(url)
    except Exception as exc:
        # Stil terugvallen zou betekenen dat altijd-aan uit staat zonder dat
        # iemand het merkt — bijvoorbeeld bij een config-parameter die deze
        # crawl4ai-versie niet kent, of een ontbrekende Chromium.
        logging.getLogger("crawl4ai").warning(
            "Renderen mislukt voor %s (%s: %s); platte HTTP-tekst gebruikt",
            url, type(exc).__name__, exc,
        )
        return pagina

    if settings.crawl4ai_altijd:
        # Markdown mág korter zijn dan de platte tekst — dat is juist de winst:
        # PruningContentFilter haalt navigatie en boilerplate eruit vóórdat de
        # tekst tokens kost. Alleen terugvallen als er niets over blijft.
        return rendered if len(rendered["tekst"]) >= _MIN_MARKDOWN_TEKST else pagina
    # Fallbackmodus: renderen moest juist méér tekst opleveren dan platte HTTP.
    return rendered if len(rendered["tekst"]) > len(pagina["tekst"]) else pagina
