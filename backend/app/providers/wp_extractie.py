"""Van zoekresultaat naar AgentFinding.

Gedeeld door de website- en jaarverslag-agents: haal de pagina op, controleer of
de bron werkelijk over deze organisatie gaat, en laat de LLM er een WP-getal uit
halen. De naamcheck staat bewust vóór de LLM-call — dat scheelt tokens én
voorkomt de duurste foutklasse (een getal van een ander bedrijf)."""
from ..config import get_settings
from . import fetch, llm, search
from .base import AgentFinding
from .naam_matching import _is_vacature_of_jobs_url, _tekst_lijkt_bij_bedrijf_te_horen

settings = get_settings()


def _als_aantal(waarde) -> int | None:
    """Een LLM-antwoord naar een aantal, of None als het er geen is.

    `int(data["wp_gevonden"])` vertrouwde erop dat dit veld een getal is. Bij
    Stichting XONAR sloeg de hele jaarverslagcontrole daarop stuk
    (`invalid literal for int() with base 10: '8d\\xc2\\x94...'`): de bron was een
    PDF die als platte tekst werd binnengehaald, de LLM kreeg bytes te zien en
    gaf een stuk van die ruis terug als aantal. Externe tekst is onbetrouwbare
    invoer, dus ook wat de LLM eruit terugkoppelt — één onbruikbaar veld mag
    hoogstens deze bron laten vallen, niet de controle van de organisatie.

    Punten en spaties als duizendscheiding blijven toegestaan (`1.204`, `1 204`).
    """
    if isinstance(waarde, bool):
        return None
    if isinstance(waarde, int):
        return waarde
    if isinstance(waarde, float):
        return int(waarde)
    tekst = str(waarde or "").strip().replace(".", "").replace(" ", "")
    return int(tekst) if tekst.isdigit() else None


def _finding_van_zoekresultaat(naam: str, data: dict, result: dict, bron_type: str) -> AgentFinding:
    return AgentFinding(
        wp_gevonden=_als_aantal(data["wp_gevonden"]),
        context=data.get("context"),
        zekerheid=data.get("zekerheid", "laag"),
        reden=data.get("reden"),
        bron_url=result["url"],
        bron_type=bron_type,
        is_totaal_meerdere_vestigingen=data.get("is_totaal_meerdere_vestigingen", False),
        is_limburg_specifiek=data.get("is_limburg_specifiek"),
        is_fte=data.get("is_fte", False),
        peilmoment=data.get("peilmoment"),
        eigen_personeel=data.get("eigen_personeel"), uitzend=data.get("uitzend"),
        detachering=data.get("detachering"), wsw=data.get("wsw"),
        man=data.get("man"), vrouw=data.get("vrouw"),
        voltijd=data.get("voltijd"), deeltijd=data.get("deeltijd"),
        pct_op_locatie=llm._pct_op_locatie_fractie(data.get("pct_op_locatie")),
        raw={**data, "research_source": result.get("bron", "duckduckgo"), "search_result": result},
    )


async def _extract_wp_van_zoekresultaten(
    naam: str, gemeente: str | None, results: list[dict[str, str]],
    bron_type: str = "media", max_bronnen: int = 1,
) -> list[AgentFinding]:
    """Doorloopt zoekresultaten en extraheert WP-bevindingen; stopt zodra
    max_bronnen gevonden is (max_bronnen=1 repliceert het oude 'stop bij eerste
    hit'-gedrag, hogere waarden verzamelen meerdere bronnen voor het
    human-in-the-loop-overzicht)."""
    if not settings.openai_api_key:
        return []
    bevindingen: list[AgentFinding] = []
    for result in results:
        if len(bevindingen) >= max_bronnen:
            break
        if _is_vacature_of_jobs_url(result["url"]):
            continue
        try:
            tekst = await fetch._fetch_text(result["url"])
        except Exception:
            continue
        bron_context = " ".join([
            result.get("title", ""),
            result.get("snippet", ""),
            result.get("url", ""),
            tekst[:20000],
        ])
        if not _tekst_lijkt_bij_bedrijf_te_horen(naam, bron_context):
            continue
        data = await llm._llm_extract(naam, gemeente, tekst)
        if not data or _als_aantal(data.get("wp_gevonden")) is None:
            continue
        bevindingen.append(_finding_van_zoekresultaat(naam, data, result, bron_type))
    return bevindingen


async def _extract_wp_from_search_results(
    naam: str, gemeente: str | None, results: list[dict[str, str]], bron_type: str = "media"
) -> AgentFinding | None:
    bevindingen = await _extract_wp_van_zoekresultaten(naam, gemeente, results[:3], bron_type, max_bronnen=1)
    return bevindingen[0] if bevindingen else None


async def _web_search_wp(naam: str, gemeente: str | None) -> AgentFinding | None:
    results = await search._web_search(
        f"{naam} {gemeente or ''} medewerkers".strip(),
        max_results=5,
    )
    return await _extract_wp_from_search_results(naam, gemeente, results)


async def verzamel_extra_media_bronnen(
    naam: str, gemeente: str | None, uitsluiten: set[str] | None = None,
) -> list[AgentFinding]:
    """Verzamelt tot settings.extra_bronnen_aantal aanvullende publieke bronnen
    (LinkedIn, KvK-vermeldingen, nieuwsartikelen, etc.) naast website/jaarverslag —
    ook voor kleine bedrijven zonder jaarverslag. Telt niet mee in de reconciliatie/
    confidence-score; dient puur als extra keuzemateriaal voor de reviewer."""
    if settings.extra_bronnen_aantal <= 0:
        return []
    results = await search._web_search(
        f"{naam} {gemeente or ''} medewerkers".strip(),
        max_results=settings.extra_bronnen_aantal + 3,
    )
    uitsluiten = uitsluiten or set()
    results = [r for r in results if r["url"] not in uitsluiten]
    return await _extract_wp_van_zoekresultaten(
        naam, gemeente, results, bron_type="media", max_bronnen=settings.extra_bronnen_aantal,
    )
