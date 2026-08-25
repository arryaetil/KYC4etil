"""Fase C: de jaarverslag-agent zelf — zoeken, valideren, uitlezen.

Deze module regisseert de andere twee (`jaarverslag_zoeken`,
`jaarverslag_validatie`) en leest het WP-getal uit de PDF. Een afgewezen bron
wordt uitgesloten zodat een retry een ánder zoekresultaat probeert in plaats
van dezelfde fout opnieuw te maken."""
import re
from typing import TypedDict

import httpx

from ..config import get_settings
from ..pipeline.evidence import IdentityClass
from ..pipeline.identity_scope import domain_matches_company
from . import (
    fetch,
    jaarverslag_validatie,
    jaarverslag_zoeken,
    llm,
    search,
    wp_extractie,
)
from .base import AgentFinding

settings = get_settings()


async def _web_search_jaarverslag_wp(naam: str, jaar: int) -> AgentFinding | None:
    """Directe WP-zoekopdracht op jaarverslagdata: fallback als PDF-pad mislukt."""
    results = await search._web_search(
        f"{naam} jaarverslag {jaar} medewerkers",
        max_results=5,
    )
    return await wp_extractie._extract_wp_from_search_results(
        naam, None, results, bron_type="jaarverslag",
    )


def _baseline_jaarverslag_finding(pdf_url: str) -> AgentFinding:
    return AgentFinding(
        wp_gevonden=None, context=None, zekerheid="laag",
        reden="Jaarverslag gevonden, geen WP-getal geextraheerd",
        bron_url=pdf_url, bron_type="jaarverslag",
        raw={"research_graph": "jaarverslag", "pdf_url": pdf_url},
    )


def _deterministische_wp_uit_pdf(
    pagina_teksten: list[tuple[int, str]],
) -> dict | None:
    """Vang expliciete headcountzinnen op als de LLM ze incidenteel mist."""
    patronen = (
        re.compile(
            r"(?i)(?P<context>"
            r"(?:telt|heeft)\s+(?:bijna|ruim|circa|ongeveer)?\s*"
            r"(?P<aantal>\d{1,3}(?:[.\s]\d{3})+|\d{2,6})\s+medewerkers"
            r"[^.]{0,100})"
        ),
        re.compile(
            r"(?i)(?P<context>"
            r"biedt\s+[^.]{0,120}\s+aan\s+"
            r"(?:bijna|ruim|circa|ongeveer)?\s*"
            r"(?P<aantal>\d{1,3}(?:[.\s]\d{3})+|\d{2,6})\s+medewerkers"
            r"[^.]{0,100})"
        ),
        re.compile(
            r"(?i)(?P<context>"
            r"(?:bijna|ruim|circa|ongeveer)?\s*"
            r"(?P<aantal>\d{1,3}(?:[.\s]\d{3})+|\d{2,6})\s+medewerkers"
            r"\s+(?:in dienst|werkzaam|actief)[^.]{0,100})"
        ),
    )
    for paginanummer, tekst in pagina_teksten:
        compacte_tekst = " ".join(tekst.split())
        for patroon in patronen:
            match = patroon.search(compacte_tekst)
            if match:
                aantal = int(
                    match.group("aantal").replace(".", "").replace(" ", "")
                )
                return {
                    "wp_gevonden": aantal,
                    "context": match.group("context").strip(),
                    "zekerheid": "middel",
                    "reden": "expliciete headcountzin in jaarverslag",
                    "is_limburg_specifiek": None,
                    "is_fte": False,
                    "peilmoment": None,
                    "bron_pagina": paginanummer,
                    "extractiemethode": "deterministische_fallback",
                }
    return None


def _vind_paginanummer(context: str | None, pagina_teksten: list[tuple[int, str]]) -> int | None:
    """Zoekt op welke PDF-pagina de door de LLM geciteerde context daadwerkelijk
    staat, zodat de bron direct op de juiste pagina geopend kan worden."""
    if not context:
        return None
    fragment = context.strip()[:80].lower()
    if not fragment:
        return None
    for paginanummer, tekst in pagina_teksten:
        if fragment in tekst.lower():
            return paginanummer
    return None


# Waarop een pagina wordt geselecteerd voordat de LLM hem leest. Deze lijst
# bepaalt dus wat er überhaupt gevonden kán worden: staat het getal op een
# pagina die geen van deze woorden bevat, dan komt er "geen WP-getal" uit
# terwijl het er gewoon staat.
#
# Vandaar de verbreding: niet elk verslag schrijft "medewerkers". "Wij hebben
# 412 collega's", "312 arbeidsplaatsen" en Engelstalige verslagen met "workforce"
# of "staff" vielen er allemaal doorheen. Ruim kiezen kost weinig — de pagina's
# gaan daarna alsnog langs het model, dat zelf beslist of er een bruikbaar getal
# staat.
_WP_TREFWOORDEN = (
    "medewerker", "personeel", "headcount", "fte", "employee", "werknemer",
    "collega", "arbeidsplaats", "arbeidsovereenkomst", "dienstverband",
    "workforce", "staff", "in dienst", "loondienst", "formatie",
)


# Hoeveel pagina's er hoogstens naar het model gaan. Een jaarverslag van 109
# pagina's leverde er 59 met een personeelswoord op — samen 145.000 tekens, zo'n
# 36.000 tokens. Het model faalt daar niet op, het verliest het getal in de
# hooiberg: gemeten op het jaarverslag van SOML kwam er `wp_gevonden: None` uit
# terwijl "medewerkers" er 81 keer in staat. Juist bij grote organisaties, waar
# het cijfer er het meest toe doet.
MAX_PAGINAS_NAAR_MODEL = 8

# Een getal vlak vóór een personeelswoord: "1.066 medewerkers", "412 fte".
# Zo'n pagina is veel waarschijnlijker de vindplaats dan een pagina waar het
# woord alleen in lopende tekst voorkomt.
_GETAL_BIJ_PERSONEEL = re.compile(
    r"\d[\d.,\s]{0,8}\s*(?:mede|person|fte|collega|werknem|arbeidspl)",
    re.IGNORECASE,
)


def _paginascore(tekst: str) -> int:
    """Hoe waarschijnlijk staat het personeelsgetal op deze pagina?"""
    laag = tekst.lower()
    trefwoorden = sum(laag.count(woord) for woord in _WP_TREFWOORDEN)
    getallen = len(_GETAL_BIJ_PERSONEEL.findall(tekst))
    return trefwoorden + getallen * 5


def kies_paginas_voor_model(
    paginas: list[tuple[int | None, str]],
) -> list[tuple[int | None, str]]:
    """De meest belovende pagina's, in hun oorspronkelijke volgorde.

    Trimmen en niet afkappen: een kale afkapping op tekenaantal gooit net zo
    goed de juiste pagina weg. Deze selectie kijkt waar een getal naast een
    personeelswoord staat en houdt daarna de leesvolgorde aan, zodat het
    citaat en het paginanummer blijven kloppen.
    """
    if len(paginas) <= MAX_PAGINAS_NAAR_MODEL:
        return paginas
    beste = sorted(
        paginas,
        key=lambda item: _paginascore(item[1]),
        reverse=True,
    )[:MAX_PAGINAS_NAAR_MODEL]
    gekozen = {id(item) for item in beste}
    return [item for item in paginas if id(item) in gekozen]


async def _relevante_bronpaginas(bron_url: str) -> list[tuple[int | None, str]]:
    """De stukken van een jaarverslag waar personeel in voorkomt.

    Per pagina bij een PDF — het paginanummer is nodig om de bron later precies
    op de plek van het citaat te openen. Een webversie kent die nummering niet;
    daar is het één blok en blijft het paginanummer leeg, wat de viewer gewoon
    aankan.

    Zonder deze splitsing was de hele extractie aan PDF vastgeklonken:
    `fitz.open` op een HTML-pagina levert niets bruikbaars op, dus een
    jaarverslag dat als website is gepubliceerd gaf altijd None terug.
    """
    if not fetch._is_pdf_url(bron_url):
        try:
            tekst = await fetch._fetch_text(bron_url)
        except Exception:
            return []
        heeft_trefwoord = any(
            woord in tekst.lower() for woord in _WP_TREFWOORDEN
        )
        return [(None, tekst)] if heeft_trefwoord else []

    import fitz  # PyMuPDF

    async with httpx.AsyncClient(
        timeout=60,
        follow_redirects=True,
        headers={"User-Agent": fetch.USER_AGENT},
    ) as client:
        response = await client.get(bron_url)
        response.raise_for_status()
    document = fitz.open(stream=response.content, filetype="pdf")
    return [
        (index + 1, pagina.get_text())
        for index, pagina in enumerate(document)
        if any(woord in pagina.get_text().lower() for woord in _WP_TREFWOORDEN)
    ]


class JaarverslagResearchState(TypedDict, total=False):
    naam: str
    jaar: int
    website_url: str | None
    pdf_url: str | None
    laatste_pdf_url: str | None
    laatste_geldige_pdf_url: str | None
    afgewezen_urls: set[str]
    pogingen: int
    source_identity_class: str | None
    strict_identity: bool
    finding: AgentFinding | None


def _build_jaarverslag_research_graph():
    from langgraph.graph import END, StateGraph

    async def find_pdf(state: JaarverslagResearchState) -> dict:
        afgewezen = state.get("afgewezen_urls") or set()
        pdf_url = await jaarverslag_zoeken._zoek_jaarverslagbron(
            state["naam"], state["jaar"], website_url=state.get("website_url"),
            uitgesloten=afgewezen,
        )
        return {
            "pdf_url": pdf_url,
            "laatste_pdf_url": pdf_url or state.get("laatste_pdf_url"),
            "pogingen": state.get("pogingen", 0) + 1,
        }

    async def valideer_bron(state: JaarverslagResearchState) -> dict:
        pdf_url = state.get("pdf_url")
        domein_match = domain_matches_company(
            pdf_url,
            state.get("website_url"),
        )
        identity = (
            IdentityClass.EXACT_ENTITY
            if domein_match is True
            else await jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit(
                state["naam"],
                pdf_url,
            )
        )
        toegestaan = identity == IdentityClass.EXACT_ENTITY or (
            identity == IdentityClass.SAME_BRAND_OR_GROUP
            and not state.get("strict_identity", False)
        )
        if toegestaan and state.get("strict_identity", False):
            organisatiebreed = await jaarverslag_validatie._is_organisatiebreed_jaarverslag(
                state["naam"],
                pdf_url,
            )
            if organisatiebreed is not True:
                toegestaan = False
        if (
            toegestaan
            and state.get("strict_identity", False)
            and not await jaarverslag_validatie._pdf_is_recent_jaarverslag(
                pdf_url,
                state["jaar"],
            )
        ):
            toegestaan = False
        if pdf_url and toegestaan:
            return {
                "pdf_url": pdf_url,
                "laatste_geldige_pdf_url": pdf_url,
                "source_identity_class": identity.value,
            }
        # Afgewezen (verkeerd bedrijf): uitsluiten zodat een retry een ANDER
        # zoekresultaat probeert i.p.v. dezelfde foute bron opnieuw te vinden.
        afgewezen = set(state.get("afgewezen_urls") or set())
        if pdf_url:
            afgewezen.add(pdf_url)
        return {"pdf_url": None, "source_identity_class": identity.value, "afgewezen_urls": afgewezen}

    async def extract_pdf(state: JaarverslagResearchState) -> dict:
        pdf_url = state.get("pdf_url")
        if not pdf_url:
            return {"finding": None}
        afgewezen = set(state.get("afgewezen_urls") or set())
        afgewezen.add(pdf_url)  # bij een retry niet nogmaals dezelfde (mogelijk lege) bron proberen
        try:
            finding = await LiveJaarverslagAgent().run_met_bron(state["naam"], pdf_url)
            if finding:
                finding.raw = {
                    **(finding.raw or {}),
                    "identity_class": state.get("source_identity_class") or IdentityClass.UNKNOWN.value,
                }
            return {"finding": finding, "afgewezen_urls": afgewezen}
        except Exception:
            return {"finding": None, "afgewezen_urls": afgewezen}

    async def web_search_fallback(state: JaarverslagResearchState) -> dict:
        return {"finding": await _web_search_jaarverslag_wp(state["naam"], state["jaar"])}

    async def baseline_source(state: JaarverslagResearchState) -> dict:
        pdf_url = state.get("laatste_geldige_pdf_url")
        return {"finding": _baseline_jaarverslag_finding(pdf_url) if pdf_url else None}

    def mag_opnieuw(state: JaarverslagResearchState) -> bool:
        return state.get("pogingen", 0) < settings.jaarverslag_max_pogingen

    def after_find_pdf(state: JaarverslagResearchState) -> str:
        if state.get("pdf_url"):
            return "valideer_bron"
        if state.get("laatste_geldige_pdf_url"):
            return "baseline_source"
        return "web_search_fallback" if settings.jaarverslag_web_fallback else END

    def after_valideer_bron(state: JaarverslagResearchState) -> str:
        if state.get("pdf_url"):
            return "extract_pdf"
        # Afgewezen bron: probeer een ANDER zoekresultaat i.p.v. meteen op te geven
        # (dit was letterlijk het Mondriaan/Salon Handmade-scenario).
        if mag_opnieuw(state):
            return "find_pdf"
        if state.get("laatste_geldige_pdf_url"):
            return "baseline_source"
        return "web_search_fallback" if settings.jaarverslag_web_fallback else END

    def after_extract_pdf(state: JaarverslagResearchState) -> str:
        if state.get("finding"):
            return END
        # Geldige bron, maar geen WP-getal erin (bv. een kwaliteitsverslag i.p.v. de
        # jaarverantwoording) -> ook dit is retry-waardig, geen definitieve mislukking.
        if mag_opnieuw(state):
            return "find_pdf"
        return "web_search_fallback" if settings.jaarverslag_web_fallback else "baseline_source"

    def after_web_search(state: JaarverslagResearchState) -> str:
        return END if state.get("finding") else "baseline_source"

    graph = StateGraph(JaarverslagResearchState)
    graph.add_node("find_pdf", find_pdf)
    graph.add_node("valideer_bron", valideer_bron)
    graph.add_node("extract_pdf", extract_pdf)
    graph.add_node("web_search_fallback", web_search_fallback)
    graph.add_node("baseline_source", baseline_source)
    graph.set_entry_point("find_pdf")
    graph.add_conditional_edges("find_pdf", after_find_pdf)
    graph.add_conditional_edges("valideer_bron", after_valideer_bron)
    graph.add_conditional_edges("extract_pdf", after_extract_pdf)
    graph.add_conditional_edges("web_search_fallback", after_web_search)
    graph.add_edge("baseline_source", END)
    return graph.compile()


async def _run_jaarverslag_research_graph(
    naam: str,
    jaar: int,
    website_url: str | None = None,
    strict_identity: bool = False,
) -> AgentFinding | None:
    graph = _build_jaarverslag_research_graph()
    result = await graph.ainvoke({
        "naam": naam,
        "jaar": jaar,
        "website_url": website_url,
        "pdf_url": None,
        "laatste_pdf_url": None,
        "laatste_geldige_pdf_url": None,
        "afgewezen_urls": set(),
        "pogingen": 0,
        "source_identity_class": None,
        "strict_identity": strict_identity,
        "finding": None,
    })
    return result.get("finding")


class LiveJaarverslagAgent:
    async def find_latest_source(
        self,
        naam: str,
        jaar: int,
        website_url: str | None = None,
        strict_identity: bool = False,
    ) -> AgentFinding | None:
        """Vind en valideer alleen de nieuwste bron; monitoring hoeft geen WP-extractie."""
        uitgesloten: set[str] = set()
        beste_oude_vinding: AgentFinding | None = None
        beste_oude_jaar: int | None = None
        zoekjaren: tuple[int, ...] | None = None
        for _ in range(min(settings.jaarverslag_max_pogingen, 3)):
            pdf_url = await jaarverslag_zoeken._zoek_jaarverslagbron(
                naam,
                jaar,
                website_url=website_url,
                uitgesloten=uitgesloten,
                zoekjaren=zoekjaren,
            )
            if not pdf_url:
                return beste_oude_vinding

            try:
                eerste_paginas = await fetch._brontekst(pdf_url)
            except Exception:
                uitgesloten.add(pdf_url)
                continue

            domein_match = domain_matches_company(pdf_url, website_url)
            landdomein_conflict = fetch._heeft_landdomein_conflict(
                pdf_url,
                website_url,
            )
            identity = (
                IdentityClass.MISMATCH
                if landdomein_conflict
                else
                IdentityClass.EXACT_ENTITY
                if domein_match is True
                else await jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit(
                    naam,
                    pdf_url,
                    eerste_paginas,
                )
            )
            toegestaan = identity == IdentityClass.EXACT_ENTITY or (
                identity == IdentityClass.SAME_BRAND_OR_GROUP
                and not strict_identity
            )
            if toegestaan and strict_identity:
                toegestaan = await jaarverslag_validatie._is_organisatiebreed_jaarverslag(
                    naam,
                    pdf_url,
                    eerste_paginas,
                ) is True
            verslagjaar = jaarverslag_zoeken._verslagjaar_uit_pdftekst(eerste_paginas, jaar)
            if toegestaan and strict_identity:
                toegestaan = verslagjaar is not None
            if toegestaan:
                finding = _baseline_jaarverslag_finding(pdf_url)
                finding.raw = {
                    **(finding.raw or {}),
                    "identity_class": identity.value,
                    "verslagjaar": verslagjaar,
                }
                # Een gecombineerde zoekopdracht kan ondanks de jaarfilters een
                # oud resultaat bovenaan zetten. Zoek dan gericht naar de
                # tussenliggende jaren; behoud het oude document als veilige
                # fallback wanneer geen nieuwer officieel document bestaat.
                if (
                    strict_identity
                    and verslagjaar is not None
                    and verslagjaar < jaar - 1
                ):
                    if beste_oude_jaar is None or verslagjaar > beste_oude_jaar:
                        beste_oude_vinding = finding
                        beste_oude_jaar = verslagjaar
                    uitgesloten.add(pdf_url)
                    zoekjaren = tuple(
                        range(jaar - 1, verslagjaar, -1)
                    )
                    continue
                return finding
            if landdomein_conflict:
                return None
            uitgesloten.add(pdf_url)
        return beste_oude_vinding

    async def run(
        self,
        naam: str,
        jaar: int,
        website_url: str | None = None,
        strict_identity: bool = False,
    ) -> AgentFinding | None:
        """Fase A: zoek jaarverslag-PDF via web search; Fase B: extraheer WP uit PDF.
        Fase C (optioneel): directe WP-zoekopdracht op jaarverslagdata als PDF-pad mislukt.
        Fase C is standaard uitgeschakeld (JAARVERSLAG_WEB_FALLBACK=false) voor kostenbeheersing.
        Vindt Fase A wel een PDF maar levert geen van beide paden een WP-getal op, dan
        wordt de gevonden bron_url alsnog teruggegeven (zonder wp_gevonden) zodat de
        jaarverslag-monitoring een baseline-URL heeft om toekomstige wijzigingen aan te
        toetsen — anders gaat een gevonden jaarverslag-link onnodig verloren.

        website_url wordt, indien bekend, gebruikt om de PDF-zoekopdracht eerst binnen
        het eigen domein te laten zoeken (site:-scoped) — dat is veel minder gevoelig
        voor niet-determinisme/mismatches dan een open zoekopdracht op alleen de naam."""
        return await _run_jaarverslag_research_graph(
            naam,
            jaar,
            website_url=website_url,
            strict_identity=strict_identity,
        )

    async def validate_source(
        self,
        naam: str,
        jaar: int,
        bron_url: str,
        website_url: str | None = None,
        strict_identity: bool = False,
    ) -> bool:
        """Herbeoordeel een legacy-baseline met de huidige strikte regels."""
        try:
            eerste_paginas = await fetch._brontekst(bron_url)
        except Exception:
            return False
        if fetch._heeft_landdomein_conflict(bron_url, website_url):
            return False
        if jaarverslag_zoeken._verslagjaar_uit_pdftekst(eerste_paginas, jaar) is None:
            return False
        if strict_identity:
            organisatiebreed = await jaarverslag_validatie._is_organisatiebreed_jaarverslag(
                naam,
                bron_url,
                eerste_paginas,
            )
            if organisatiebreed is not True:
                return False
        if domain_matches_company(bron_url, website_url) is True:
            return True
        identity = await jaarverslag_validatie._classificeer_jaarverslag_bron_identiteit(
            naam,
            bron_url,
            eerste_paginas,
        )
        return identity == IdentityClass.EXACT_ENTITY or (
            identity == IdentityClass.SAME_BRAND_OR_GROUP
            and not strict_identity
        )

    async def run_met_bron(self, naam: str, bron_url: str) -> AgentFinding | None:
        """Lees het WP-getal uit een jaarverslag, of dat nu een PDF is of een site."""
        relevant = await _relevante_bronpaginas(bron_url)
        if not relevant:
            return None
        # Alleen naar het model gaat een selectie; de deterministische
        # terugval leest gewoon alles, want die kost niets en heeft geen last
        # van lange documenten.
        voor_model = kies_paginas_voor_model(relevant)
        data = await llm._llm_extract(
            naam, None, "\n\n".join(tekst for _, tekst in voor_model),
        )
        if not data or not data.get("wp_gevonden"):
            data = _deterministische_wp_uit_pdf(relevant)
            if data is None:
                return None
        pct = data.get("pct_op_locatie")
        return AgentFinding(
            wp_gevonden=data["wp_gevonden"], context=data.get("context"),
            zekerheid=data.get("zekerheid", "laag"), reden=data.get("reden"),
            bron_url=bron_url, bron_type="jaarverslag",
            is_limburg_specifiek=data.get("is_limburg_specifiek"),
            is_fte=data.get("is_fte", False), peilmoment=data.get("peilmoment"),
            eigen_personeel=data.get("eigen_personeel"), uitzend=data.get("uitzend"),
            detachering=data.get("detachering"), wsw=data.get("wsw"),
            man=data.get("man"), vrouw=data.get("vrouw"),
            voltijd=data.get("voltijd"), deeltijd=data.get("deeltijd"),
            pct_op_locatie=llm._pct_op_locatie_fractie(pct),
            bron_pagina=_vind_paginanummer(data.get("context"), relevant),
            raw=data,
        )
