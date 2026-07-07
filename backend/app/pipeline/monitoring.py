"""Periodieke jaarverslag-monitoring: hergebruikt de bestaande jaarverslag-agent
en reconciliatie-/confidence-logica, maar draait buiten een handmatige batch-run om."""
import time

from sqlalchemy.orm import Session

from ..models import AgentResult, Candidate, Company, JaarverslagMonitoring
from ..providers import get_providers
from .confidence import bereken_confidence
from .reconcile import reconcilieer
from .runner import _log, _now


async def check_company_jaarverslag(db: Session, company: Company, jaar: int) -> bool:
    """Controleert of er een nieuw jaarverslag is t.o.v. de laatst bekende bron.
    Retourneert True als er een nieuwe/bijgewerkte candidate is aangemaakt."""
    _, _, jaarverslag_agent = get_providers()
    t0 = time.monotonic()

    status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one_or_none()
    if status is None:
        status = JaarverslagMonitoring(company_id=company.id)
        db.add(status)

    finding = await jaarverslag_agent.run(company.naam, jaar)
    status.laatst_gecontroleerd_op = _now()

    if finding is None or not finding.wp_gevonden:
        _log(db, company.batch_id, company.id, "jaarverslag_monitoring", "skipped", t0)
        db.commit()
        return False

    if finding.bron_url == status.laatste_bron_url:
        _log(db, company.batch_id, company.id, "jaarverslag_monitoring", "skipped", t0)
        db.commit()
        return False

    status.laatste_bron_url = finding.bron_url

    ar = AgentResult(
        company_id=company.id, batch_id=company.batch_id, agent_type="jaarverslag",
        wp_gevonden=finding.wp_gevonden, wp_context=finding.context,
        is_limburg_specifiek=finding.is_limburg_specifiek, is_fte=finding.is_fte,
        peilmoment=finding.peilmoment, bron_url=finding.bron_url,
        bron_type=finding.bron_type, llm_zekerheid=finding.zekerheid,
        raw_output=finding.raw or None,
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
