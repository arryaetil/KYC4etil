"""Dashboard-niveau jaarverslag-monitoring: werkt altijd op de ene actieve
watchlist (Batch.is_monitoringlijst=True), zonder batch_id in de URL."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    Batch, BronKandidaat, Company, JaarverslagMonitoring, PipelineRun,
)
from ..pipeline.monitoring import run_monitoring_watchlist_background
from ..research.urls import canonicaliseer_url

router = APIRouter(prefix="/monitoring", tags=["monitoring"], dependencies=[Depends(get_current_user)])


def _actieve_watchlist(db: Session) -> Batch | None:
    return (db.query(Batch).filter_by(is_monitoringlijst=True)
            .order_by(Batch.created_at.desc()).first())


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
        return {"batch": None, "totaal": 0, "gecontroleerd": 0,
                "bronnen_gevonden": 0, "bronnen_ontbreken": 0,
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

    out = []
    for comp in companies:
        status = status_map.get(comp.id)
        pagina, fragment = bewijsplek.get(comp.id, (None, None))
        out.append({
            "company_id": comp.id, "naam": comp.naam, "gemeente": comp.gemeente,
            "laatst_gecontroleerd_op": (status.laatst_gecontroleerd_op.isoformat() + "Z"
                                        if status and status.laatst_gecontroleerd_op else None),
            "laatste_bron_url": status.laatste_bron_url if status else None,
            "verslagjaar": status.laatste_verslagjaar if status else None,
            # Vindplaats van het WP-getal, zodat de viewer op de juiste pagina
            # opent en het cijfer markeert in plaats van op pagina 1 te beginnen.
            "bron_pagina": pagina,
            "bewijsfragment": fragment,
            "bron_status": "gevonden" if status and status.laatste_bron_url else "ontbreekt",
            "nieuwe_bevinding": comp.id in bevindingen,
            "fout": fouten_map.get(comp.id),
        })

    gecontroleerd = sum(1 for c in out if c["laatst_gecontroleerd_op"])
    bronnen_gevonden = sum(1 for c in out if c["laatste_bron_url"])
    return {
        "batch": {"id": batch.id, "naam": batch.naam, "jaar": batch.jaar},
        "totaal": len(companies),
        "gecontroleerd": gecontroleerd,
        "bronnen_gevonden": bronnen_gevonden,
        "bronnen_ontbreken": len(companies) - bronnen_gevonden,
        "nieuwe_bevindingen": len(bevindingen),
        "fouten": len(fouten_map),
        "companies": out,
    }


@router.post("/run")
def start_monitoring_run(
    background_tasks: BackgroundTasks,
    limit: int | None = None,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Start handmatig een controle van de actieve watchlist.
    Optioneel: ?limit=N controleert alleen de eerste N organisaties — handig om
    tijdens testen niet steeds de volledige (live, kostbare) watchlist te draaien."""
    batch = _actieve_watchlist(db)
    if batch is None:
        raise HTTPException(404, "geen watchlist ingesteld")
    resterend = max(0, len(batch.companies) - max(offset, 0))
    aantal = resterend if limit is None else min(limit, resterend)
    background_tasks.add_task(
        run_monitoring_watchlist_background,
        limit,
        max(offset, 0),
    )
    return {
        "batch_id": batch.id,
        "aantal_companies": aantal,
        "offset": max(offset, 0),
    }
