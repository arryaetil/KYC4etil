"""Dashboard-niveau jaarverslag-monitoring: werkt altijd op de ene actieve
watchlist (Batch.is_monitoringlijst=True), zonder batch_id in de URL."""
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from .. import documenten
from ..database import get_db
from ..models import (
    Batch, BronKandidaat, Company, JaarverslagMonitoring, PipelineRun,
)
from ..pipeline.identity_scope import heuristic_scope_class
from ..pipeline.monitoring import (
    bepaal_over_te_slaan_companies, run_monitoring_watchlist_background,
)
from ..providers import jaarverslag as jaarverslag_provider
from ..research.losse_bron import gevraagd_jaar_van, maak_kandidaat
from ..research.urls import canonicaliseer_url, jaar_uit_url
from ..research.validation import SourceDocument
from .research import _candidate_dict

router = APIRouter(prefix="/monitoring", tags=["monitoring"], dependencies=[Depends(get_current_user)])


def _actieve_watchlist(db: Session) -> Batch | None:
    return (db.query(Batch).filter_by(is_monitoringlijst=True)
            .order_by(Batch.created_at.desc()).first())


def _jaarstatus(
    doeljaar: int | None,
    verslagjaar: int | None,
    bron_url: str | None,
) -> str:
    """Waar staat deze organisatie ten opzichte van het gevraagde verslagjaar?

    Dit is de vraag die de monitoring moet beantwoorden: van hoeveel
    organisaties hebben we het verslag over `doeljaar`, van hoeveel alleen een
    ouder verslag, en van hoeveel niets. `nieuwe_bevinding` beantwoordde die
    vraag niet — dat is een delta ten opzichte van de vorige controleronde.
    Gemeten op de watchlist van 10-08-2026 stonden de enige twee organisaties
    met die markering allebei op verslagjaar 2023, terwijl de 51 organisaties
    mét een verslag over 2025 geen enkel signaal kregen.

    `>= doeljaar` en niet `== doeljaar`: een verslag dat nieuwer is dan
    gevraagd is in geen geval verouderd. In de praktijk komt dat alleen voor
    bij een URL waarin een publicatiedatum als verslagjaar wordt gelezen
    (DSV: `.../filings/3363/2026/RNS/3363_rns_2026-02-04_...`). Zo'n geval
    blijft zichtbaar in `jaren_verdeling` in plaats van als "verouderd" in de
    verkeerde bak te vallen.
    """
    if not bron_url:
        return "ontbreekt"
    if doeljaar is None or verslagjaar is None:
        return "verouderd"
    return "actueel" if verslagjaar >= doeljaar else "verouderd"


def _bronkandidaat_per_company(
    db: Session,
    bron_per_company: dict[str, str],
) -> dict[str, dict]:
    """Zoekt bij elke monitoringbron de bijbehorende bronkandidaat op.

    De monitoringronde bewaart op JaarverslagMonitoring alleen de URL, maar legt
    álles wat ze uit het verslag las vast op de BronKandidaat die ze in dezelfde
    transactie aanmaakt: het WP-getal, het citaat, het paginanummer, de scope.
    Die stonden hier niet in de respons, dus de monitoringkaart kon alleen een
    link tonen terwijl het cijfer al bekend was.

    Vergelijking gaat over de canonieke URL: de monitoring en de kandidaat
    kunnen dezelfde bron met een andere querystring of trailing slash hebben.

    De vorm komt uit `_candidate_dict` van de onderzoeksmodule — dezelfde velden,
    zodat de monitoringkaart dezelfde samenvatting kan tonen als de bronnenlijst
    in plaats van een tweede variant die stilzwijgend uiteenloopt.
    """
    if not bron_per_company:
        return {}

    canoniek = {cid: canonicaliseer_url(url) for cid, url in bron_per_company.items()}
    company_ids = list(bron_per_company)
    gevonden: dict[str, dict] = {}

    # Oplopend op created_at zodat de nieuwste vondst de oudere overschrijft.
    for kandidaat in (db.query(BronKandidaat)
                      .filter(BronKandidaat.company_id.in_(company_ids))
                      .order_by(BronKandidaat.created_at)):
        doel = canoniek.get(kandidaat.company_id)
        bron = kandidaat.canonical_url or canonicaliseer_url(kandidaat.url or "")
        if doel and bron == doel:
            gevonden[kandidaat.company_id] = _candidate_dict(kandidaat)

    return gevonden


@router.get("")
def monitoring_status(db: Session = Depends(get_db)):
    """Status van de actieve jaarverslag-watchlist. batch=null als er nog geen is ingesteld."""
    batch = _actieve_watchlist(db)
    if batch is None:
        return {"batch": None, "doeljaar": None, "totaal": 0, "gecontroleerd": 0,
                "bronnen_gevonden": 0, "bronnen_ontbreken": 0,
                "actueel": 0, "verouderd": 0, "ontbreekt": 0,
                "overgeslagen_actueel": 0, "te_controleren": 0,
                "jaren_verdeling": [],
                "nieuwe_bevindingen": 0, "fouten": 0, "companies": []}

    companies = db.query(Company).filter_by(batch_id=batch.id).all()
    company_ids = [c.id for c in companies]

    status_map: dict[str, JaarverslagMonitoring] = {}
    if company_ids:
        for status in (db.query(JaarverslagMonitoring)
                       .filter(JaarverslagMonitoring.company_id.in_(company_ids))):
            status_map[status.company_id] = status

    bevindingen: set[str] = set()
    fouten_map: dict[str, str] = {}
    if company_ids:
        laatste_status: dict[str, PipelineRun] = {}
        for pr in (db.query(PipelineRun)
                   .filter(PipelineRun.company_id.in_(company_ids),
                           PipelineRun.stap == "jaarverslag_monitoring")
                   .order_by(PipelineRun.created_at)):
            laatste_status[pr.company_id] = pr
        for pr in laatste_status.values():
            # Bewust alléén 'new'. 'updated' is een betere extractie op dezelfde
            # URL en 'bronkaart_toegevoegd' een reeds bekende bron die alsnog
            # beoordeelbaar werd; geen van beide is een nieuw jaarverslag. Zie
            # test_monitoring_dashboard_noemt_betere_extractie_geen_nieuw_jaarverslag.
            if pr.status == "new":
                bevindingen.add(pr.company_id)
            elif pr.status == "error":
                fouten_map[pr.company_id] = pr.error or "onbekende fout"

    kandidaat_per_company = _bronkandidaat_per_company(db, {
        cid: status.laatste_bron_url
        for cid, status in status_map.items()
        if status.laatste_bron_url
    })

    # Het verslagjaar waar deze ronde om draait. `batch.jaar` is het lopende
    # jaar van de watchlist; een jaarverslag over jaar X verschijnt pas in
    # X+1, dus het nieuwste verslag dat kán bestaan is dat over jaar-1.
    # Dezelfde afleiding als `pipeline/monitoring.py::_sla_moderne_bron_op`
    # en als de onderzoeksmodule (`KandidatenPaneel`: batchJaar - 1).
    doeljaar = batch.jaar - 1 if batch.jaar is not None else None

    out = []
    for comp in companies:
        status = status_map.get(comp.id)
        kandidaat = kandidaat_per_company.get(comp.id)
        pagina = kandidaat.get("bron_pagina") if kandidaat else None
        fragment = kandidaat.get("bewijsfragment") if kandidaat else None
        bron_url = status.laatste_bron_url if status else None
        verslagjaar = status.laatste_verslagjaar if status else None
        out.append({
            "company_id": comp.id, "naam": comp.naam, "gemeente": comp.gemeente,
            "laatst_gecontroleerd_op": (status.laatst_gecontroleerd_op.isoformat() + "Z"
                                        if status and status.laatst_gecontroleerd_op else None),
            "laatste_bron_url": bron_url,
            "verslagjaar": verslagjaar,
            # Vindplaats van het WP-getal, zodat de viewer op de juiste pagina
            # opent en het cijfer markeert in plaats van op pagina 1 te beginnen.
            "bron_pagina": pagina,
            "bewijsfragment": fragment,
            # De volledige kandidaat, zodat de monitoringkaart het WP-getal en
            # dezelfde samenvatting kan tonen als de bronnenlijst.
            "bron": kandidaat,
            "bron_status": "gevonden" if bron_url else "ontbreekt",
            "doeljaar": doeljaar,
            "jaarstatus": _jaarstatus(doeljaar, verslagjaar, bron_url),
            # Blijft bestaan, maar is niet langer de hoofdstatus: dit zegt
            # "veranderd sinds de vorige controle", niet "actueel".
            "nieuwe_bevinding": comp.id in bevindingen,
            "fout": fouten_map.get(comp.id),
        })

    # Wat een volgende ronde zou doen, vóórdat iemand erop klikt. Deze regel
    # bestond al — organisaties met het verslag over het doeljaar én een
    # beoordeelbare kaart worden overgeslagen — maar was pas te zien in de
    # bevestiging ná het starten. Wie 205 organisaties in de lijst ziet staan
    # gaat er redelijkerwijs van uit dat hij er 205 gaat controleren.
    overgeslagen = (
        len(bepaal_over_te_slaan_companies(db, batch, doeljaar))
        if doeljaar is not None else 0
    )

    gecontroleerd = sum(1 for c in out if c["laatst_gecontroleerd_op"])
    bronnen_gevonden = sum(1 for c in out if c["laatste_bron_url"])
    jaarstatussen = Counter(c["jaarstatus"] for c in out)
    # Aflopend op jaar, met de organisaties zonder herkenbaar jaartal
    # achteraan: zo staat het doeljaar altijd bovenaan de verdeling.
    jaren = Counter(
        c["verslagjaar"] for c in out if c["laatste_bron_url"]
    )
    jaren_verdeling = [
        {"verslagjaar": jaar, "aantal": jaren[jaar]}
        for jaar in sorted(
            jaren, key=lambda jaar: (jaar is not None, jaar or 0), reverse=True,
        )
    ]
    return {
        "batch": {"id": batch.id, "naam": batch.naam, "jaar": batch.jaar},
        "doeljaar": doeljaar,
        "totaal": len(companies),
        "gecontroleerd": gecontroleerd,
        "bronnen_gevonden": bronnen_gevonden,
        "bronnen_ontbreken": len(companies) - bronnen_gevonden,
        "actueel": jaarstatussen["actueel"],
        "verouderd": jaarstatussen["verouderd"],
        "ontbreekt": jaarstatussen["ontbreekt"],
        # Wat "Nu controleren" deze ronde zou doen, zodat het scherm dat kan
        # zeggen in plaats van het totaal te suggereren.
        "overgeslagen_actueel": overgeslagen,
        "te_controleren": max(0, len(companies) - overgeslagen),
        "jaren_verdeling": jaren_verdeling,
        "nieuwe_bevindingen": len(bevindingen),
        "fouten": len(fouten_map),
        "companies": out,
    }


@router.post("/run")
def start_monitoring_run(
    background_tasks: BackgroundTasks,
    limit: int | None = None,
    offset: int = 0,
    hercontroleer_actuele: bool = False,
    db: Session = Depends(get_db),
):
    """Start handmatig een controle van de actieve watchlist.
    Optioneel: ?limit=N controleert alleen de eerste N organisaties — handig om
    tijdens testen niet steeds de volledige (live, kostbare) watchlist te draaien.

    Organisaties die het verslag over het doeljaar al hebben worden
    overgeslagen: daar valt niets nieuwers te vinden en elke ronde zou
    opnieuw zoek- en modeltokens kosten. `?hercontroleer_actuele=true`
    doorzoekt ze alsnog."""
    batch = _actieve_watchlist(db)
    if batch is None:
        raise HTTPException(404, "geen watchlist ingesteld")
    doeljaar = batch.jaar - 1 if batch.jaar is not None else None
    te_doen = len(batch.companies)
    overgeslagen = 0
    if not hercontroleer_actuele and doeljaar is not None:
        overgeslagen = len(
            bepaal_over_te_slaan_companies(db, batch, doeljaar),
        )
        te_doen -= overgeslagen
    resterend = max(0, te_doen - max(offset, 0))
    aantal = resterend if limit is None else min(limit, resterend)
    background_tasks.add_task(
        run_monitoring_watchlist_background,
        limit,
        max(offset, 0),
        hercontroleer_actuele,
    )
    return {
        "batch_id": batch.id,
        "aantal_companies": aantal,
        "offset": max(offset, 0),
        "overgeslagen_actueel": overgeslagen,
    }


def _nu() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/companies/{company_id}/jaarverslag", status_code=201)
async def upload_jaarverslag(
    company_id: str,
    file: UploadFile,
    verslagjaar: int | None = Form(None),
    db: Session = Depends(get_db),
):
    """Een jaarverslag dat de agent niet vond, door de reviewer aangeleverd.

    De monitoring vindt lang niet alles: op de watchlist van 17-09-2026 staan
    110 van de 205 organisaties op "niet gevonden", terwijl een reviewer het
    verslag van bijvoorbeeld Koraal Groep gewoon op zijn schijf heeft staan. Er
    was geen enkele manier om dat de werkbank in te krijgen.

    Het geüploade document gaat door dezelfde lezing als een gevonden verslag —
    dezelfde paginakeuze, dezelfde extractie, dezelfde weging — zodat er een
    bronkaart uit komt die de reviewer op precies dezelfde manier beoordeelt,
    met het WP-getal, het citaat en het paginanummer erbij.
    """
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "organisatie niet gevonden")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(422, "het bestand moet een PDF zijn (.pdf)")

    inhoud = await file.read()
    if not inhoud:
        raise HTTPException(422, "het bestand is leeg")
    if len(inhoud) > documenten.MAX_DOCUMENT_BYTES:
        raise HTTPException(413, "het bestand is te groot")

    try:
        paginas = jaarverslag_provider.relevante_pdf_paginas(inhoud)
    except Exception as exc:
        raise HTTPException(422, "het bestand is geen leesbare PDF") from exc

    # Zonder opslag is er straks geen bewijs te tonen: de kaart zou naar een
    # document verwijzen dat nergens bestaat. Dan liever hier stoppen met de
    # reden, dan een kaart die bij het openen stukloopt.
    url = documenten.upload_url(company.id, inhoud)
    if not documenten.bewaar(url, inhoud):
        raise HTTPException(
            503,
            "documentopslag is niet beschikbaar; het jaarverslag kan niet "
            "worden bewaard",
        )

    finding = await jaarverslag_provider.lees_wp_uit_paginas(
        company.naam, url, paginas,
    )
    gevraagd_jaar = gevraagd_jaar_van(company)
    # Het jaartal dat de reviewer opgeeft gaat vóór: hij heeft het verslag in
    # handen. Anders de bestandsnaam, die er vaak in staat.
    jaar_van_verslag = verslagjaar or jaar_uit_url(file.filename)
    document = SourceDocument(
        naam=company.naam,
        company_website_url=(
            (company.enrichment.website_url if company.enrichment else None)
            or company.website_url
        ),
        url=url,
        titel=file.filename or "Geüpload jaarverslag",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=gevraagd_jaar,
        verslagjaar=jaar_van_verslag,
        informatie_peilmoment=finding.peilmoment if finding else None,
        wp_gevonden=finding.wp_gevonden if finding else None,
        eenheid=(
            "fte" if finding and finding.is_fte
            else "werkzame_personen" if finding and finding.wp_gevonden is not None
            else None
        ),
        bewijsfragment=finding.context if finding else None,
        bron_pagina=finding.bron_pagina if finding else None,
        scope_class=heuristic_scope_class(
            finding.is_limburg_specifiek if finding else None,
            "jaarverslag",
        ),
        # Er is gezocht, ook als er niets uit kwam. Zonder deze vlag zegt de
        # kaart "nog niet uitgelezen" terwijl het document wel degelijk is
        # doorzocht, en betaalt de volgende ronde er opnieuw voor.
        wp_extractie_gedaan=True,
        raw_data={
            **((finding.raw if finding else None) or {}),
            "geupload_bestand": file.filename,
            "paginas_met_personeel": len(paginas),
        },
    )
    kandidaat = maak_kandidaat(
        db,
        company,
        document,
        doel="door de reviewer geüpload jaarverslag",
        onderzoekspaden=[{
            "route": "upload",
            "reden": "jaarverslag aangeleverd door de reviewer",
            "status": "afgerond",
            "aantal_bronnen": 1,
        }],
    )

    status_rij = (
        db.query(JaarverslagMonitoring).filter_by(company_id=company.id)
        .one_or_none()
    )
    if status_rij is None:
        status_rij = JaarverslagMonitoring(company_id=company.id)
        db.add(status_rij)
    # Alleen vooruit. Een reviewer die het verslag over 2023 aanlevert mag de
    # baseline niet terugzetten als de monitoring 2025 al heeft; een jaartal
    # dat we niet kennen verdringt een bekend jaartal evenmin.
    bestaand = status_rij.laatste_verslagjaar
    if not status_rij.laatste_bron_url or (
        jaar_van_verslag is not None
        and (bestaand is None or jaar_van_verslag >= bestaand)
    ):
        status_rij.laatste_bron_url = url
        status_rij.laatste_verslagjaar = jaar_van_verslag or bestaand
    status_rij.laatst_gecontroleerd_op = _nu()
    db.commit()

    return {
        "bron": _candidate_dict(kandidaat),
        # Leeg als er een getal uit kwam. Geen fout: het verslag staat er, is
        # doorzocht, en de reviewer kan het alsnog zelf openen en beoordelen.
        "melding": (
            None if kandidaat.wp_gevonden is not None
            else "Het verslag is opgeslagen en doorzocht, maar er kwam geen "
                 "WP-getal uit. Open het bewijs om zelf te kijken."
        ),
    }
