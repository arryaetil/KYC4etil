"""Hoe lang doet een lijst erover, en waar zit die tijd in?

Gebruik vanuit backend/:  PROVIDER_MODE=mock python -m scripts.bench_batch

Dit meet de echte `run_research_batch` — dezelfde code die op Railway draait —
maar met een gereedschapslaag die niet het netwerk op gaat en in plaats daarvan
wacht. De wachttijden zijn geijkt op de productiecijfers van 638 research-runs
(mediaan 25 modelcalls en 16 gelezen documenten per run), en daarna gedeeld
door `SCHAAL`, zodat een meting minuten kost en geen uren. Wat je hier afleest
zijn dus verhoudingen, geen seconden: het vaste werk (database, planning) valt
door die deling relatief zwaarder uit, dus de gemeten winst is eerder te laag
dan te hoog.

Twee vormen van lijst, want ze hebben niet dezelfde bottleneck:

- losse organisaties, die niets met elkaar delen. Alleen parallelliseren helpt.
- één organisatie met veel vestigingen — de vorm van "Copy of Zorggroep": 108
  vestigingen, 407 bronkaarten over 149 unieke URL's. Daar telt ook of
  hetzelfde jaarverslag één keer of tien keer wordt gelezen.

De gedeelde browser laat maar een beperkt aantal pagina's tegelijk renderen
(`fetch._crawler_semafoor`, procesbreed), en die rem zit hier in de meting.
Dat is nodig sinds er meer organisaties tegelijk lopen: ze delen die plaatsen,
dus een rem die niet meegroeit zet het parallelle werk weer op een rij. Elke
HTML-leesbeurt rendert hier; in productie staat CRAWL4AI_ALTIJD op false en
rendert alleen wat de platte HTTP-poging niet prijsgeeft. Wat je hier van de
rem ziet is dus de bovengrens, niet het dagelijkse beeld.

Deze benchmark heeft één idee al afgeschoten: vestigingen van dezelfde
organisatie groeperen en er één vooruitsturen, zodat de rest haar bronnen kan
overnemen. Dat kost meer dan het oplevert — alleen de eerste golf loopt het
hergebruik mis. Zie de docstring van `run_research_batch`.
"""
import asyncio
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("PROVIDER_MODE", "mock")

from app.config import get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Batch, Company  # noqa: E402
from app.research import organizations, seeds, service  # noqa: E402
from app.research.types import CombinedSearchResult  # noqa: E402
from app.research.urls import canonicaliseer_url  # noqa: E402
from app.research.validation import SourceDocument, valideer_bron  # noqa: E402

# Alles door tien. Zie de moduletekst: het gaat om de verhouding.
SCHAAL = 10
T_ZOEKEN = 0.6 / SCHAAL      # één Serper-zoekopdracht
# Ophalen + extractiecall over de paginatekst: samen 3,0s, zoals eerder geijkt.
# Hier gesplitst, want alleen het ophalen staat achter de browserrem: de
# semafoor in fetch.py omsluit `crawler.arun` en niet de extractie die erop
# volgt. De verdeling half/half is een aanname — is het renderdeel in
# werkelijkheid groter, dan knijpt de rem harder dan hier te zien is.
T_RENDEREN = 1.5 / SCHAAL
T_EXTRACTIE = 1.5 / SCHAAL
T_LEZEN = T_RENDEREN + T_EXTRACTIE
T_REVIEW = 2.0 / SCHAAL      # de bronreview-call
T_SCOPE = 1.5 / SCHAAL       # losse scope-call als de scope nog niet vaststaat
T_SAMENVATTING = 1.5 / SCHAAL

AANTAL = 12


class TraagTools:
    """Doet niets, maar doet er wel even over. Telt wat het gedaan heeft.

    `rem` staat voor `fetch._crawler_semafoor`: de gedeelde browser laat maar
    een beperkt aantal renders tegelijk toe, en die semafoor geldt voor het
    hele proces — dus voor alle organisaties samen. Zonder dat hier zat de
    benchmark naast de werkelijkheid: hij mat de winst van parallel draaien
    zonder de rem die dat parallelle werk juist opnieuw op een rij zet.
    """

    def __init__(self, gedeeld: bool, rem: asyncio.Semaphore):
        # Bij een organisatie met meer vestigingen wijst iedereen naar hetzelfde
        # concernjaarverslag; dat is precies de bron die herbruikbaar is.
        self.gedeeld = gedeeld
        self.rem = rem
        self.gelezen = 0
        self.gerenderd = 0
        self.gezocht = 0
        self.remwacht = 0.0

    def _documenten_voor(self, naam: str) -> list[tuple[str, str, str]]:
        stam = "concern" if self.gedeeld else naam.lower().replace(" ", "-")
        return [
            (f"https://{stam}.example/jaarverslag-2025.pdf", "jaarverslag", "concern"),
            (f"https://{stam}.example/nieuws/groei", "media", "nederland"),
            (f"https://{naam.lower().replace(' ', '-')}.example/team", "website", "vestiging"),
        ]

    async def search(self, query, max_results: int) -> list[CombinedSearchResult]:
        self.gezocht += 1
        await asyncio.sleep(T_ZOEKEN)
        return [
            CombinedSearchResult(
                title=f"{soort} — {url}", url=url,
                canonical_url=canonicaliseer_url(url),
                snippets=["Er werken 852 medewerkers."],
                providers=["bench"], queries=[query.query],
            )
            for url, soort, _ in self._documenten_voor(query.query.split(" ")[0])
        ][:max_results]

    async def inspect(self, context, query, result) -> SourceDocument | None:
        self.gelezen += 1
        if ".pdf" in result.url:
            # De PDF-route raakt de browser niet aan: fetch.py stuurt een
            # PDF-URL langs de renderpoging heen, en live_tools laat hem door
            # de jaarverslag-agent lezen. Die leesbeurt wacht dus op niets.
            await asyncio.sleep(T_LEZEN)
        else:
            self.gerenderd += 1
            begin = time.perf_counter()
            async with self.rem:
                self.remwacht += time.perf_counter() - begin
                await asyncio.sleep(T_RENDEREN)
            # De extractiecall staat buiten de semafoor; de tab is dan al vrij.
            await asyncio.sleep(T_EXTRACTIE)
        scope = next(
            (s for url, _, s in self._documenten_voor(context.naam)
             if url == result.url),
            None,
        )
        return SourceDocument(
            naam=context.naam,
            company_website_url=context.website_url,
            url=result.url,
            titel=result.title,
            tekst="Er werken 852 medewerkers bij deze organisatie.",
            brontype="jaarverslag" if ".pdf" in result.url else "media",
            documenttype="jaarverslag" if ".pdf" in result.url else "nieuwsartikel",
            gevraagd_jaar=context.gevraagd_jaar,
            verslagjaar=context.gevraagd_jaar,
            wp_gevonden=852,
            eenheid="werkzame_personen",
            bewijsfragment="Er werken 852 medewerkers.",
            scope_class=scope,
            wp_extractie_gedaan=True,
            raw_data={"bench": True},
        )

    async def find_officiele_website(self, context):
        return None

    async def find_nieuwste_officiele_document(self, context):
        return None

    async def find_jaarverslag(self, context):
        return None


class TraagReviewer:
    """Modelleert de bronreview: één call, plus één extra als de scope nog open
    staat. Een hergebruikte bron ruilt de extractiecall in voor die scopecall —
    dat verschil hoort dus in de meting te zitten en niet weggemoffeld."""

    def __init__(self, tools: TraagTools):
        self.tools = tools
        self.reviews = 0
        self.scopecalls = 0

    async def review(self, context, document):
        self.reviews += 1
        await asyncio.sleep(T_REVIEW)
        if document.scope_class is None:
            self.scopecalls += 1
            await asyncio.sleep(T_SCOPE)
            document = replace(document, scope_class="limburg")
        return valideer_bron(document)


class _Controle:
    bruikbaar = True
    reden = "ok"

    def __init__(self, url):
        self.url = url


async def _geen_websitecontrole(url):
    return _Controle(url)


async def _geen_probe(context, route_plan):
    return route_plan


async def _geen_samenvatting(*args, **kwargs):
    await asyncio.sleep(T_SAMENVATTING)
    return None


async def _leeg(*args, **kwargs):
    return None


async def _lege_lijst(*args, **kwargs):
    return []


def _zet_klaar(naam: str, gedeeld: bool, aantal: int = AANTAL) -> str:
    """Eén lijst met `aantal` vestigingen; gedeeld = allemaal dezelfde organisatie."""
    with SessionLocal() as db:
        batch = Batch(naam=naam, jaar=2026, totaal=aantal)
        db.add(batch)
        db.flush()
        for nummer in range(aantal):
            db.add(Company(
                batch_id=batch.id,
                naam=f"Vestiging {nummer:02d}",
                vestigingsnummer=f"{naam}-{nummer:02d}",
                gemeente="Heerlen",
                sbi_code="6201",
                # Hetzelfde KvK-nummer maakt er één organisatie van; dat is de
                # enige deterministische sleutel die vestigingen mag koppelen.
                kvk_nummer="12345678" if gedeeld else f"1234{nummer:04d}",
                website_url=(
                    "https://concern.example" if gedeeld
                    else f"https://vestiging-{nummer:02d}.example"
                ),
            ))
        db.commit()
        return batch.id


def _patch(monkeys, gedeeld: bool, hergebruik: bool, rem: asyncio.Semaphore):
    tools = TraagTools(gedeeld=gedeeld, rem=rem)
    reviewer = TraagReviewer(tools)
    monkeys.update({
        (service, "LiveResearchTools"): lambda: tools,
        (service, "controleer_website"): _geen_websitecontrole,
        (service, "verrijk_routeplan"): _geen_probe,
        (service, "schrijf_samenvatting"): _geen_samenvatting,
        (service, "IntelligentSourceReviewer"): lambda: reviewer,
        (seeds, "zoek_digimv_documenten"): _lege_lijst,
        (seeds, "vind_duo_personeelsbron"): _leeg,
        (seeds, "vind_lrk_bron"): _leeg,
    })
    if not hergebruik:
        # De oude situatie: een zusterbron wordt gevonden maar opnieuw gelezen.
        # Geen codewijziging nodig — `zelfde_lijst` uitzetten ís het oude gedrag.
        echt = organizations.vind_bestaande_bronnen

        def zonder_hergebruik(db, company, limiet=12):
            return [
                replace(bron, zelfde_lijst=False)
                for bron in echt(db, company, limiet)
            ]

        monkeys[(service, "vind_bestaande_bronnen")] = zonder_hergebruik
    return tools, reviewer


async def _meet(label: str, gedeeld: bool, parallel: int, hergebruik: bool,
                aantal: int = AANTAL, herhalingen: int = 2,
                rem: int | None = None) -> dict:
    """De snelste van een paar pogingen. Eén meting op een laptop zegt weinig:
    achtergrondwerk maakt het verschil tussen twee identieke runs groter dan
    het verschil dat we willen zien."""
    beste = None
    for _ in range(herhalingen):
        poging = await _een_meting(label, gedeeld, parallel, hergebruik, aantal,
                                   rem=rem)
        if beste is None or poging["duur"] < beste["duur"]:
            beste = poging
    return beste


async def _een_meting(label: str, gedeeld: bool, parallel: int, hergebruik: bool,
                      aantal: int = AANTAL, rem: int | None = None) -> dict:
    settings = get_settings()
    settings.provider_mode = "live"   # zodat seeds en de bronreview meedraaien
    settings.research_max_parallel_companies = parallel
    # None = de rem zoals de app hem afleidt (per organisatie maal het aantal
    # organisaties). Een getal zet hem vast, en dat is hoe je het oude gedrag
    # terugkrijgt: één procesbrede semafoor die niet meegroeit.
    remgrootte = settings.crawl4ai_max_parallel if rem is None else rem

    origineel: dict = {}
    monkeys: dict = {}
    tools, reviewer = _patch(monkeys, gedeeld, hergebruik,
                             asyncio.Semaphore(remgrootte))
    for (module, attribuut), waarde in monkeys.items():
        origineel[(module, attribuut)] = getattr(module, attribuut)
        setattr(module, attribuut, waarde)
    try:
        # Schoon beginnen. Zonder dit meet de laatste meting mede de rijen van
        # alle eerdere: SQLite serialiseert schrijvers, en dan lijkt parallel
        # ineens trager. Datzelfde effect maakt deze cijfers sowieso aan de
        # voorzichtige kant — op Railway staat Postgres.
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        batch_id = _zet_klaar(label, gedeeld, aantal)
        start = time.perf_counter()
        await service.run_research_batch(batch_id)
        duur = time.perf_counter() - start
    finally:
        for (module, attribuut), waarde in origineel.items():
            setattr(module, attribuut, waarde)
        settings.provider_mode = "mock"

    return {
        "label": label, "duur": duur, "gelezen": tools.gelezen,
        "gezocht": tools.gezocht, "reviews": reviewer.reviews,
        "rem": remgrootte, "gerenderd": tools.gerenderd,
        "remwacht": tools.remwacht,
    }


async def main() -> int:
    Base.metadata.create_all(bind=engine)
    print()
    print(f"{AANTAL} vestigingen per lijst · wachttijden gedeeld door {SCHAAL}")
    print()

    kop = (f"{'scenario':<42} {'rem':>4} {'duur':>8} {'gelezen':>8} "
           f"{'wachten':>9}")
    metingen: list[tuple[str, dict]] = []

    def _regel(label: str, meting: dict) -> None:
        print(f"{label:<42} {meting['rem']:>4} {meting['duur']:>7.1f}s "
              f"{meting['gelezen']:>8} {meting['remwacht']:>8.1f}s")

    print("== losse organisaties (niets te delen) ==")
    print(kop)
    for label, parallel, rem in (
        ("serieel (oud)", 1, None),
        ("parallel x4, rem bleef op 3", 4, 3),
        ("parallel x4, rem 12 (nieuw)", 4, None),
    ):
        meting = await _meet(f"los-{parallel}-{rem}", False, parallel, True,
                             rem=rem)
        metingen.append((f"los/{label}", meting))
        _regel(label, meting)

    print()
    print("== één organisatie, veel vestigingen (vorm van Zorggroep) ==")
    print(kop)
    for label, parallel, hergebruik, rem in (
        ("serieel, alles herlezen (oud)", 1, False, None),
        ("parallel x4, alles herlezen, rem 3", 4, False, 3),
        ("parallel x4 + hergebruik, rem bleef op 3", 4, True, 3),
        ("parallel x4 + hergebruik, rem 12 (nieuw)", 4, True, None),
    ):
        meting = await _meet(f"gedeeld-{parallel}-{hergebruik}-{rem}", True,
                             parallel, hergebruik, rem=rem)
        metingen.append((f"gedeeld/{label}", meting))
        _regel(label, meting)

    print()
    print("== waar vlakt de rem af? (parallel x4, één organisatie) ==")
    print(f"{'rem':<20} {'duur':>9} {'gerenderd':>10} {'wachten':>9}")
    for omschrijving, rem in (
        ("3 (oud, vast)", 3),
        ("6", 6),
        ("12 (per org 3)", 12),
        ("24 (per org 6)", 24),
        ("onbegrensd", 10_000),
    ):
        meting = await _meet(f"rem-{rem}", True, 4, True, rem=rem)
        print(f"{omschrijving:<20} {meting['duur']:>8.1f}s "
              f"{meting['gerenderd']:>10} {meting['remwacht']:>8.1f}s")

    print()
    print("== schaalt het mee? (één organisatie, alles naast elkaar) ==")
    print(f"{'vestigingen':<20} {'duur':>9} {'gelezen':>9} {'per vestiging':>14}")
    for aantal in (12, 24, 48):
        meting = await _meet(f"schaal-{aantal}", True, 4, True, aantal=aantal)
        print(f"{aantal:<20} {meting['duur']:>8.1f}s {meting['gelezen']:>9} "
              f"{meting['duur'] / aantal:>13.2f}s")

    def _van(sleutel: str) -> dict:
        return next(m for naam, m in metingen if naam.startswith(sleutel))

    los_oud = _van("los/serieel")
    los_klem = _van("los/parallel x4, rem bleef")
    los_nieuw = _van("los/parallel x4, rem 12")
    ged_oud = _van("gedeeld/serieel")
    ged_parallel = _van("gedeeld/parallel x4, alles")
    ged_klem = _van("gedeeld/parallel x4 + hergebruik, rem bleef")
    ged_nieuw = _van("gedeeld/parallel x4 + hergebruik, rem 12")

    print()
    print("== winst ==")
    print(f"losse organisaties:        {los_oud['duur'] / los_nieuw['duur']:.1f}x sneller")
    print(f"veel vestigingen, totaal:  {ged_oud['duur'] / ged_nieuw['duur']:.1f}x sneller")
    print(f"  waarvan parallel:        {ged_oud['duur'] / ged_parallel['duur']:.1f}x")
    print(f"  waarvan hergebruik:      {ged_parallel['duur'] / ged_klem['duur']:.1f}x")
    print(f"  waarvan de rem mee:      {ged_klem['duur'] / ged_nieuw['duur']:.1f}x")
    print(f"documenten gelezen:        {ged_parallel['gelezen']} -> "
          f"{ged_nieuw['gelezen']} "
          f"({1 - ged_nieuw['gelezen'] / ged_parallel['gelezen']:.0%} minder)")
    print()
    print("== wat een vaste rem kost ==")
    print(f"losse organisaties:        {los_klem['duur'] / los_nieuw['duur']:.1f}x trager")
    print(f"veel vestigingen:          {ged_klem['duur'] / ged_nieuw['duur']:.1f}x trager")
    return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
