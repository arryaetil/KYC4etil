"""Pipeline-orchestratie: verrijking -> agents -> reconciliatie -> scoring.
Elke stap logt naar pipeline_runs (observability + kosten, doc §5)."""
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import (AgentResult, Batch, CallListItem, Candidate, Company,
                      Enrichment, PipelineRun)
from ..providers import get_providers
from ..research.usage import (get_cost_summary, get_usage_totals,
                              neem_token_delta, start_usage_tracking)
from .confidence import bereken_confidence
from .evidence import IdentityClass, ScopeClass
from .reconcile import (Strategie, bepaal_strategie, reconcilieer,
                        signaleer_afwijkende_extra_bronnen)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _log(db: Session, batch_id: str, company_id: str | None, stap: str,
         status: str, t0: float, error: str | None = None) -> None:
    """Logt één pipeline-stap, inclusief de tokens die deze stap zelf verbruikte."""
    tokens_in, tokens_out = neem_token_delta()
    db.add(PipelineRun(batch_id=batch_id, company_id=company_id, stap=stap,
                       status=status, duur_ms=int((time.monotonic() - t0) * 1000),
                       tokens_in=tokens_in, tokens_out=tokens_out,
                       error=error))


async def verwerk_company(db: Session, company: Company, batch: Batch) -> Candidate:
    lookup, website_agent, jaarverslag_agent, identity_scope_classifier = get_providers()
    # Per organisatie tellen, zodat kosten niet doorlekken naar de volgende.
    start_usage_tracking()
    t_company = time.monotonic()

    # STAP 1 — verrijking
    t0 = time.monotonic()
    place = await lookup.lookup(company.naam, company.gemeente)
    loc = await lookup.locations(company.naam, company.kvk_nummer)
    website_url = (place.website if place else None) or company.website_url
    telefoonnummer = (place.phone if place else None) or company.telefoonnummer
    email = await lookup.scrape_email(website_url)
    enrichment = Enrichment(
        company_id=company.id,
        website_url=website_url,
        telefoonnummer=telefoonnummer,
        email=email,
        locatie_count_nl=loc.count_nl, locatie_count_lb=loc.count_lb,
        locatie_bron=loc.bron,
        is_multi_locatie=bool(loc.count_nl and loc.count_nl > 1),
        adres_validated=bool(place and place.raw.get("adres_match", place.adres is not None)),
        lookup_failed=place is None and not website_url,
    )
    db.add(enrichment)
    _log(db, batch.id, company.id, "verrijking", "ok" if place else "skipped", t0)

    strategie = bepaal_strategie(enrichment.lookup_failed, loc.count_nl, loc.count_lb,
                                 loc.count_nl_is_ondergrens)

    # STAP 2 — agents (altijd draaien; website_agent valt intern terug op web search als
    # er geen URL is — zie live.py Fase C. Zo werkt ook lookup_failed niet als blokkade.)
    t0 = time.monotonic()
    w_finding = await website_agent.run(
        company.naam, company.adres, enrichment.website_url, gemeente=company.gemeente)
    _log(db, batch.id, company.id, "website_agent", "ok" if w_finding else "skipped", t0)
    t0 = time.monotonic()
    # Sla jaarverslag-agent over als website-agent al een hoog-zekerheidsbevinding heeft.
    # Dit bespaart 1-2 extra LLM-calls per bedrijf (kostenbeheersing) én verkleint de kans
    # dat een generieke jaarverslag-zoekopdracht (vooral bij kleine bedrijven zonder eigen
    # jaarverslag) een onverwant document van een heel ander bedrijf oppikt.
    if w_finding and getattr(w_finding, "zekerheid", None) == "hoog":
        j_finding = None
        _log(db, batch.id, company.id, "jaarverslag_agent", "skipped", t0)
    else:
        j_finding = await jaarverslag_agent.run(company.naam, batch.jaar,
                                                website_url=enrichment.website_url)
        _log(db, batch.id, company.id, "jaarverslag_agent", "ok" if j_finding else "skipped", t0)

    # Extra publieke bronnen (LinkedIn, KvK-vermeldingen, nieuws, etc.) — ook voor kleine
    # bedrijven zonder jaarverslag. Puur human-in-the-loop-keuzemateriaal; telt niet mee
    # in reconciliatie/confidence-score.
    t0 = time.monotonic()
    uitgesloten_urls = {f.bron_url for f in (w_finding, j_finding) if f and f.bron_url}
    extra_findings = await website_agent.extra_bronnen(company.naam, company.gemeente, uitgesloten_urls)
    _log(db, batch.id, company.id, "extra_bronnen",
         "ok" if extra_findings else "skipped", t0)

    agent_result_ids = {}
    t0 = time.monotonic()
    classificatie_status = "skipped"
    for finding in (w_finding, j_finding, *extra_findings):
        if finding is None:
            continue
        is_extra = finding in extra_findings
        if classificatie_status == "skipped":
            classificatie_status = "ok"
        try:
            identity_class, scope_class = await identity_scope_classifier.classify(
                company.naam, company.adres, company.gemeente,
                enrichment.website_url, finding,
            )
        except Exception:
            # Classificatie is puur informatief voor reviewers en mag nooit de hele
            # bedrijfsverwerking (reconciliatie/confidence/candidate) laten falen.
            classificatie_status = "error"
            identity_class, scope_class = IdentityClass.UNKNOWN.value, ScopeClass.UNKNOWN.value
        ar = AgentResult(
            company_id=company.id, batch_id=batch.id,
            agent_type="extra_bron" if is_extra
            else "website" if finding.bron_type in ("website", "media") else "jaarverslag",
            wp_gevonden=finding.wp_gevonden, wp_context=finding.context,
            is_limburg_specifiek=finding.is_limburg_specifiek, is_fte=finding.is_fte,
            peilmoment=finding.peilmoment, bron_url=finding.bron_url,
            bron_type=finding.bron_type, llm_zekerheid=finding.zekerheid,
            raw_output=finding.raw or None,
            eigen_personeel=finding.eigen_personeel, uitzend=finding.uitzend,
            detachering=finding.detachering, wsw=finding.wsw,
            man=finding.man, vrouw=finding.vrouw,
            voltijd=finding.voltijd, deeltijd=finding.deeltijd,
            pct_op_locatie=finding.pct_op_locatie, bron_pagina=finding.bron_pagina,
            identity_class=identity_class, scope_class=scope_class,
        )
        db.add(ar)
        db.flush()
        agent_result_ids[id(finding)] = ar.id
    _log(db, batch.id, company.id, "identity_scope_classificatie", classificatie_status, t0)

    # STAP 3 — reconciliatie
    rec = reconcilieer(w_finding, j_finding, loc.count_nl, loc.count_lb,
                       loc.count_nl_is_ondergrens)
    reviewer_signaal = signaleer_afwijkende_extra_bronnen(rec.wp_kandidaat, extra_findings)

    # STAP 4 — confidence
    if rec.finding is not None:
        score = bereken_confidence(
            rec.finding, rec.n_bronnen, rec.bronnen_consistent, peiljaar=batch.jaar,
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
            reviewer_signaal=reviewer_signaal,
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

    # 🔴 zonder data -> bellijst; bij herverwerk reden bijwerken zodat die actueel blijft
    existing_cli = db.query(CallListItem).filter_by(company_id=company.id).first()
    if candidate.confidence_label == "laag" and enrichment.telefoonnummer:
        if existing_cli:
            existing_cli.reden = candidate.reconciliatie_reden or "lage confidence"
        else:
            db.add(CallListItem(company_id=company.id, telefoonnummer=enrichment.telefoonnummer,
                                reden=candidate.reconciliatie_reden or "lage confidence"))

    # Afsluitende totaalregel: het bedrag staat hier en niet per stap, omdat
    # kosten_cents in hele centen is en een losse stap daaronder blijft.
    tokens_in, tokens_out = get_usage_totals()
    db.add(PipelineRun(
        batch_id=batch.id, company_id=company.id, stap="totaal", status="ok",
        duur_ms=int((time.monotonic() - t_company) * 1000),
        tokens_in=tokens_in, tokens_out=tokens_out,
        kosten_cents=get_cost_summary()["totaal_cents"],
    ))
    return candidate


async def run_batch(db: Session, batch_id: str) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise ValueError(f"batch {batch_id} bestaat niet")
    batch.status = "running"
    batch.verwerkt = 0
    db.commit()

    for company in batch.companies:
        # Al succesvol verwerkt (re-run of gedeeltelijk uitgevoerde batch)
        if company.candidate is not None:
            batch.verwerkt += 1
            db.commit()
            continue

        # Maak eventuele halve vorige run schoon (enrichment maar geen candidate)
        if company.enrichment is not None:
            db.delete(company.enrichment)
            for ar in list(company.agent_results):
                db.delete(ar)
            db.flush()

        t0 = time.monotonic()
        try:
            await verwerk_company(db, company, batch)
        except Exception as exc:
            # Eén fout stopt de hele batch niet — loggen en doorgaan
            db.rollback()
            _log(db, batch.id, company.id, "verwerk_company", "error", t0,
                 error=str(exc)[:1000])
        batch.verwerkt += 1  # altijd ophogen, ook bij fout (= verwerkt/geprobeerd)
        db.commit()
        db.refresh(batch)
        if batch.status == "cancelled":
            return batch

    batch.status = "done"
    batch.completed_at = _now()
    db.commit()
    return batch
