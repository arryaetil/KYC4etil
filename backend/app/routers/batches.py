"""Batch-API voor de bronnenwerkbank.

De actieve workflow kent alleen organisaties, research-runs en bronkandidaten.
Oude tabellen worden bij het verwijderen van historische batches nog defensief
opgeruimd, maar spelen geen rol meer in lezen, onderzoeken of exporteren.
"""
import asyncio
import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from zipfile import BadZipFile

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    AgentResult, Batch, BronKandidaat, CallListItem, Candidate, ChatSession,
    Company, Enrichment, JaarverslagMonitoring, PipelineRun, ResearchRun, User,
    VastgoedRecord, WPRecord,
)
from ..research.service import run_research_batch

router = APIRouter(
    prefix="/batches", tags=["batches"], dependencies=[Depends(get_current_user)],
)

CSV_VELDEN = {"naam"}
# Spelling verschilt per export; de VVL-lijsten en de handmatige Excels noemen
# de SBI-tekst allebei anders. "omschrijving" zonder voorvoegsel mag hier op
# sbi_omschrijving uitkomen: het is de enige omschrijvende kolom in dit formaat.
KOLOM_ALIASSEN = {
    "vestnr": "vestigingsnummer",
    "omschrijving": "sbi_omschrijving",
    "sbi omschrijving": "sbi_omschrijving",
    "sbi-omschrijving": "sbi_omschrijving",
    "sbi_code_omschrijving": "sbi_omschrijving",
}
MONITORINGLIJST_NAAM_MARKERS = ("monitoringlijst", "monitorlijst", "watchlist")


def _lijkt_monitoringlijst_batch(batch: Batch) -> bool:
    naam = (batch.naam or "").lower()
    return any(marker in naam for marker in MONITORINGLIJST_NAAM_MARKERS)


def _latest_research_maps(
    db: Session,
    batch_id: str,
) -> tuple[dict[str, ResearchRun], dict[str, BronKandidaat], set[str]]:
    latest_runs: dict[str, ResearchRun] = {}
    for run in (
        db.query(ResearchRun)
        .filter_by(batch_id=batch_id)
        .order_by(ResearchRun.created_at.desc())
    ):
        latest_runs.setdefault(run.company_id, run)

    run_ids = [run.id for run in latest_runs.values()]
    top_candidates: dict[str, BronKandidaat] = {}
    accepted_run_ids: set[str] = set()
    if run_ids:
        candidates = (
            db.query(BronKandidaat)
            .filter(BronKandidaat.research_run_id.in_(run_ids))
            .order_by(BronKandidaat.rang, BronKandidaat.created_at)
            .all()
        )
        for candidate in candidates:
            top_candidates.setdefault(candidate.research_run_id, candidate)
            if candidate.status == "geaccepteerd":
                accepted_run_ids.add(candidate.research_run_id)
                top_candidates[candidate.research_run_id] = candidate
    return latest_runs, top_candidates, accepted_run_ids


def _run_research_batch_background(batch_id: str) -> None:
    asyncio.run(run_research_batch(batch_id))


def _lees_upload(content: bytes, bestandsnaam: str) -> tuple[set[str], list[dict]]:
    if Path(bestandsnaam).suffix.lower() == ".xlsx":
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            worksheet = workbook.active
            waarden = worksheet.iter_rows(values_only=True)
            kop = next(waarden, ())
            rows = [dict(zip(kop, row)) for row in waarden]
            workbook.close()
        except (BadZipFile, InvalidFileException, OSError, ValueError) as exc:
            raise HTTPException(422, "Ongeldig Excel-bestand") from exc
    else:
        try:
            tekst = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(422, "Bestand moet CSV of Excel (.xlsx) zijn") from exc
        reader = csv.DictReader(io.StringIO(tekst))
        kop = reader.fieldnames or ()
        rows = list(reader)

    kolommen = {
        KOLOM_ALIASSEN.get(str(k).strip().lower(), str(k).strip().lower())
        for k in kop if k is not None
    }
    genormaliseerd = []
    for row in rows:
        schoon = {
            KOLOM_ALIASSEN.get(str(k).strip().lower(), str(k).strip().lower()):
                (str(v).strip() if v is not None and str(v).strip() else None)
            for k, v in row.items() if k is not None
        }
        if schoon.get("naam"):
            genormaliseerd.append(schoon)
    return kolommen, genormaliseerd


@router.post("/upload")
async def upload_batch(
    file: UploadFile,
    naam: str | None = None,
    jaar: int | None = None,
    monitoringlijst: bool = False,
    map_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Maak een onderzoekslijst uit een CSV- of Excel-bestand."""
    kolommen, rows = _lees_upload(await file.read(), file.filename or "")
    if not rows or not CSV_VELDEN.issubset(kolommen):
        raise HTTPException(422, "Bestand mist verplichte kolom 'naam'")

    if monitoringlijst:
        db.query(Batch).filter_by(is_monitoringlijst=True).update(
            {"is_monitoringlijst": False},
        )

    batch = Batch(
        naam=naam or file.filename,
        jaar=jaar or datetime.now(timezone.utc).year,
        totaal=len(rows),
        is_monitoringlijst=monitoringlijst,
        geupload_door=current_user.id,
        # Een monitoringlijst hoort niet in een map: die heeft een eigen
        # module en zou anders tussen de onderzoekslijsten opduiken.
        map_id=None if monitoringlijst else map_id,
    )
    db.add(batch)
    db.flush()
    for row in rows:
        db.add(Company(
            batch_id=batch.id,
            vestigingsnummer=row.get("vestigingsnummer"),
            naam=row["naam"],
            gemeente=row.get("gemeente"),
            adres=row.get("adres"),
            sbi_code=row.get("sbi_code"),
            # Werd niet ingelezen, terwijl `Company` het veld heeft en de
            # queryplanner erop stuurt: zonder SBI-code herkent hij een
            # zorgaanbieder of school alleen nog aan de bedrijfsnaam. Wie de
            # kolom in zijn bestand zette, zag hem stil verdwijnen.
            sbi_omschrijving=row.get("sbi_omschrijving"),
            cb_er=row.get("cb_er"),
            kvk_nummer=row.get("kvk_nummer"),
            website_url=row.get("website_url"),
            telefoonnummer=row.get("telefoonnummer"),
        ))
    db.commit()
    return {"batch_id": batch.id, "aantal_companies": len(rows)}


@router.post("/{batch_id}/run")
async def start_batch(
    batch_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start autonome bronnenresearch voor de volledige lijst."""
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, f"batch {batch_id} bestaat niet")
    if batch.status == "running":
        return {"batch_id": batch.id, "status": batch.status,
                "verwerkt": batch.verwerkt, "totaal": batch.totaal}

    afgerond = (
        db.query(func.count(func.distinct(ResearchRun.company_id)))
        .filter_by(batch_id=batch.id, status="completed")
        .scalar() or 0
    )
    batch.status = "running"
    batch.verwerkt = afgerond
    batch.completed_at = None
    db.commit()
    background_tasks.add_task(_run_research_batch_background, batch.id)
    return {"batch_id": batch.id, "status": batch.status,
            "verwerkt": batch.verwerkt, "totaal": batch.totaal,
            "workflow": "autonome_bronnenresearch"}


@router.post("/{batch_id}/cancel")
def cancel_batch(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "batch niet gevonden")
    if batch.status != "running":
        raise HTTPException(409, f"batch heeft status '{batch.status}', niet 'running'")
    batch.status = "cancelled"
    db.commit()
    return {"batch_id": batch.id, "status": batch.status}


@router.post("/{batch_id}/reset-vastgelopen")
def reset_vastgelopen(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "batch niet gevonden")
    if batch.status != "running":
        raise HTTPException(409, "alleen een lopende batch kan worden gereset")
    batch.status = "pending"
    db.commit()
    return {"batch_id": batch.id, "status": batch.status}


@router.delete("/{batch_id}")
def delete_batch(batch_id: str, db: Session = Depends(get_db)):
    """Verwijder één lijst; ruim historische afhankelijkheden defensief mee op."""
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "batch niet gevonden")
    if batch.status == "running":
        raise HTTPException(409, "batch draait nog; annuleer eerst")

    company_ids = [row[0] for row in db.query(Company.id).filter_by(batch_id=batch_id)]
    if company_ids:
        for model in (CallListItem, WPRecord, ChatSession, Enrichment,
                      JaarverslagMonitoring, VastgoedRecord):
            db.query(model).filter(model.company_id.in_(company_ids)).delete(
                synchronize_session=False,
            )
        db.query(BronKandidaat).filter(
            BronKandidaat.company_id.in_(company_ids),
        ).delete(synchronize_session=False)
        db.query(ResearchRun).filter(
            ResearchRun.company_id.in_(company_ids),
        ).delete(synchronize_session=False)
    for model in (Candidate, AgentResult, PipelineRun):
        db.query(model).filter(model.batch_id == batch_id).delete(
            synchronize_session=False,
        )
    db.query(Company).filter_by(batch_id=batch_id).delete(synchronize_session=False)
    db.delete(batch)
    db.commit()
    return {"deleted": batch_id}


@router.get("")
def list_batches(
    map_id: str | None = None,
    losse_lijsten: bool = False,
    db: Session = Depends(get_db),
):
    """Lijsten, optioneel beperkt tot één map.

    Zonder filter blijft dit alle lijsten teruggeven, zodat bestaande
    aanroepers niet veranderen. `losse_lijsten=true` geeft juist alleen wat
    buiten elke map staat.
    """
    query = db.query(Batch).filter(Batch.is_monitoringlijst.isnot(True))
    if map_id:
        query = query.filter(Batch.map_id == map_id)
    elif losse_lijsten:
        query = query.filter(Batch.map_id.is_(None))
    batches = [
        batch for batch in query.order_by(Batch.created_at.desc()).all()
        if not _lijkt_monitoringlijst_batch(batch)
    ]
    uploader_ids = {batch.geupload_door for batch in batches if batch.geupload_door}
    naam_per_id = {
        user.id: user.naam
        for user in db.query(User).filter(User.id.in_(uploader_ids)).all()
    } if uploader_ids else {}
    return [{
        "id": batch.id,
        "naam": batch.naam,
        "jaar": batch.jaar,
        "status": batch.status,
        "totaal": batch.totaal,
        "verwerkt": batch.verwerkt,
        "created_at": batch.created_at.isoformat() + "Z" if batch.created_at else None,
        "completed_at": (
            batch.completed_at.isoformat() + "Z" if batch.completed_at else None
        ),
        "geupload_door_naam": naam_per_id.get(batch.geupload_door),
        "map_id": batch.map_id,
    } for batch in batches]


@router.get("/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "batch niet gevonden")
    latest_runs, top_candidates, accepted_run_ids = _latest_research_maps(db, batch_id)
    research = {
        "gestart": len(latest_runs),
        "afgerond": sum(run.status == "completed" for run in latest_runs.values()),
        "review_nodig": sum(
            run.status == "completed"
            and run.id not in accepted_run_ids
            and run.id in top_candidates
            for run in latest_runs.values()
        ),
        "geaccepteerd": len(accepted_run_ids),
        "niet_gevonden": sum(
            run.status == "completed" and run.resultaat_status == "niet_gevonden"
            for run in latest_runs.values()
        ),
        "fouten": sum(run.status == "error" for run in latest_runs.values()),
    }
    return {
        "id": batch.id, "naam": batch.naam, "jaar": batch.jaar,
        "status": batch.status, "totaal": batch.totaal,
        "verwerkt": batch.verwerkt, "workflow": "autonome_bronnenresearch",
        "research": research,
        "created_at": batch.created_at.isoformat() + "Z" if batch.created_at else None,
        "completed_at": (
            batch.completed_at.isoformat() + "Z" if batch.completed_at else None
        ),
    }


@router.get("/{batch_id}/companies")
def list_companies(batch_id: str, db: Session = Depends(get_db)):
    if db.get(Batch, batch_id) is None:
        raise HTTPException(404, "batch niet gevonden")
    latest_runs, top_candidates, accepted_run_ids = _latest_research_maps(db, batch_id)
    out = []
    for company in db.query(Company).filter_by(batch_id=batch_id).order_by(Company.naam):
        run = latest_runs.get(company.id)
        top = top_candidates.get(run.id) if run else None
        wp_bruikbaar = bool(
            top and top.eenheid == "werkzame_personen"
            and top.scope_class in {"vestiging", "limburg"}
        )
        out.append({
            "company_id": company.id,
            "naam": company.naam,
            "gemeente": company.gemeente,
            "vestigingsnummer": company.vestigingsnummer,
            "cb_er": company.cb_er,
            "kvk_nummer": company.kvk_nummer,
            "sbi_omschrijving": company.sbi_omschrijving,
            "research_run_id": run.id if run else None,
            "research_status": run.status if run else "niet_gestart",
            "research_resultaat_status": run.resultaat_status if run else None,
            "research_top_id": top.id if top else None,
            "research_top_url": top.url if top else None,
            "research_top_titel": top.titel if top else None,
            "research_top_type": top.brontype if top else None,
            "research_top_wp": top.wp_gevonden if wp_bruikbaar else None,
            "research_top_wp_raw": top.wp_gevonden if top else None,
            "research_top_wp_bruikbaar": wp_bruikbaar,
            "research_top_scope": top.scope_class if top else None,
            "research_top_score": top.ranking_score if top else None,
            "research_review_status": (
                "geaccepteerd" if run and run.id in accepted_run_ids
                else top.status if top else None
            ),
        })
    return out


@router.get("/{batch_id}/export.xlsx")
def export_bronnen(batch_id: str, db: Session = Depends(get_db)):
    """Exporteer per organisatie alleen de door een mens gekozen bron."""
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, "batch niet gevonden")
    latest_runs, gekozen_per_run, _ = _latest_research_maps(db, batch_id)
    reviewer_ids = {
        bron.reviewed_by for bron in gekozen_per_run.values() if bron.reviewed_by
    }
    reviewer_namen = {
        user.id: user.naam
        for user in db.query(User).filter(User.id.in_(reviewer_ids)).all()
    } if reviewer_ids else {}
    headers = [
        "Vestigingsnummer", "Organisatienaam", "Gemeente", "KvK-nummer",
        "Batchjaar", "Researchstatus", "Reviewstatus", "Bron-URL", "Brontype",
        "Documenttype", "Verslagjaar", "Informatiepeilmoment", "Gevonden waarde",
        "Eenheid", "Scope", "Identity class", "Bewijsfragment", "PDF-pagina",
        "Ranking-score", "Reviewredencode", "Reviewtoelichting", "Beoordeeld door",
        "Beoordeeld op",
    ]
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Gekozen bronnen"
    worksheet.append(headers)
    for company in db.query(Company).filter_by(batch_id=batch_id).order_by(Company.naam):
        run = latest_runs.get(company.id)
        bron = gekozen_per_run.get(run.id) if run else None
        if bron is not None and bron.status != "geaccepteerd":
            bron = None
        worksheet.append([
            company.vestigingsnummer, company.naam, company.gemeente,
            company.kvk_nummer, batch.jaar,
            run.status if run else "niet_gestart",
            bron.status if bron else None,
            bron.url if bron else None,
            bron.brontype if bron else None,
            bron.documenttype if bron else None,
            bron.verslagjaar if bron else None,
            bron.informatie_peilmoment if bron else None,
            bron.wp_gevonden if bron else None,
            bron.eenheid if bron else None,
            bron.scope_class if bron else None,
            bron.identity_class if bron else None,
            bron.bewijsfragment if bron else None,
            bron.bron_pagina if bron else None,
            bron.ranking_score if bron else None,
            bron.review_reason_code if bron else None,
            bron.review_reason if bron else None,
            reviewer_namen.get(bron.reviewed_by) if bron else None,
            bron.reviewed_at.isoformat() + "Z" if bron and bron.reviewed_at else None,
        ])
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    buffer = io.BytesIO()
    workbook.save(buffer)
    filename = f"bronnen_{batch.naam or batch.id}.xlsx".replace('"', "")
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
