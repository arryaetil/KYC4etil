"""Periodieke jaarverslag-monitoring: hergebruikt de bestaande jaarverslag-agent
en reconciliatie-/confidence-logica, maar draait buiten een handmatige batch-run om."""
import asyncio
import logging
import re
import time
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
from ..research.ranking import rank_bronnen
from ..research.urls import canonicaliseer_url
from ..research.validation import SourceDocument, valideer_bron
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


def _sla_moderne_bron_op(
    db: Session,
    company: Company,
    jaar: int,
    finding,
) -> None:
    """Maak een reviewbare bronkandidaat in het canonieke bronnenmodel."""
    gevraagd_jaar = jaar - 1
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
    )
    ranked = rank_bronnen([valideer_bron(document)])
    run = ResearchRun(
        company_id=company.id,
        batch_id=company.batch_id,
        doel="periodieke jaarverslagmonitoring",
        gevraagd_jaar=gevraagd_jaar,
        status="completed",
        resultaat_status="review_nodig" if ranked else "niet_gevonden",
        onderzoekspaden=["document"],
        configuratie={"bron": "jaarverslag_monitoring"},
        started_at=_now(),
        completed_at=_now(),
    )
    db.add(run)
    db.flush()
    if not ranked:
        return
    bron = ranked[0]
    db.add(BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url=document.url,
        canonical_url=canonicaliseer_url(document.url),
        titel=document.titel,
        brontype=document.brontype,
        documenttype=document.documenttype,
        verslagjaar=document.verslagjaar,
        informatie_peilmoment=document.informatie_peilmoment,
        wp_gevonden=document.wp_gevonden,
        eenheid=document.eenheid,
        bewijsfragment=document.bewijsfragment,
        bron_pagina=document.bron_pagina,
        identity_class=bron.identity_class,
        scope_class=document.scope_class,
        autoriteit_score=bron.score_breakdown["autoriteit"],
        actualiteit_score=bron.score_breakdown["actualiteit"],
        identiteit_score=bron.score_breakdown["identiteit"],
        relevantie_score=bron.score_breakdown["relevantie"],
        ranking_score=bron.ranking_score,
        score_breakdown=bron.score_breakdown,
        validaties=bron.validaties,
        waarschuwingen=bron.waarschuwingen,
        raw_data=finding.raw or None,
        status="voorgesteld",
        rang=1,
    ))


def _documentjaar(url: str | None) -> int | None:
    if not url:
        return None
    decoded = unquote(url)
    jaren = [
        int(match)
        for match in re.findall(
            r"(?<!\d)(20\d{2})(?!\d)",
            decoded,
        )
    ]
    # Sommige zoekproviders verwijderen het procentteken uit `%20`, waardoor
    # `Jaarverslag%202025` als `Jaarverslag202025` terugkomt. Herstel alleen
    # het jaartal aan het einde van zo'n aaneengesloten cijferreeks.
    jaren.extend(
        int(cijferreeks[-4:])
        for cijferreeks in re.findall(r"\d{5,8}", decoded)
        if cijferreeks[-4:].startswith("20")
    )
    # Bestandsnamen beginnen vaak met een publicatiedatum en eindigen met het
    # verslagjaar, bv. 20250604_..._Jaarverslag_2024.pdf.
    return jaren[-1] if jaren else None


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
) -> BronKandidaat | None:
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
        if kandidaat.verslagjaar != werkelijk_jaar:
            kandidaat.verslagjaar = werkelijk_jaar
        geldig.append((werkelijk_jaar, kandidaat))
    return max(geldig, key=lambda item: item[0])[1] if geldig else None


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
    De laatst bekende bron_url wordt altijd bijgewerkt zodra de agent er één vindt,
    ook als er geen WP-getal uit te halen was — zo houdt de monitoring altijd een
    actuele link naar het meest recente jaarverslag bij. Een candidate wordt alleen
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

    beste_moderne_bron = _beste_moderne_jaarverslagbron(
        db,
        company,
        jaar,
    )
    if (
        beste_moderne_bron is not None
        and (
            status.laatste_verslagjaar
            or _documentjaar(status.laatste_bron_url)
            or 0
        ) < (beste_moderne_bron.verslagjaar or 0)
    ):
        status.laatste_bron_url = beste_moderne_bron.url
        status.laatste_verslagjaar = beste_moderne_bron.verslagjaar

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
    status.laatste_bron_url = finding.bron_url
    status.laatste_verslagjaar = gevonden_jaar

    wp_is_nieuw = _wp_is_nieuw_voor_bron(
        db,
        company,
        finding.bron_url,
        finding.wp_gevonden,
    )
    if not url_gewijzigd and not wp_is_nieuw:
        _log(db, company.batch_id, company.id, "jaarverslag_monitoring",
             STATUS_ONGEWIJZIGD, t0)
        db.commit()
        return False

    wijzigingsstatus = "new" if verslag_is_nieuw else "updated"

    _sla_moderne_bron_op(db, company, jaar, finding)

    _log(
        db,
        company.batch_id,
        company.id,
        "jaarverslag_monitoring",
        wijzigingsstatus,
        t0,
    )
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


def run_monitoring_watchlist_background(
    limit: int | None = None,
    offset: int = 0,
) -> None:
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
        company_ids = [
            company_id
            for (company_id,) in (
                db.query(Company.id)
                .filter_by(batch_id=batch.id)
                .order_by(Company.created_at, Company.id)
                .all()
            )
        ]
    finally:
        db.close()

    company_ids = company_ids[offset:]
    if limit is not None:
        company_ids = company_ids[:limit]
    if not company_ids:
        return
    asyncio.run(check_batch_jaarverslagen(batch_id, jaar, company_ids))
