"""Dashboard-niveau jaarverslag-monitoring: werkt altijd op de ene actieve
watchlist (Batch.is_monitoringlijst=True), zonder batch_id in de URL."""
from collections import Counter

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    Batch, BronKandidaat, Company, JaarverslagMonitoring, PipelineRun,
)
from ..pipeline.monitoring import (
    bepaal_over_te_slaan_companies, run_monitoring_watchlist_background,
)
from ..research.urls import canonicaliseer_url

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


def _bewijsplek_per_company(
    db: Session,
    bron_per_company: dict[str, str],
) -> dict[str, tuple[int | None, str | None]]:
    """Zoekt bij elke monitoringbron het paginanummer en bewijsfragment op.

    De monitoringronde bewaart op JaarverslagMonitoring alleen de URL, maar legt
    de vindplaats van het WP-getal wél vast op de BronKandidaat die zij in
    dezelfde transactie aanmaakt. Zonder die twee velden opent de reviewer het
    jaarverslag op pagina 1 in plaats van bij het cijfer.

    Vergelijking gaat over de canonieke URL: de monitoring en de kandidaat
    kunnen dezelfde bron met een andere querystring of trailing slash hebben.
    """
    if not bron_per_company:
        return {}

    canoniek = {cid: canonicaliseer_url(url) for cid, url in bron_per_company.items()}
    company_ids = list(bron_per_company)
    gevonden: dict[str, tuple[int | None, str | None]] = {}

    # Oplopend op created_at zodat de nieuwste vondst de oudere overschrijft.
    for kandidaat in (db.query(BronKandidaat)
                      .filter(BronKandidaat.company_id.in_(company_ids))
                      .order_by(BronKandidaat.created_at)):
        doel = canoniek.get(kandidaat.company_id)
        bron = kandidaat.canonical_url or canonicaliseer_url(kandidaat.url or "")
        if doel and bron == doel and (kandidaat.bron_pagina or kandidaat.bewijsfragment):
            gevonden[kandidaat.company_id] = (
                kandidaat.bron_pagina, kandidaat.bewijsfragment,
            )

    return gevonden


@router.get("")
def monitoring_status(db: Session = Depends(get_db)):
    """Status van de actieve jaarverslag-watchlist. batch=null als er nog geen is ingesteld."""
    batch = _actieve_watchlist(db)
    if batch is None:
        return {"batch": None, "doeljaar": None, "totaal": 0, "gecontroleerd": 0,
                "bronnen_gevonden": 0, "bronnen_ontbreken": 0,
                "actueel": 0, "verouderd": 0, "ontbreekt": 0,
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
            if pr.status == "new":
                bevindingen.add(pr.company_id)
            elif pr.status == "error":
                fouten_map[pr.company_id] = pr.error or "onbekende fout"

    bewijsplek = _bewijsplek_per_company(db, {
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
        pagina, fragment = bewijsplek.get(comp.id, (None, None))
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
            "bron_status": "gevonden" if bron_url else "ontbreekt",
            "doeljaar": doeljaar,
            "jaarstatus": _jaarstatus(doeljaar, verslagjaar, bron_url),
            # Blijft bestaan, maar is niet langer de hoofdstatus: dit zegt
            # "veranderd sinds de vorige controle", niet "actueel".
            "nieuwe_bevinding": comp.id in bevindingen,
            "fout": fouten_map.get(comp.id),
        })

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
