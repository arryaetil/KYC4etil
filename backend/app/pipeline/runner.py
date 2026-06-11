"""Pipeline-orchestratie: verrijking -> agents -> reconciliatie -> scoring.
Elke stap logt naar pipeline_runs (observability + kosten, doc §5)."""
import time
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import (AgentResult, Batch, CallListItem, Candidate, Company,
                      Enrichment, PipelineRun)
from ..providers import get_providers
from .confidence import bereken_confidence
from .reconcile import Strategie, bepaal_strategie, reconcilieer


def _log(db: Session, batch_id: str, company_id: str | None, stap: str,
         status: str, t0: float, error: str | None = None) -> None:
    db.add(PipelineRun(batch_id=batch_id, company_id=company_id, stap=stap,
                       status=status, duur_ms=int((time.monotonic() - t0) * 1000),
                       error=error))


async def verwerk_company(db: Session, company: Company, batch: Batch) -> Candidate:
    lookup, website_agent, jaarverslag_agent = get_providers()

    # STAP 1 — verrijking
    t0 = time.monotonic()
    place = await lookup.lookup(company.naam, company.gemeente)
    loc = await lookup.locations(company.naam, company.kvk_nummer)
    website_url = (place.website if place else None) or company.website_url
    telefoonnummer = (place.phone if place else None) or company.telefoonnummer
    enrichment = Enrichment(
        company_id=company.id,
        website_url=website_url,
        telefoonnummer=telefoonnummer,
        locatie_count_nl=loc.count_nl, locatie_count_lb=loc.count_lb,
        locatie_bron=loc.bron,
        is_multi_locatie=bool(loc.count_nl and loc.count_nl > 1),
        adres_validated=bool(place and place.raw.get("adres_match", place.adres is not None)),
        lookup_failed=place is None and not website_url,
    )
    db.add(enrichment)
    _log(db, batch.id, company.id, "verrijking", "ok" if place else "skipped", t0)

    strategie = bepaal_strategie(enrichment.lookup_failed, loc.count_nl, loc.count_lb)

    # STAP 2 — agents (altijd draaien; website_agent valt intern terug op web search als
    # er geen URL is — zie live.py Fase C. Zo werkt ook lookup_failed niet als blokkade.)
    t0 = time.monotonic()
    w_finding = await website_agent.run(
        company.naam, company.adres, enrichment.website_url, gemeente=company.gemeente)
    _log(db, batch.id, company.id, "website_agent", "ok" if w_finding else "skipped", t0)
    t0 = time.monotonic()
    j_finding = await jaarverslag_agent.run(company.naam, batch.jaar)
    _log(db, batch.id, company.id, "jaarverslag_agent", "ok" if j_finding else "skipped", t0)

    agent_result_ids = {}
    for finding in (w_finding, j_finding):
        if finding is None:
            continue
        ar = AgentResult(
            company_id=company.id, batch_id=batch.id,
            agent_type="website" if finding.bron_type in ("website", "media") else "jaarverslag",
            wp_gevonden=finding.wp_gevonden, wp_context=finding.context,
            is_limburg_specifiek=finding.is_limburg_specifiek, is_fte=finding.is_fte,
            peilmoment=finding.peilmoment, bron_url=finding.bron_url,
            bron_type=finding.bron_type, llm_zekerheid=finding.zekerheid,
            raw_output=finding.raw or None,
        )
        db.add(ar)
        db.flush()
        agent_result_ids[id(finding)] = ar.id

    # STAP 3 — reconciliatie
    rec = reconcilieer(w_finding, j_finding, loc.count_nl, loc.count_lb)

    # STAP 4 — confidence
    if rec.finding is not None:
        score = bereken_confidence(
            rec.finding, loc.count_nl, loc.count_lb, enrichment.adres_validated,
            rec.n_bronnen, rec.bronnen_consistent, peiljaar=batch.jaar,
            is_schatting=rec.is_schatting, schatting_penalty=rec.schatting_penalty,
            locatie_bron=loc.bron,
        )
        label = score.label
        # label bepaalt de definitieve actie, ongeacht voorlopige strategie
        definitieve_strategie = (
            Strategie.DIRECT_VERWERKEN if label == "hoog"
            else Strategie.GERICHTE_CHAT if label == "middel"
            else Strategie.VOLLEDIGE_CHAT_OF_BELLIJST
        )
        candidate = Candidate(
            company_id=company.id, batch_id=batch.id,
            wp_kandidaat=rec.wp_kandidaat, is_schatting=rec.is_schatting,
            gekozen_agent_result=agent_result_ids.get(id(rec.finding)),
            reconciliatie_reden=rec.reden,
            confidence_score=score.score, confidence_label=label,
            score_breakdown=score.breakdown, strategie=definitieve_strategie.value,
        )
    else:
        candidate = Candidate(
            company_id=company.id, batch_id=batch.id,
            wp_kandidaat=None, reconciliatie_reden=rec.reden,
            confidence_score=0.0, confidence_label="laag",
            score_breakdown={"reden": rec.reden},
            strategie=strategie.value if strategie != Strategie.DIRECT_VERWERKEN
            else Strategie.VOLLEDIGE_CHAT_OF_BELLIJST.value,
        )
    db.add(candidate)

    # 🔴 zonder data -> bellijst
    if candidate.confidence_label == "laag" and enrichment.telefoonnummer:
        db.add(CallListItem(company_id=company.id, telefoonnummer=enrichment.telefoonnummer,
                            reden=candidate.reconciliatie_reden or "lage confidence"))
    return candidate


async def run_batch(db: Session, batch_id: str) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise ValueError(f"batch {batch_id} bestaat niet")
    batch.status = "running"
    batch.verwerkt = 0
    db.commit()
    try:
        for company in batch.companies:
            await verwerk_company(db, company, batch)
            batch.verwerkt += 1
            db.commit()
        batch.status = "done"
        batch.completed_at = datetime.utcnow()
    except Exception:
        batch.status = "error"
        db.commit()
        raise
    db.commit()
    return batch
