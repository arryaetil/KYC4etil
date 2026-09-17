"""Fase A: een kandidaat-jaarverslag vinden en als jaarverslag herkennen.

De herkenning is bewust streng: deelrapporten (cliëntenraad, raad van toezicht,
VTH) en niet-verslagen (toezichtbrief, transcript) worden geweigerd, en een
aantoonbaar verkeerd verslagjaar ook. De zoekvolgorde loopt van goedkoop naar
duur: site:-scoped op het eigen domein, dan open, dan jaarstukken voor
overheden, en pas als laatste de hosted search van OpenAI."""
import re

import httpx

from . import fetch, search

# verslag uit 2017 werd geaccepteerd omdat het pad "2024" bevatte.
_UPLOADPAD = re.compile(r"/(?:19|20)\d{2}(?:/\d{1,2})?(?=/)")
_JAAR = re.compile(r"(?<!\d)(20\d{2})(?!\d)")


def _verslagjaren_uit(tekst: str) -> set[int]:
    """Jaartallen die iets over het verslagjaar zeggen: uit de titel en de
    bestandsnaam, niet uit tussenliggende padsegmenten."""
    return {int(m) for m in _JAAR.findall(_UPLOADPAD.sub("/", tekst))}


def _lijkt_jaarverslag(
    tekst: str,
    zoekjaar: int,
    *,
    weiger_deelrapporten: bool = True,
) -> bool:
    """Weiger andere PDF-soorten en aantoonbaar verkeerde verslagjaren."""
    lowered = tekst.lower()
    if any(marker in lowered for marker in (
        "toezichtbrief",
        "rechtmatigheidbrief",
        "rechtmatigheidsbrief",
        "privacy statement",
        "privacyverklaring",
        "bezwaarschrift",
        "wederhoortabel",
        "investor day",
        "transcript",
    )):
        return False
    # Normaliseer scheidingstekens: 'VTH-jaarverslag', 'jaarverslag_vth' en
    # 'jaarverslag vth' zijn hetzelfde deelrapport, maar alleen de laatste stond
    # in de lijst.
    genormaliseerd = re.sub(r"[-_]+", " ", lowered)
    if weiger_deelrapporten and any(marker in genormaliseerd for marker in (
        "cliëntenraad",
        "clientenraad",
        "commissie van toezicht",
        "raad en griffie",
        "gouverneur",
        "raad van toezicht",
        "raad van commissarissen",
        "professionele adviesraad",
        "jaarverslag vth",
        "vth jaarverslag",
        "jaarverslagccr",
        "jaarverslagrvt",
    )):
        return False
    markers = (
        "jaarverslag",
        "jaarrekening",
        "bestuursverslag",
        "jaardocument",
        "jaarverantwoording",
        # Gemeenten en provincies publiceren geen "jaarverslag" maar deze:
        "jaarstukken",
        "programmarekening",
        "programmaverantwoording",
        # Hetzelfde document, andere naam op de omslag. Deze lijst bepaalt wat
        # er überhaupt opgehaald wordt, dus een organisatie die haar verslag
        # "jaarbeeld" noemt was onvindbaar — hoe goed de zoekopdracht ook was.
        # Gemeten op de 77 vindplaatsen van 17-09-2026 die de monitoring niet
        # had gevonden: AZL en NLW (jaarbeeld), Veiligheidsregio Zuid-Limburg
        # (jaarbericht), de Belastingdienst (jaarrapportage) en De Rooyse
        # Wissel (jaarmagazine) vielen alle vijf hier af.
        "jaarbeeld",
        "jaarbericht",
        "jaarrapportage",
        "jaarmagazine",
        "annual report",
        "integrated report",
        "integrated annual",
    )
    jaren = _verslagjaren_uit(tekst)
    if jaren and zoekjaar not in jaren:
        return False
    # Tegen de genormaliseerde tekst, net als de deelrapportcheck hierboven:
    # `Annual-Report`, `Annual_Report` en `Annual Report` zijn hetzelfde woord.
    # Voorheen stond alleen "annual-report" er los bij en viel de underscore-
    # schrijfwijze eruit — precies de spelling van SPIE's verslag.
    return any(marker in genormaliseerd for marker in markers)


def _verslagjaar_uit_pdftekst(tekst: str, jaar: int) -> int | None:
    voorblad = re.sub(r"\s+", " ", tekst[:5000].lower())
    documentlabels = (
        "jaarverslag|jaarrekening|bestuursverslag|jaardocument|"
        "jaarverantwoording|annual report|integrated report"
    )
    nabije_jaren = [
        int(match)
        for pattern in (
            rf"(?:{documentlabels})[^0-9]{{0,40}}(20\d{{2}})",
            rf"(20\d{{2}})[^a-z0-9]{{0,20}}(?:{documentlabels})",
        )
        for match in re.findall(pattern, voorblad)
    ]
    toegestane_jaren = {jaar - 1, jaar - 2, jaar - 3}
    for verslagjaar in nabije_jaren:
        if verslagjaar in toegestane_jaren:
            return verslagjaar
    return next((
        verslagjaar
        for verslagjaar in (jaar - 1, jaar - 2, jaar - 3)
        if _lijkt_jaarverslag(
            tekst,
            verslagjaar,
            weiger_deelrapporten=False,
        )
    ), None)


async def _scrape_pdf_van_pagina(pagina_url: str, jaar: int) -> str | None:
    """Haal HTML-pagina op en zoek naar <a href="...pdf..."> links voor het jaarverslag."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True,
                                     headers={"User-Agent": fetch.USER_AGENT}) as client:
            r = await client.get(pagina_url)
            r.raise_for_status()
    except Exception:
        return None

    from urllib.parse import urljoin

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(r.text, "html.parser")
    keywords = [
        "jaarverslag", "annual report", "jaarrapport", "jaarrekening",
        "bestuursverslag", "jaarverantwoording", str(jaar),
    ]

    candidates: list[tuple[int, str]] = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if ".pdf" not in href.lower():
            continue
        link_text = a.get_text(strip=True).lower()
        if not _lijkt_jaarverslag(f"{link_text} {href}", jaar):
            continue
        score = sum(1 for kw in keywords if kw in href.lower() or kw in link_text)
        if score > 0:
            candidates.append((score, urljoin(pagina_url, href)))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


async def _eerste_pdf_uit_resultaten(
    results: list[dict[str, str]], zoekjaar: int, uitgesloten: set[str] | None = None,
) -> str | None:
    uitgesloten = uitgesloten or set()
    for result in results:
        url = fetch._unwrap_safelink(result["url"])
        if url in uitgesloten:
            continue
        context = f"{result.get('title', '')} {url}"
        if not _lijkt_jaarverslag(context, zoekjaar):
            continue
        if ".pdf" in url.lower():
            return url
        pdf_from_page = await _scrape_pdf_van_pagina(url, zoekjaar)
        if (
            pdf_from_page
            and pdf_from_page not in uitgesloten
            and _lijkt_jaarverslag(pdf_from_page, zoekjaar)
        ):
            return pdf_from_page
    return None


# Een overzichtspagina ("Jaarverslagen" met links naar 2019 t/m 2024) lijkt op
# een jaarverslag maar is er geen. Zulke pagina's zijn kort en bestaan vooral uit
# links; een verslag zelf heeft lopende tekst. Deze ondergrens scheidt de twee
# zonder dat er een model aan te pas komt.
_MIN_TEKENS_HTML_JAARVERSLAG = 3_000


async def _html_jaarverslag_van_pagina(pagina_url: str, jaar: int) -> str | None:
    """Is deze pagina zélf het jaarverslag, in plaats van een link ernaartoe?

    Steeds meer organisaties publiceren hun jaarverslag als website in plaats van
    als PDF. Die werden volledig gemist: `_eerste_pdf_uit_resultaten` sloeg elke
    pagina over waar geen PDF-link op stond, dus kwam er "geen jaarverslag
    gevonden" uit terwijl het er gewoon stond.

    Twee eisen, allebei zonder model: er moet genoeg lopende tekst staan om een
    overzichtspagina uit te sluiten, en het verslagjaar moet in die tekst
    terugkomen. Dat laatste voorkomt dat een willekeurige "over ons"-pagina die
    het woord jaarverslag noemt als bron wordt aangemerkt.
    """
    try:
        tekst = await fetch._fetch_text(pagina_url)
    except Exception:
        return None
    if len(tekst) < _MIN_TEKENS_HTML_JAARVERSLAG:
        return None
    if jaar not in _verslagjaren_uit(tekst[:20_000]):
        return None
    return pagina_url


async def _eerste_html_uit_resultaten(
    results: list[dict[str, str]], zoekjaar: int, uitgesloten: set[str] | None = None,
) -> str | None:
    uitgesloten = uitgesloten or set()
    for result in results:
        url = fetch._unwrap_safelink(result["url"])
        if url in uitgesloten or ".pdf" in url.lower():
            continue
        if not _lijkt_jaarverslag(f"{result.get('title', '')} {url}", zoekjaar):
            continue
        gevonden = await _html_jaarverslag_van_pagina(url, zoekjaar)
        if gevonden:
            return gevonden
    return None


async def _zoek_jaarverslagbron(
    naam: str, jaar: int, website_url: str | None = None, uitgesloten: set[str] | None = None,
    zoekjaren: tuple[int, ...] | None = None,
) -> str | None:
    """Zoek drie verslagjaren in één provider-ronde en selecteer nieuwste-eerst.

    De zoekopdracht blijft bewust kort. Gemeten op 10 organisaties die
    aantoonbaar publiceren vond de oude, uitgebreide query er 2 en deze er 8:
    een opsomming van synoniemen en jaartallen verwatert de zoekopdracht zodat
    de index vooral op "jaarverslag pdf" matcht in plaats van op de organisatie.
    De jaarselectie gebeurt daarna alsnog, in nieuwste_uit()."""
    jaren = zoekjaren or (jaar - 1, jaar - 2, jaar - 3)
    # Alleen nog voor de hosted fallback, die een beschrijvende opdracht krijgt
    # in plaats van zoekwoorden.
    jaren_query = " ".join(str(zoekjaar) for zoekjaar in jaren)

    async def nieuwste_uit(results: list[dict[str, str]]) -> str | None:
        """Eerst alle jaren op PDF, pas daarna alle jaren op HTML.

        Twee volledige rondes en niet één gecombineerde: een PDF is de sterkere
        bron (vaste opmaak, paginanummer voor het bewijs), dus een HTML-treffer
        van een nieuwer jaar mag een beschikbare PDF niet verdringen.
        """
        for zoekjaar in jaren:
            gevonden = await _eerste_pdf_uit_resultaten(
                results,
                zoekjaar,
                uitgesloten,
            )
            if gevonden:
                return gevonden
        for zoekjaar in jaren:
            gevonden = await _eerste_html_uit_resultaten(
                results,
                zoekjaar,
                uitgesloten,
            )
            if gevonden:
                return gevonden
        return None

    domein = fetch._domein_van_url(website_url)
    if domein:
        site_results = await search._web_search(
            f"site:{domein} jaarverslag",
            max_results=8,
        )
        gevonden = await nieuwste_uit(site_results)
        if gevonden:
            return gevonden

    results = await search._web_search(
        f"{naam} jaarverslag pdf",
        max_results=10,
    )
    gevonden = await nieuwste_uit(results)
    if gevonden:
        return gevonden

    # Overheden publiceren geen "jaarverslag" maar jaarstukken. Deze extra ronde
    # kost 0,1 ct en wordt alleen gedaan als de gewone zoekopdracht niets oplevert.
    jaarstukken_results = await search._web_search(
        f"{naam} jaarstukken filetype:pdf",
        max_results=10,
    )
    gevonden = await nieuwste_uit(jaarstukken_results)
    if gevonden:
        return gevonden

    hosted_results = await search._openai_web_search(
        (
            f'"{naam}" meest recente officiële organisatiebrede jaarverslag '
            f"of bestuursverslag uit {jaren_query}, direct pdf; geen deelverslag "
            "van raad, commissie, afdeling, toezichthouder of gouverneur"
        ),
        max_results=8,
    )
    return await nieuwste_uit(hosted_results)

