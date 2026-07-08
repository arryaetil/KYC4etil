"""Seed de vaste jaarverslag-monitoringlijst in de database.

Gebruik vanuit backend/:
    python -m scripts.seed_monitoringlijst

Het vaste CSV-bestand is data/jaarverslag_monitoringlijst.csv. Ondersteunde
kolommen: naam, cb_er en optioneel jaarverslag_url/laatste_bron_url/bron_url/url.
Als een URL aanwezig is, wordt die als baseline in JaarverslagMonitoring gezet.
"""
import argparse
import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import (AgentResult, Batch, CallListItem, Candidate, ChatSession,
                        Company, Enrichment, JaarverslagMonitoring, JaarverslagUpload,
                        PipelineRun, VastgoedRecord, WPRecord)  # noqa: E402

URL_KOLOMMEN = ("jaarverslag_url", "laatste_bron_url", "bron_url", "url")
DEFAULT_NAAM = "Jaarverslag-monitoringlijst"


def _tekst(waarde) -> str | None:
    if waarde is None:
        return None
    tekst = str(waarde).strip()
    return tekst or None


def _url_uit_rij(rij: dict) -> str | None:
    for kolom in URL_KOLOMMEN:
        url = _tekst(rij.get(kolom))
        if url:
            return url
    return None


def lees_monitoringlijst(pad: Path) -> list[dict]:
    with pad.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "naam" not in {h.strip().lower() for h in reader.fieldnames}:
            raise ValueError("monitoringlijst mist verplichte kolom 'naam'")

        rijen = []
        for rij in reader:
            genormaliseerd = {(k or "").strip().lower(): v for k, v in rij.items()}
            naam = _tekst(genormaliseerd.get("naam"))
            if not naam:
                continue
            rijen.append({
                "naam": naam,
                "cb_er": _tekst(genormaliseerd.get("cb_er")),
                "jaarverslag_url": _url_uit_rij(genormaliseerd),
            })
        return rijen


def _verwijder_batch_data(db, batch: Batch) -> None:
    company_ids = [c.id for c in db.query(Company).filter_by(batch_id=batch.id)]
    if company_ids:
        db.query(CallListItem).filter(CallListItem.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(WPRecord).filter(WPRecord.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(ChatSession).filter(ChatSession.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(JaarverslagUpload).filter(JaarverslagUpload.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(VastgoedRecord).filter(VastgoedRecord.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(Candidate).filter(Candidate.batch_id == batch.id).delete(synchronize_session=False)
        db.query(AgentResult).filter(AgentResult.batch_id == batch.id).delete(synchronize_session=False)
        db.query(Enrichment).filter(Enrichment.company_id.in_(company_ids)).delete(synchronize_session=False)
        db.query(JaarverslagMonitoring).filter(JaarverslagMonitoring.company_id.in_(company_ids)).delete(synchronize_session=False)
    db.query(PipelineRun).filter_by(batch_id=batch.id).delete(synchronize_session=False)
    db.query(Company).filter_by(batch_id=batch.id).delete(synchronize_session=False)
    db.delete(batch)


def seed_monitoringlijst(db, rijen: list[dict], jaar: int, naam: str = DEFAULT_NAAM) -> dict:
    """Vervangt de actieve watchlist door de vaste CSV-inhoud en zet URL-baselines."""
    for batch in db.query(Batch).filter_by(is_monitoringlijst=True).all():
        _verwijder_batch_data(db, batch)

    batch = Batch(naam=naam, jaar=jaar, totaal=len(rijen), is_monitoringlijst=True)
    db.add(batch)
    db.flush()

    urls_gevuld = 0
    for rij in rijen:
        company = Company(batch_id=batch.id, naam=rij["naam"], cb_er=rij.get("cb_er"))
        db.add(company)
        db.flush()
        url = rij.get("jaarverslag_url")
        if url:
            urls_gevuld += 1
            db.add(JaarverslagMonitoring(company_id=company.id, laatste_bron_url=url))

    db.commit()
    return {
        "batch_id": batch.id,
        "totaal": len(rijen),
        "urls_gevuld": urls_gevuld,
        "urls_ontbreken": len(rijen) - urls_gevuld,
    }


async def ontdek_ontbrekende_urls(db, batch_id: str, jaar: int) -> int:
    """Vul ontbrekende baseline-URL's via de live jaarverslag-agent."""
    from app.providers.live import LiveJaarverslagAgent

    agent = LiveJaarverslagAgent()
    gevuld = 0
    companies = db.query(Company).filter_by(batch_id=batch_id).all()
    for company in companies:
        status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one_or_none()
        if status and status.laatste_bron_url:
            continue
        finding = await agent.run(company.naam, jaar)
        if not finding or not finding.bron_url:
            continue
        if status is None:
            status = JaarverslagMonitoring(company_id=company.id)
            db.add(status)
        status.laatste_bron_url = finding.bron_url
        gevuld += 1
        db.commit()
    return gevuld


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(Path(__file__).resolve().parents[1] / "data" / "jaarverslag_monitoringlijst.csv"))
    parser.add_argument("--jaar", type=int, default=2026)
    parser.add_argument("--naam", default=DEFAULT_NAAM)
    parser.add_argument("--discover-missing-urls", action="store_true",
                        help="Zoek ontbrekende baseline-URL's via de live OpenAI jaarverslag-agent.")
    args = parser.parse_args()

    rijen = lees_monitoringlijst(Path(args.csv))
    db = SessionLocal()
    try:
        resultaat = seed_monitoringlijst(db, rijen, args.jaar, args.naam)
        if args.discover_missing_urls:
            settings = get_settings()
            if not settings.openai_api_key:
                print("Kan URL's niet live zoeken: OPENAI_API_KEY ontbreekt.")
                return 2
            gevonden = asyncio.run(ontdek_ontbrekende_urls(db, resultaat["batch_id"], args.jaar))
            resultaat["urls_gevuld"] += gevonden
            resultaat["urls_ontbreken"] -= gevonden
    finally:
        db.close()

    print(
        f"Monitoringlijst seeded: {resultaat['totaal']} organisaties, "
        f"{resultaat['urls_gevuld']} URL-baselines, "
        f"{resultaat['urls_ontbreken']} zonder URL"
    )
    print(f"Batch: {resultaat['batch_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
