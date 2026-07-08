"""Periodieke jaarverslag-monitoring: hergebruikt de bestaande jaarverslag-agent
en reconciliatie-/confidence-logica, maar draait buiten een handmatige batch-run om."""
import asyncio
import logging
import time

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import AgentResult, Batch, Candidate, Company, JaarverslagMonitoring, PipelineRun
from ..providers import get_providers
from .confidence import bereken_confidence
from .reconcile import reconcilieer
from .runner import _log, _now


async def check_company_jaarverslag(db: Session, company: Company, jaar: int) -> bool:
    """Controleert of er een nieuw jaarverslag is t.o.v. de laatst bekende bron.
    De laatst bekende bron_url wordt altijd bijgewerkt zodra de agent er één vindt,
    ook als er geen WP-getal uit te halen was — zo houdt de monitoring altijd een
    actuele link naar het meest recente jaarverslag bij. Een candidate wordt alleen
    aangemaakt/bijgewerkt als er zowel een nieuwe URL als een bruikbaar WP-getal is.
    Retourneert True als er een wijziging is vastgesteld (nieuwe URL, met of zonder
    WP-getal)."""
    _, _, jaarverslag_agent = get_providers()
    t0 = time.monotonic()

    status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one_or_none()
    if status is None:
        status = JaarverslagMonitoring(company_id=company.id)
        db.add(status)

    finding = await jaarverslag_agent.run(company.naam, jaar)
    status.laatst_gecontroleerd_op = _now()

    if finding is None or not finding.bron_url:
        _log(db, company.batch_id, company.id, "jaarverslag_monitoring", "skipped", t0)
        db.commit()
        return False

    url_gewijzigd = finding.bron_url != status.laatste_bron_url
    status.laatste_bron_url = finding.bron_url

    if not url_gewijzigd or not finding.wp_gevonden:
        _log(db, company.batch_id, company.id, "jaarverslag_monitoring",
             "ok" if url_gewijzigd else "skipped", t0)
        db.commit()
        return url_gewijzigd

    ar = AgentResult(
        company_id=company.id, batch_id=company.batch_id, agent_type="jaarverslag",
        wp_gevonden=finding.wp_gevonden, wp_context=finding.context,
        is_limburg_specifiek=finding.is_limburg_specifiek, is_fte=finding.is_fte,
        peilmoment=finding.peilmoment, bron_url=finding.bron_url,
        bron_type=finding.bron_type, llm_zekerheid=finding.zekerheid,
        raw_output=finding.raw or None,
        eigen_personeel=finding.eigen_personeel, uitzend=finding.uitzend,
        detachering=finding.detachering, wsw=finding.wsw,
        man=finding.man, vrouw=finding.vrouw,
        voltijd=finding.voltijd, deeltijd=finding.deeltijd,
        pct_op_locatie=finding.pct_op_locatie,
    )
    db.add(ar)
    db.flush()

    rec = reconcilieer(None, finding, None, None)
    score = bereken_confidence(
        rec.finding, None, None, adres_validated=False,
        n_bronnen=rec.n_bronnen, bronnen_consistent=rec.bronnen_consistent,
        peiljaar=jaar, is_schatting=rec.is_schatting,
        schatting_penalty=rec.schatting_penalty, locatie_bron="mock",
    )

    bestaande_candidate = db.query(Candidate).filter_by(
        company_id=company.id, batch_id=company.batch_id).one_or_none()
    if bestaande_candidate is not None:
        bestaande_candidate.wp_kandidaat = rec.wp_kandidaat
        bestaande_candidate.is_schatting = rec.is_schatting
        bestaande_candidate.gekozen_agent_result = ar.id
        bestaande_candidate.reconciliatie_reden = rec.reden
        bestaande_candidate.confidence_score = score.score
        bestaande_candidate.confidence_label = score.label
        bestaande_candidate.score_breakdown = score.breakdown
        bestaande_candidate.status = "pending"
    else:
        db.add(Candidate(
            company_id=company.id, batch_id=company.batch_id,
            wp_kandidaat=rec.wp_kandidaat, is_schatting=rec.is_schatting,
            gekozen_agent_result=ar.id, reconciliatie_reden=rec.reden,
            confidence_score=score.score, confidence_label=score.label,
            score_breakdown=score.breakdown, strategie="auto",
        ))

    _log(db, company.batch_id, company.id, "jaarverslag_monitoring", "ok", t0)
    db.commit()
    return True


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
            await check_company_jaarverslag(db, company, jaar)
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


def run_monitoring_watchlist_background(limit: int | None = None) -> None:
    """Zoekt de gemarkeerde watchlist-batch op (Batch.is_monitoringlijst=True) en
    controleert alle organisaties daarin gelijktijdig op nieuwe jaarverslagen.
    Geen watchlist ingesteld of leeg -> stille no-op.
    limit beperkt (optioneel) het aantal gecontroleerde organisaties — bedoeld
    om tijdens testen/ontwikkelen niet steeds de volledige, live-kostbare
    watchlist te hoeven doorlopen."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter_by(is_monitoringlijst=True).order_by(
            Batch.created_at.desc()).first()
        if batch is None:
            return
        batch_id, jaar = batch.id, batch.jaar
        company_ids = [c.id for c in batch.companies]
    finally:
        db.close()

    if limit is not None:
        company_ids = company_ids[:limit]
    if not company_ids:
        return
    asyncio.run(check_batch_jaarverslagen(batch_id, jaar, company_ids))
