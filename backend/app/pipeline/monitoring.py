"""Periodieke jaarverslag-monitoring: hergebruikt de bestaande jaarverslag-agent
en reconciliatie-/confidence-logica, maar draait buiten een handmatige batch-run om."""
import asyncio
import logging
import time
from dataclasses import replace
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..models import (
    Batch, BronKandidaat, Company, JaarverslagMonitoring, PipelineRun,
    ResearchRun,
)
from ..pipeline.identity_scope import heuristic_scope_class
from ..providers import get_providers
from ..providers.base import AgentFinding
from ..research.digimv import zoek_digimv_documenten
from ..research.live_tools import LiveResearchTools
from ..research.query_planner import QueryContext
from ..research.ranking import rank_bronnen
from ..research.types import PlannedQuery
from ..research.urls import canonicaliseer_url
from ..research.urls import jaar_uit_url as _documentjaar
from ..research.validation import BronValidatie, SourceDocument, valideer_bron
from ..research.usage import get_cost_summary, start_usage_tracking
from .runner import _log as _log_stap
from .runner import _now


def _log(db, batch_id, company_id, stap, status, t0, error=None):
    """Als _log uit runner.py, maar legt ook de kosten van deze controle vast.
    Monitoring verwerkt één organisatie per aanroep, dus het totaal van de
    lopende tracking is precies de kostprijs van deze controle."""
    run = _log_stap(db, batch_id, company_id, stap, status, t0, error)
    run.kosten_cents = get_cost_summary()["totaal_cents"]
    return run

# Uitkomsten van een monitoringcontrole. Eerder viel alles hieronder onder
# "skipped", waardoor "gezocht en niets gevonden" niet te onderscheiden was van
# "bron stond al goed" — en je dus niet kon zien of het zoeken faalde.
# 'new', 'updated' en 'error' houden hun bestaande betekenis in de
# dashboard-aggregatie (routers/monitoring.py) en blijven ongemoeid.
STATUS_GEEN_BRON_GEVONDEN = "geen_bron_gevonden"
STATUS_OUDER_VERSLAG = "ouder_verslag"
STATUS_ONGEWIJZIGD = "ongewijzigd"
# De bron was al bekend, maar had nog geen beoordeelbare bronkaart. Bewust geen
# 'new' of 'updated': er is niets veranderd aan de bron zelf, dus dit mag niet
# als bevinding in de dashboardaggregatie meetellen.
STATUS_BRONKAART_TOEGEVOEGD = "bronkaart_toegevoegd"


def _mag_ouder_verslag_bewaren(document: SourceDocument) -> bool:
    """Is dit een verslag over een ouder jaar dan gevraagd, en niets ergers?

    `valideer_bron` wijst een afwijkend verslagjaar hard af. Voor de
    batchpipeline is dat juist: die zoekt gericht het verslag over één jaar.
    Monitoring stelt een andere vraag — "wat is het nieuwste dat er is?" — en
    verloor daardoor elke oudere vondst voordat die de reviewer bereikte:
    `rank_bronnen` sloeg de afgewezen bron over, waarna `_sla_moderne_bron_op`
    terugkeerde vóór het opslaan. Gemeten op de watchlist van 10-08-2026 had van
    de 26 organisaties op verslagjaar 2024 en de 13 op 2023 er 0 een
    beoordeelbare bronkaart; de URL stond alleen op de monitoringkaart.

    Alleen ouder wordt bewaard. Een verslagjaar boven het gevraagde jaar komt in
    de praktijk alleen voor als een publicatiedatum uit de URL is gelezen (DSV:
    `.../filings/3363/2026/RNS/...`); dat als verslagjaar op een bronkaart zetten
    zou een feit beweren dat we niet hebben.
    """
    return (
        document.verslagjaar is not None
        and document.gevraagd_jaar is not None
        and document.verslagjaar < document.gevraagd_jaar
    )


def _is_digimv_archiefdocument(document: SourceDocument) -> bool:
    return document.research_route == "digimv"


def _valideer_voor_monitoring(document: SourceDocument) -> BronValidatie:
    """Zelfde validatie als de batchpipeline, met twee lokale uitzonderingen.

    Beide gebeuren hier en niet in `valideer_bron`: die is gedeeld met de
    batchpipeline. Beide hebben daar ook een tegenhanger — de batchflow
    neutraliseert dezelfde twee motieven in `research/source_reviewer.py`, waar
    een LLM-reviewer de bron alsnog beoordeelt. Monitoring heeft die reviewer
    niet en moet het dus deterministisch doen.

    1. Een ouder verslagjaar blijft beoordeelbaar, met dezelfde
       waarschuwingssleutel `afwijkend_verslagjaar` als de batchflow gebruikt,
       zodat de reviewer één begrip ziet in plaats van twee. Zie
       `_mag_ouder_verslag_bewaren`.

    2. Een document uit het DigiMV-archief wordt niet afgewezen op de
       naamheuristiek. Die heuristiek zoekt de organisatienaam in titel en
       bewijsfragment, en een archiefbestand heet `Jaardocument.pdf` op
       `digimv13.desan.nl` — dus luidde het oordeel "verkeerde organisatie"
       precies zo vaak als de naam toevallig in het geciteerde zinnetje stond.
       DigiMV zelf identificeert scherper: `digimv.py::_selecteer_organisatie`
       geeft alleen documenten terug bij een exact KvK-nummer of een unieke
       exacte kernnaam, en is fail-closed bij meerdere naamgenoten.
       `source_reviewer.py` doet hetzelfde voor de gestructureerde DUO-bron.

       Bewust géén `exact_entity`: DigiMV identificeert de rechtspersoon, niet
       deze vestiging, en de watchlist heeft 0 KvK-nummers — de match loopt daar
       dus over de kernnaam. De bron gaat naar de reviewer als
       `possible_match` ("Mogelijk ander bedrijf", amber) met de identificatie
       in `validaties`, zodat er niets wordt beweerd wat we niet weten.
    """
    validatie = valideer_bron(document)
    if not validatie.is_afgewezen:
        return validatie

    resterend = list(validatie.afwijsredenen)
    waarschuwingen = list(validatie.waarschuwingen)
    validaties = dict(validatie.validaties)
    identity_class = validatie.identity_class

    if "verkeerd verslagjaar" in resterend and _mag_ouder_verslag_bewaren(document):
        resterend.remove("verkeerd verslagjaar")
        waarschuwingen.append("afwijkend_verslagjaar")
    if (
        "verkeerde organisatie" in resterend
        and _is_digimv_archiefdocument(document)
    ):
        resterend.remove("verkeerde organisatie")
        identity_class = "possible_match"
        validaties["digimv_archiefidentificatie"] = {
            "reden": "exacte organisatietreffer in het openbare DigiMV-archief",
            "heuristiek": validatie.identity_class,
        }

    # Blijft er één motief over, dan wijst de bron af zoals hij was: de
    # oorspronkelijke afwijsredenen blijven staan als reden voor de reviewer.
    if resterend:
        return validatie
    return replace(
        validatie,
        identity_class=identity_class,
        is_afgewezen=False,
        afwijsredenen=[],
        validaties=validaties,
        waarschuwingen=waarschuwingen,
    )


# Reden waarom de DigiMV-route niet is uitgevoerd; None betekent: wél gedaan.
DIGIMV_NIET_NODIG = "de jaarverslag-agent vond het verslag over het doeljaar al"
DIGIMV_ALLEEN_LIVE = "het DigiMV-archief wordt alleen in live-modus bevraagd"


def _monitoring_onderzoekspaden(
    winnende_route: str,
    digimv_statusreden: str | None,
) -> list[dict]:
    """Welke routes deze controle werkelijk heeft gelopen.

    Stond hardcoded op `["document"]`, ook toen dat het enige pad was — het
    paneel "Onderzoeksroutes" vertelde de reviewer dus altijd hetzelfde,
    ongeacht wat er gebeurde. Vorm volgt `routers/research.py::_onderzoekspaden`
    en `supervisor.py::route_statussen`, zodat monitoring- en batchruns in
    dezelfde UI hetzelfde lezen. Oude runs met tekstpaden blijven werken: die
    router zet een losse string zelf om.
    """
    return [
        {
            "route": "document",
            "verplicht": True,
            "status": "afgerond",
            "reden": "de jaarverslag-agent zoekt het nieuwste jaarverslag",
            "aantal_bronnen": 1 if winnende_route == "document" else 0,
        },
        {
            "route": "digimv",
            # Niet verplicht: een organisatie die niet in DigiMV staat levert
            # vanzelf niets op. Dat is geen technische mislukking.
            "verplicht": False,
            "status": "overgeslagen" if digimv_statusreden else "afgerond",
            "statusreden": digimv_statusreden or (
                "document uit het archief gebruikt"
                if winnende_route == "digimv"
                else "geen bruikbaar archiefdocument gevonden"
            ),
            "reden": (
                "het DigiMV-archief bevat de jaarverantwoording van "
                "zorgorganisaties"
            ),
            "aantal_bronnen": 1 if winnende_route == "digimv" else 0,
        },
    ]


def _als_agentfinding(document: SourceDocument) -> AgentFinding:
    """Een onderzocht DigiMV-document in de vorm die deze controle al kent.

    Zo hoeft de vergelijkingslogica hieronder (nieuwer verslagjaar, gewijzigde
    URL, nieuw WP-getal) niet te weten waar de bron vandaan komt.
    """
    return AgentFinding(
        wp_gevonden=document.wp_gevonden,
        context=document.bewijsfragment,
        # Monitoring rekent geen confidence uit; dit veld hoort bij het
        # AgentFinding-contract en wordt hier door niets gelezen.
        zekerheid="laag",
        reden="rechtstreeks document uit het openbare DigiMV-archief",
        bron_url=document.url,
        bron_type="jaarverslag",
        is_fte=document.eenheid == "fte",
        peilmoment=document.informatie_peilmoment,
        bron_pagina=document.bron_pagina,
        raw=document.raw_data or {},
    )


async def _zoek_digimv_document(
    company: Company,
    jaar: int,
    website_url: str | None,
) -> SourceDocument | None:
    """Het beste jaarverantwoordingsdocument uit het openbare DigiMV-archief.

    Monitoring vroeg DigiMV nooit iets: `check_company_jaarverslag` riep alleen
    de jaarverslag-agent aan. Voor zorgorganisaties is dat de sterkste
    verklaring voor de 108 van de 205 watchlist-organisaties zonder bron — hun
    jaarverantwoording staat niet op de eigen website maar in dit archief.

    Bewust alleen deze ene sectorroute en niet het hele routeplan-apparaat: een
    organisatie die niet in DigiMV staat levert vanzelf niets op, dus de lookup
    is zijn eigen sectorbepaling. Een aparte sectorbepaling zou hier ook zwak
    zijn: alle 205 organisaties missen een SBI-code en de naamfallback herkent
    er 14 van de 32 zorgorganisaties (zie `research/sector_probe.py`).
    """
    context = QueryContext(
        naam=company.naam,
        gevraagd_jaar=jaar - 1,
        website_url=website_url,
        gemeente=company.gemeente,
        huidig_jaar=jaar,
        kvk_nummer=company.kvk_nummer,
        vestigingsnummer=company.vestigingsnummer,
    )

    async def _veilig(coroutine, wat: str):
        """Een falende archiefaanroep mag de controle niet stoppen, wel opvallen."""
        try:
            return await coroutine
        except Exception as exc:
            logging.getLogger("monitoring").warning(
                "DigiMV %s mislukt voor %s (%s: %s)",
                wat, company.naam, type(exc).__name__, str(exc)[:200],
            )
            return None

    resultaten = await _veilig(
        zoek_digimv_documenten(context), "archiefzoekopdracht",
    )
    if not resultaten:
        return None

    tools = LiveResearchTools()
    onderzocht = await asyncio.gather(*[
        _veilig(
            tools.inspect(
                context,
                PlannedQuery(
                    "digimv",
                    result.queries[0],
                    "rechtstreeks document uit het openbare DigiMV-archief",
                ),
                result,
            ),
            "documentinspectie",
        )
        for result in resultaten
    ])
    documenten = [
        # Het boekjaar staat in de archief-URL (`?year=`) en is het jaar
        # waaronder DigiMV het document heeft aangeleverd gekregen. De
        # bestandsnaam noemt vaak geen jaartal, waardoor `inspect` op None
        # uitkomt — en zonder verslagjaar kan de monitoring niet zien of dit
        # verslag actueel is.
        replace(
            document,
            verslagjaar=_documentjaar(document.url) or document.verslagjaar,
        )
        for document in onderzocht if document is not None
    ]
    if not documenten:
        return None
    # Dezelfde ranking als de batchflow, zodat het document met echt WP-bewijs
    # voorgaat op de accountantsverklaring ernaast.
    ranked = rank_bronnen([
        _valideer_voor_monitoring(document) for document in documenten
    ])
    return ranked[0].document if ranked else None


def _sla_moderne_bron_op(
    db: Session,
    company: Company,
    jaar: int,
    finding,
    document: SourceDocument | None = None,
    onderzoekspaden: list[dict] | None = None,
) -> None:
    """Maak een reviewbare bronkandidaat in het canonieke bronnenmodel.

    `document` is gevuld wanneer de bron al als SourceDocument is onderzocht (de
    DigiMV-route). Dan houdt de bron zijn eigen brontype en concern-scope, in
    plaats van hier opnieuw als website-jaarverslag te worden opgebouwd.
    """
    gevraagd_jaar = jaar - 1
    if document is None:
        titel = unquote(PurePosixPath(urlsplit(finding.bron_url).path).name)
        document = SourceDocument(
            naam=company.naam,
            company_website_url=(
                (company.enrichment.website_url if company.enrichment else None)
                or company.website_url
            ),
            url=finding.bron_url,
            titel=titel or "Gevonden jaarverslag",
            brontype="jaarverslag",
            documenttype="jaarverslag",
            gevraagd_jaar=gevraagd_jaar,
            verslagjaar=_documentjaar(finding.bron_url),
            informatie_peilmoment=finding.peilmoment,
            wp_gevonden=finding.wp_gevonden,
            eenheid=(
                "fte" if finding.is_fte
                else "werkzame_personen"
                if finding.wp_gevonden is not None
                else None
            ),
            bewijsfragment=finding.context,
            bron_pagina=finding.bron_pagina,
            scope_class=heuristic_scope_class(
                finding.is_limburg_specifiek,
                "jaarverslag",
            ),
            # De extractievlaggen horen bij het document, want `valideer_bron`
            # leest hieruit of het getal uit een namenlijst is geteld. Zonder dit
            # bleef `draag_naamlijsttelling_over_aan_reviewer` uit en kwam een
            # telling uit een namenlijst als hard WP-getal op de kaart: Stichting
            # Dichterbij kreeg zo 16 werkzame personen uit de samenstelling van
            # de ondernemingsraad.
            raw_data=finding.raw or None,
        )
    ranked = rank_bronnen([_valideer_voor_monitoring(document)])
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="periodieke jaarverslagmonitoring",
        gevraagd_jaar=gevraagd_jaar,
        status="completed",
        resultaat_status="review_nodig" if ranked else "niet_gevonden",
        onderzoekspaden=(
            onderzoekspaden
            or _monitoring_onderzoekspaden("document", DIGIMV_NIET_NODIG)
        ),
        configuratie={"bron": "jaarverslag_monitoring"},
        started_at=_now(),
        completed_at=_now(),
    )
    db.add(run)
    db.flush()
    if not ranked:
        return
    bron = ranked[0]
    # Het document zoals de validatie het achterlaat, niet zoals het erin ging.
    # `draag_naamlijsttelling_over_aan_reviewer` trekt een telling uit een
    # namenlijst in door het getal uit het document te halen; die correctie zat
    # in `bron.document` en werd hier overschreven door het origineel. Zolang
    # monitoring `raw_data` niet meestuurde kon dat niet misgaan — sinds de
    # WP-extractie wel.
    bewijs = bron.document
    db.add(BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url=bewijs.url,
        canonical_url=canonicaliseer_url(bewijs.url),
        titel=bewijs.titel,
        brontype=bewijs.brontype,
        documenttype=bewijs.documenttype,
        verslagjaar=bewijs.verslagjaar,
        informatie_peilmoment=bewijs.informatie_peilmoment,
        wp_gevonden=bewijs.wp_gevonden,
        eenheid=bewijs.eenheid,
        bewijsfragment=bewijs.bewijsfragment,
        bron_pagina=bewijs.bron_pagina,
        identity_class=bron.identity_class,
        scope_class=bewijs.scope_class,
        autoriteit_score=bron.score_breakdown["autoriteit"],
        actualiteit_score=bron.score_breakdown["actualiteit"],
        identiteit_score=bron.score_breakdown["identiteit"],
        relevantie_score=bron.score_breakdown["relevantie"],
        ranking_score=bron.ranking_score,
        score_breakdown=bron.score_breakdown,
        validaties=bron.validaties,
        waarschuwingen=bron.waarschuwingen,
        # Een al onderzocht document (DigiMV) draagt zijn eigen herkomst mee;
        # bij de agentroute staat die alleen in de finding.
        raw_data=bewijs.raw_data or (finding.raw if finding else None) or None,
        status="voorgesteld",
        rang=1,
    ))


def _trek_afgewezen_bron_in(
    db: Session,
    company: Company,
    afgewezen_url: str,
) -> None:
    canonical = canonicaliseer_url(afgewezen_url)
    for bron in db.query(BronKandidaat).filter(
        BronKandidaat.company_id == company.id,
        BronKandidaat.canonical_url == canonical,
        BronKandidaat.status != "afgewezen",
    ):
        bron.status = "afgewezen"
        bron.review_reason_code = "bron_niet_toegankelijk"
        bron.review_reason = "Automatisch ingetrokken bij hervalidatie"


def _beste_moderne_jaarverslagbron(
    db: Session,
    company: Company,
    jaar: int,
) -> tuple[int, BronKandidaat] | None:
    """De nieuwste bruikbare jaarverslagkandidaat, met zijn afgeleide verslagjaar."""
    kandidaten = (
        db.query(BronKandidaat)
        .filter(
            BronKandidaat.company_id == company.id,
            BronKandidaat.brontype == "jaarverslag",
            BronKandidaat.status != "afgewezen",
        )
        .order_by(BronKandidaat.created_at.desc())
        .all()
    )
    geldig: list[tuple[int, BronKandidaat]] = []
    for kandidaat in kandidaten:
        # Alleen een aantoonbaar URL-jaar is veilig genoeg voor automatisch
        # herstel. Oude records konden gevraagd_jaar als verslagjaar opslaan,
        # zelfs bij een privacy- of ander fout document.
        werkelijk_jaar = _documentjaar(kandidaat.url)
        if werkelijk_jaar is None or not jaar - 3 <= werkelijk_jaar <= jaar - 1:
            continue
        geldig.append((werkelijk_jaar, kandidaat))
    if not geldig:
        return None
    # Het afgeleide jaar wordt níet op de kandidaat teruggeschreven. Deze query
    # ziet ook kandidaten van de researchflow, en die dragen een `verslagjaar`
    # dat verweven is met hun `relevantie_score`, `ranking_score` en
    # `validaties["verslagjaar_match"]`. Alleen dat ene veld overschrijven levert
    # een bronkaart op die zichzelf tegenspreekt: jaartal 2024 naast een score
    # die een exacte treffer op 2025 beloofde. Monitoring gebruikt het afgeleide
    # jaar dus alleen om te kiezen en om zijn eigen status te vullen.
    return max(geldig, key=lambda item: item[0])


async def _lees_wp_uit_document(jaarverslag_agent, company_naam: str, finding):
    """Haal het WP-getal uit een gevonden jaarverslag, als dat er nog niet is.

    `find_latest_source` zoekt en valideert alleen de bron — zijn docstring zegt
    het letterlijk: "monitoring hoeft geen WP-extractie". Dat klopte toen
    monitoring niets anders deed dan een URL bijhouden. Sinds monitoring
    beoordeelbare bronkandidaten aanmaakt, is dat een halve bronkaart: gemeten op
    17-08-2026 leverde de documentroute 25 kaarten op met 0 WP-getallen, terwijl
    de DigiMV-route (die wél door `inspect` gaat) er 8 van de 14 vulde. De
    reviewer moest die 25 PDF's zelf openen.

    Dezelfde extractie als de DigiMV-route dus: `run_met_bron` van de
    jaarverslag-agent. Kost ongeveer 1 cent per document en geen enkele
    zoekopdracht — de URL is al bekend.

    Een bestaand getal wordt nooit overschreven, en een mislukte extractie laat
    de bron gewoon staan zoals hij was.
    """
    if finding is None or finding.wp_gevonden is not None or not finding.bron_url:
        return finding
    extractor = getattr(type(jaarverslag_agent), "run_met_bron", None)
    if extractor is None:
        return finding
    try:
        # De naam gaat mee: `run_met_bron` geeft die aan de extractie, en een
        # jaarverslag van een concern noemt meerdere organisaties.
        gelezen = await jaarverslag_agent.run_met_bron(
            company_naam, finding.bron_url,
        )
    except Exception as exc:
        logging.getLogger("monitoring").warning(
            "WP-extractie mislukt voor %s (%s: %s)",
            finding.bron_url, type(exc).__name__, str(exc)[:200],
        )
        return finding
    if gelezen is None or gelezen.wp_gevonden is None:
        return finding
    return replace(
        finding,
        wp_gevonden=gelezen.wp_gevonden,
        context=gelezen.context,
        is_fte=gelezen.is_fte,
        peilmoment=gelezen.peilmoment,
        bron_pagina=gelezen.bron_pagina,
        is_limburg_specifiek=(
            finding.is_limburg_specifiek
            if finding.is_limburg_specifiek is not None
            else gelezen.is_limburg_specifiek
        ),
        # De extractievlaggen meenemen, want `valideer_bron` leest hieruit of het
        # getal uit een namenlijst komt. Zonder dat blijft de telopdracht-regel
        # uit: Stichting Dichterbij kreeg zo `wp = 16` uit de samenstelling van
        # de ondernemingsraad, met een citaat dat zelfverzekerd leest.
        raw={**(finding.raw or {}), **(gelezen.raw or {})},
    )


def _heeft_al_een_bronkaart(
    db: Session,
    company: Company,
    bron_url: str,
) -> bool:
    """Bestaat er al een beoordeelbare bronkandidaat voor deze URL?

    "Ongewijzigd" betekende: de agent vond dezelfde URL en geen nieuw WP-getal.
    Daarmee sloeg de controle het opslaan over, óók als er nog nooit een
    bronkandidaat voor die URL was aangemaakt. Gemeten op de watchlist van
    17-08-2026: 66 van de 205 organisaties hebben een bekende bron-URL en 0
    bronkandidaten — inclusief organisaties die al op verslagjaar 2025 staan.
    Die kregen nooit een bronkaart, want hun URL verandert niet meer.

    Een afgewezen kandidaat telt mee: de reviewer heeft die bron dan gezien en
    beoordeeld, en hoort hem niet elke ronde opnieuw voorgeschoteld te krijgen.
    """
    return db.query(
        db.query(BronKandidaat)
        .filter(
            BronKandidaat.company_id == company.id,
            BronKandidaat.canonical_url == canonicaliseer_url(bron_url),
        )
        .exists()
    ).scalar()


def _wp_is_nieuw_voor_bron(
    db: Session,
    company: Company,
    bron_url: str,
    wp_gevonden: int | None,
) -> bool:
    if wp_gevonden is None:
        return False
    bestaande_bron = (
        db.query(BronKandidaat)
        .filter(
            BronKandidaat.company_id == company.id,
            BronKandidaat.canonical_url == canonicaliseer_url(bron_url),
        )
        .order_by(BronKandidaat.created_at.desc())
        .first()
    )
    if bestaande_bron is None:
        return True
    return bestaande_bron.wp_gevonden != wp_gevonden


async def check_company_jaarverslag(db: Session, company: Company, jaar: int) -> bool:
    """Controleert of er een nieuw jaarverslag is t.o.v. de laatst bekende bron.
    De laatst bekende bron_url wordt bijgewerkt zodra de agent er één vindt, ook
    als er geen WP-getal uit te halen was — zo houdt de monitoring altijd een
    actuele link naar het meest recente jaarverslag bij. Uitzondering: een vondst
    zonder herkenbaar verslagjaar verdringt geen gedateerde baseline, want dan
    zou het bekende jaartal verdwijnen. Een candidate wordt alleen
    aangemaakt/bijgewerkt als er zowel een nieuwe URL als een bruikbaar WP-getal is.
    Retourneert True als er een wijziging is vastgesteld (nieuwe URL, met of zonder
    WP-getal)."""
    lookup, _, jaarverslag_agent, _ = get_providers()
    # Zonder dit blijft de tokenteller leeg en logt _log() alleen nullen, waardoor
    # een monitoringronde geen meetbare kosten heeft.
    start_usage_tracking()
    t0 = time.monotonic()

    status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one_or_none()
    if status is None:
        status = JaarverslagMonitoring(company_id=company.id)
        db.add(status)

    beste_moderne = _beste_moderne_jaarverslagbron(db, company, jaar)
    if beste_moderne is not None:
        beste_jaar, beste_bron = beste_moderne
        if (
            status.laatste_verslagjaar
            or _documentjaar(status.laatste_bron_url)
            or 0
        ) < beste_jaar:
            status.laatste_bron_url = beste_bron.url
            status.laatste_verslagjaar = beste_jaar

    website_url = (company.enrichment.website_url if company.enrichment else None) or company.website_url
    if not website_url and lookup is not None:
        try:
            locatiehint = company.gemeente or company.adres or "Nederland"
            place = await lookup.lookup(company.naam, locatiehint)
            website_url = place.website if place else None
            if website_url:
                company.website_url = website_url
        except Exception:
            website_url = None

    te_valideren_url = status.laatste_bron_url
    source_finder = getattr(type(jaarverslag_agent), "find_latest_source", None)
    if source_finder is not None:
        finding = await jaarverslag_agent.find_latest_source(
            company.naam,
            jaar,
            website_url=website_url,
            strict_identity=True,
        )
    else:
        finding = await jaarverslag_agent.run(
            company.naam,
            jaar,
            website_url=website_url,
            strict_identity=True,
        )
    status.laatst_gecontroleerd_op = _now()

    bestaand_jaar = (
        status.laatste_verslagjaar
        or _documentjaar(te_valideren_url)
    )
    gevonden_jaar = (
        (finding.raw or {}).get("verslagjaar")
        or _documentjaar(finding.bron_url)
        if finding and finding.bron_url
        else None
    )

    # DigiMV hangt ná de jaarverslag-agent en niet ernaast: het is een
    # aanvulling voor wanneer de gewone route geen verslag over het doeljaar
    # vindt. Draait de agent al binnen, dan kost een archiefaanroep alleen
    # tijd en tokens.
    digimv_document = None
    digimv_statusreden = DIGIMV_NIET_NODIG
    if gevonden_jaar is None or gevonden_jaar < jaar - 1:
        if get_settings().provider_mode == "live":
            digimv_statusreden = None
            digimv_document = await _zoek_digimv_document(
                company, jaar, website_url,
            )
        else:
            # Er is geen mockprovider voor het DigiMV-archief; net als de
            # seedbronnen in `research/service.py` draait deze route daarom
            # alleen live.
            digimv_statusreden = DIGIMV_ALLEEN_LIVE
    if digimv_document is not None:
        # `_zoek_digimv_document` heeft het boekjaar al uit de archief-URL
        # gehaald; hier niet opnieuw afleiden, anders kunnen de bronkaart en de
        # monitoringstatus een ander jaartal tonen voor hetzelfde document.
        digimv_jaar = digimv_document.verslagjaar or 0
        agent_jaar = gevonden_jaar or 0
        # Gelijkspel op jaartal gaat naar DigiMV zodra alleen dáár een WP-getal
        # uit komt: de jaarverantwoording is het document dat het aantal
        # werkzame personen bevat, en dat is de reden om deze route te lopen.
        if digimv_jaar > agent_jaar or (
            digimv_jaar == agent_jaar
            and digimv_document.wp_gevonden is not None
            and (finding is None or finding.wp_gevonden is None)
        ):
            finding = _als_agentfinding(digimv_document)
            gevonden_jaar = digimv_jaar or None
        else:
            digimv_document = None

    zelfde_gevalideerde_bron = bool(
        finding
        and finding.bron_url
        and te_valideren_url
        and canonicaliseer_url(finding.bron_url)
        == canonicaliseer_url(te_valideren_url)
    )
    baseline_moet_worden_gevalideerd = bool(
        te_valideren_url
        and not zelfde_gevalideerde_bron
        and (
            finding is None
            or not finding.bron_url
            or gevonden_jaar is None
            or bestaand_jaar is None
            or gevonden_jaar < bestaand_jaar
        )
    )
    baseline_ingetrokken = False
    validator = getattr(type(jaarverslag_agent), "validate_source", None)
    if baseline_moet_worden_gevalideerd and validator is not None:
        bron_is_nog_geldig = await jaarverslag_agent.validate_source(
            company.naam,
            jaar,
            te_valideren_url,
            website_url=website_url,
            strict_identity=True,
        )
        if not bron_is_nog_geldig:
            status.laatste_bron_url = None
            status.laatste_verslagjaar = None
            bestaand_jaar = None
            _trek_afgewezen_bron_in(
                db,
                company,
                te_valideren_url,
            )
            baseline_ingetrokken = True
        elif not status.laatste_bron_url:
            status.laatste_bron_url = te_valideren_url
        if bron_is_nog_geldig and bestaand_jaar is not None:
            status.laatste_verslagjaar = bestaand_jaar
    elif zelfde_gevalideerde_bron and not status.laatste_bron_url:
        status.laatste_bron_url = te_valideren_url

    if finding is None or not finding.bron_url:
        if baseline_ingetrokken:
            _log(
                db,
                company.batch_id,
                company.id,
                "jaarverslag_monitoring",
                "updated",
                t0,
                error="legacy-baseline afgewezen door huidige validatie",
            )
            db.commit()
            return True
        _log(db, company.batch_id, company.id, "jaarverslag_monitoring",
             STATUS_GEEN_BRON_GEVONDEN, t0)
        db.commit()
        return False

    if (
        bestaand_jaar is not None
        and gevonden_jaar is not None
        and gevonden_jaar < bestaand_jaar
    ):
        _log(
            db,
            company.batch_id,
            company.id,
            "jaarverslag_monitoring",
            STATUS_OUDER_VERSLAG,
            t0,
            error=(
                f"ouder verslag genegeerd: {gevonden_jaar} < {bestaand_jaar}"
            ),
        )
        db.commit()
        return False

    url_gewijzigd = (
        canonicaliseer_url(finding.bron_url)
        != canonicaliseer_url(status.laatste_bron_url or "")
    )
    eerste_bron = not status.laatste_bron_url
    verslag_is_nieuw = (
        eerste_bron
        or (
            gevonden_jaar is not None
            and bestaand_jaar is not None
            and gevonden_jaar > bestaand_jaar
        )
        or (
            gevonden_jaar is None
            and bestaand_jaar is None
            and url_gewijzigd
        )
    )
    # Een vondst zonder herkenbaar verslagjaar mag een gedateerde baseline niet
    # verdringen. De check hierboven vangt alleen een aantoonbaar ouder jaar op;
    # bij `gevonden_jaar is None` liep de controle daar zo langs, waarna deze
    # regels het jaartal op None zetten. Een organisatie met het verslag over
    # 2025 zakte daardoor stil terug naar "verslag zonder jaartal" en de goede
    # URL was weg. Zulke jaarloze overzichtspagina's zijn geen randgeval: op de
    # watchlist van 10-08-2026 staan er 3 met een URL zonder jaartal.
    # De vondst zelf gaat hieronder gewoon als bronkandidaat naar de reviewer.
    if gevonden_jaar is not None or bestaand_jaar is None:
        status.laatste_bron_url = finding.bron_url
        status.laatste_verslagjaar = gevonden_jaar

    wp_is_nieuw = _wp_is_nieuw_voor_bron(
        db,
        company,
        finding.bron_url,
        finding.wp_gevonden,
    )
    alleen_bronkaart_ontbreekt = (
        not url_gewijzigd
        and not wp_is_nieuw
        and not _heeft_al_een_bronkaart(db, company, finding.bron_url)
    )
    if not url_gewijzigd and not wp_is_nieuw and not alleen_bronkaart_ontbreekt:
        _log(db, company.batch_id, company.id, "jaarverslag_monitoring",
             STATUS_ONGEWIJZIGD, t0)
        db.commit()
        return False

    wijzigingsstatus = (
        STATUS_BRONKAART_TOEGEVOEGD if alleen_bronkaart_ontbreekt
        else "new" if verslag_is_nieuw
        else "updated"
    )

    # Pas hier, en niet eerder: we weten nu dat er echt een bronkaart komt, dus
    # betalen we de extractie alleen als de reviewer er iets aan heeft.
    if digimv_document is None:
        finding = await _lees_wp_uit_document(
            jaarverslag_agent, company.naam, finding,
        )

    _sla_moderne_bron_op(
        db,
        company,
        jaar,
        finding,
        document=digimv_document,
        onderzoekspaden=_monitoring_onderzoekspaden(
            "digimv" if digimv_document is not None else "document",
            digimv_statusreden,
        ),
    )

    _log(
        db,
        company.batch_id,
        company.id,
        "jaarverslag_monitoring",
        wijzigingsstatus,
        t0,
    )
    db.commit()
    # Een toegevoegde bronkaart is geen wijziging van de bron zelf; de
    # organisatie hoort niet als "gewijzigd sinds de vorige controle" te tonen.
    return wijzigingsstatus != STATUS_BRONKAART_TOEGEVOEGD


async def _check_company_met_eigen_sessie(batch_id: str, company_id: str, jaar: int,
                                          semaphore: asyncio.Semaphore) -> None:
    """Verwerkt één organisatie met een eigen databasesessie, zodat meerdere
    organisaties veilig gelijktijdig verwerkt kunnen worden (een SQLAlchemy
    Session mag niet door meerdere gelijktijdige taken gedeeld worden)."""
    async with semaphore:
        t0 = time.monotonic()
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if company is None:
                return
            await asyncio.wait_for(
                check_company_jaarverslag(db, company, jaar),
                timeout=get_settings().research_company_timeout_seconds,
            )
        except TimeoutError:
            db.rollback()
            db.add(PipelineRun(
                batch_id=batch_id,
                company_id=company_id,
                stap="jaarverslag_monitoring",
                status="error",
                duur_ms=int((time.monotonic() - t0) * 1000),
                error=(
                    "jaarverslagcontrole afgebroken na "
                    f"{get_settings().research_company_timeout_seconds} seconden"
                ),
            ))
            db.commit()
        except Exception as exc:
            try:
                db.rollback()
                db.add(PipelineRun(batch_id=batch_id, company_id=company_id,
                                   stap="jaarverslag_monitoring", status="error",
                                   duur_ms=int((time.monotonic() - t0) * 1000),
                                   error=str(exc)[:1000]))
                db.commit()
            except Exception:
                logging.getLogger("monitoring").exception(
                    "Kon jaarverslag_monitoring-fout niet loggen voor company_id=%s "
                    "(oorspronkelijke fout: %s)", company_id, exc)
        finally:
            db.close()


async def check_batch_jaarverslagen(batch_id: str, jaar: int, company_ids: list[str],
                                    max_concurrent: int = 8) -> None:
    """Controleert alle opgegeven organisaties op nieuwe jaarverslagen, met ten
    hoogste max_concurrent gelijktijdige controles."""
    semaphore = asyncio.Semaphore(max_concurrent)
    await asyncio.gather(*(
        _check_company_met_eigen_sessie(batch_id, company_id, jaar, semaphore)
        for company_id in company_ids
    ))


def _heeft_doeljaar_al(status: JaarverslagMonitoring | None, doeljaar: int) -> bool:
    """Is het verslag over het doeljaar al binnen?

    Een jaarverslag over jaar X verschijnt pas in X+1, dus zodra het verslag
    over `doeljaar` er is, kan een volgende ronde er niets nieuwers vinden.
    Opnieuw zoeken kost dan alleen zoek- en modeltokens. Van de watchlist van
    10-08-2026 had 51 van de 205 organisaties het verslag over 2025 al; die
    zijn in elke daaropvolgende ronde tevergeefs opnieuw doorzocht.

    `>=` en niet `==`: een hoger opgeslagen jaartal komt in de praktijk alleen
    voor als een publicatiedatum als verslagjaar is gelezen, en ook dan valt
    er niets nieuwers te halen.
    """
    return bool(
        status
        and status.laatste_bron_url
        and status.laatste_verslagjaar is not None
        and status.laatste_verslagjaar >= doeljaar
    )


def bepaal_over_te_slaan_companies(
    db: Session,
    batch: Batch,
    doeljaar: int,
) -> set[str]:
    """Welke organisaties deze ronde niets nieuws kunnen opleveren.

    Het verslag over het doeljaar hebben is niet genoeg: er moet ook een
    beoordeelbare bronkandidaat zijn. Zonder die tweede eis sloot deze
    optimalisatie precies de organisaties uit die nog een bronkaart missen — op
    de watchlist van 17-08-2026 hebben 66 van de 205 een bekende bron-URL en 0
    kandidaten, en een deel daarvan staat al op verslagjaar 2025. Die zouden dan
    nooit meer aan de beurt komen, want hun URL verandert niet meer.

    Eén plek voor dit begrip, zodat de teller in `routers/monitoring.py` en de
    werkelijke ronde niet uit elkaar kunnen lopen.
    """
    met_kandidaat = {
        company_id
        for (company_id,) in (
            db.query(BronKandidaat.company_id)
            .join(Company, Company.id == BronKandidaat.company_id)
            .filter(Company.batch_id == batch.id)
            .distinct()
        )
    }
    return {
        status.company_id
        for status in (
            db.query(JaarverslagMonitoring)
            .join(Company, Company.id == JaarverslagMonitoring.company_id)
            .filter(Company.batch_id == batch.id)
        )
        if _heeft_doeljaar_al(status, doeljaar)
        and status.company_id in met_kandidaat
    }


def run_monitoring_watchlist_background(
    limit: int | None = None,
    offset: int = 0,
    hercontroleer_actuele: bool = False,
) -> None:
    """Zoekt de gemarkeerde watchlist-batch op (Batch.is_monitoringlijst=True) en
    controleert alle organisaties daarin gelijktijdig op nieuwe jaarverslagen.
    Geen watchlist ingesteld of leeg -> stille no-op.
    limit beperkt (optioneel) het aantal gecontroleerde organisaties — bedoeld
    om tijdens testen/ontwikkelen niet steeds de volledige, live-kostbare
    watchlist te hoeven doorlopen.

    Organisaties waarvan het verslag over het doeljaar al binnen is, worden
    overgeslagen; `hercontroleer_actuele=True` doorzoekt ze alsnog."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter_by(is_monitoringlijst=True).order_by(
            Batch.created_at.desc()).first()
        if batch is None:
            return
        batch_id, jaar = batch.id, batch.jaar
        doeljaar = jaar - 1
        al_actueel: set[str] = set()
        if not hercontroleer_actuele:
            al_actueel = bepaal_over_te_slaan_companies(db, batch, doeljaar)
        company_ids = [
            company_id
            for (company_id,) in (
                db.query(Company.id)
                .filter_by(batch_id=batch.id)
                .order_by(Company.created_at, Company.id)
                .all()
            )
            if company_id not in al_actueel
        ]
    finally:
        db.close()

    company_ids = company_ids[offset:]
    if limit is not None:
        company_ids = company_ids[:limit]
    if not company_ids:
        return
    asyncio.run(check_batch_jaarverslagen(batch_id, jaar, company_ids))
