"""Dashboard-niveau jaarverslag-monitoring: werkt altijd op de ene actieve
watchlist (Batch.is_monitoringlijst=True), zonder batch_id in de URL."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Batch, Company, JaarverslagMonitoring, PipelineRun
from ..pipeline.monitoring import run_monitoring_watchlist_background

router = APIRouter(prefix="/monitoring", tags=["monitoring"], dependencies=[Depends(get_current_user)])


def _actieve_watchlist(db: Session) -> Batch | None:
    return (db.query(Batch).filter_by(is_monitoringlijst=True)
            .order_by(Batch.created_at.desc()).first())


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
        for pr in (db.query(PipelineRun)
                   .filter(PipelineRun.company_id.in_(company_ids),
                           PipelineRun.stap == "jaarverslag_monitoring")
                   .order_by(PipelineRun.created_at)):
            if pr.status == "ok":
                bevindingen.add(pr.company_id)
            elif pr.status == "error":
                fouten_map[pr.company_id] = pr.error or "onbekende fout"

    out = []
    for comp in companies:
        status = status_map.get(comp.id)
        cand = comp.candidate
        out.append({
            "company_id": comp.id, "naam": comp.naam, "gemeente": comp.gemeente,
            "laatst_gecontroleerd_op": (status.laatst_gecontroleerd_op.isoformat() + "Z"
                                        if status and status.laatst_gecontroleerd_op else None),
            "laatste_bron_url": status.laatste_bron_url if status else None,
            "bron_status": "gevonden" if status and status.laatste_bron_url else "ontbreekt",
            "nieuwe_bevinding": comp.id in bevindingen,
            "fout": fouten_map.get(comp.id),
            "wp_kandidaat": cand.wp_kandidaat if cand else None,
            "confidence_label": cand.confidence_label if cand else None,
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
def start_monitoring_run(background_tasks: BackgroundTasks, limit: int | None = None,
                         db: Session = Depends(get_db)):
    """Start handmatig een controle van de actieve watchlist.
    Optioneel: ?limit=N controleert alleen de eerste N organisaties — handig om
    tijdens testen niet steeds de volledige (live, kostbare) watchlist te draaien."""
    batch = _actieve_watchlist(db)
    if batch is None:
        raise HTTPException(404, "geen watchlist ingesteld")
    aantal = len(batch.companies) if limit is None else min(limit, len(batch.companies))
    background_tasks.add_task(run_monitoring_watchlist_background, limit)
    return {"batch_id": batch.id, "aantal_companies": aantal}
