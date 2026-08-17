"""Eenmalig: vul ontbrekende monitoringbronnen aan uit bestaande researchruns.

De monitoring zoekt per organisatie opnieuw naar een jaarverslag, maar
`_beste_moderne_jaarverslagbron` kijkt alleen naar `BronKandidaat`-rijen van
dezélfde `company_id`. Een organisatie op de watchlist is een eigen
Company-rij, dus een jaarverslag dat een batchrun bij een andere rij vond,
komt nooit in beeld. Gemeten op de watchlist van 10-08-2026: 112 van de 205
organisaties zonder bron, terwijl er elders 315 jaarverslagkandidaten stonden.

Dit is bewust een eenmalig script en géén pipelinewijziging: de
batch-analysepipeline (`app/research/`) blijft ongemoeid.

## Waarom uitsluitend op websitedomein wordt gekoppeld

`CLAUDE.md` en `Organization` staan maar twee identiteitssleutels toe: een
exact KvK-nummer of een bevestigd websitedomein. Naamgelijkenis is expliciet
géén sleutel, en dat is hier geen theorie. Een naam-match levert bij
"Stichting Pergamijn" een kandidaat op met 2.400 WP die in werkelijkheid naar
`zorgboog.nl/.../Jaarverantwoording-Zorgboog-2023.pdf` wijst — het jaarverslag
van een andere zorgorganisatie, opgeslagen onder de verkeerde naam en met een
verkeerd verslagjaar. De domeineis wijst die kandidaat vanzelf af.

De watchlist-organisaties hebben geen KvK-nummer (0 van de 205) maar wel een
website (204 van de 205), dus het domein is hier de enige bruikbare sleutel.

## Gebruik

Standaard een droogloop; er wordt niets geschreven zonder `--toepassen`.

    cd backend
    DATABASE_URL=... python -m scripts.backfill_monitoring_uit_bronkandidaten
    DATABASE_URL=... python -m scripts.backfill_monitoring_uit_bronkandidaten --toepassen
"""
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Batch, BronKandidaat, Company, JaarverslagMonitoring,
)

# Documenttypen die als jaarverslag mogen doorgaan. Gelijk aan de set die
# `research/seeds.py` en `ranking._menselijke_waarde` als formeel document
# behandelen, zodat "formeel document" hier hetzelfde betekent als daar.
FORMELE_DOCUMENTTYPEN = {"jaarverslag", "jaarrekening", "bestuursverslag"}


def _domein(url: str | None) -> str | None:
    host = (urlsplit(url or "").netloc or "").lower().split(":")[0]
    return host.removeprefix("www.") or None


@dataclass
class Voorstel:
    company: Company
    kandidaat: BronKandidaat
    domein: str


def _zoek_voorstellen(db, batch: Batch) -> list[Voorstel]:
    """Eén voorstel per organisatie zonder bron, op het hoogste verslagjaar."""
    bron_per_company = {
        status.company_id: status.laatste_bron_url
        for status in (
            db.query(JaarverslagMonitoring)
            .join(Company, Company.id == JaarverslagMonitoring.company_id)
            .filter(Company.batch_id == batch.id)
        )
    }
    zonder_bron = [
        company
        for company in db.query(Company).filter_by(batch_id=batch.id)
        if not bron_per_company.get(company.id)
    ]

    kandidaten_per_domein: dict[str, list[BronKandidaat]] = {}
    for kandidaat in (
        db.query(BronKandidaat)
        .join(Company, Company.id == BronKandidaat.company_id)
        .filter(
            Company.batch_id != batch.id,
            BronKandidaat.status != "afgewezen",
        )
    ):
        if not (
            kandidaat.brontype == "jaarverslag"
            or kandidaat.documenttype in FORMELE_DOCUMENTTYPEN
        ):
            continue
        domein = _domein(kandidaat.url)
        if domein:
            kandidaten_per_domein.setdefault(domein, []).append(kandidaat)

    voorstellen: list[Voorstel] = []
    for company in zonder_bron:
        domein = _domein(company.website_url)
        if not domein:
            continue
        kandidaten = kandidaten_per_domein.get(domein)
        if not kandidaten:
            continue
        # Het hoogste verslagjaar wint; zonder jaartal telt als 0, zodat een
        # gedateerde bron altijd voorgaat op een ongedateerde.
        beste = max(kandidaten, key=lambda item: item.verslagjaar or 0)
        voorstellen.append(Voorstel(company, beste, domein))
    return voorstellen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--toepassen", action="store_true",
        help="schrijf de gevonden bronnen weg (standaard: alleen tonen)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        batch = (
            db.query(Batch)
            .filter_by(is_monitoringlijst=True)
            .order_by(Batch.created_at.desc())
            .first()
        )
        if batch is None:
            print("Geen actieve monitoringlijst gevonden.")
            return 1
        doeljaar = batch.jaar - 1 if batch.jaar is not None else None
        print(f"Watchlist: {batch.naam} (jaar {batch.jaar}, doeljaar {doeljaar})")

        voorstellen = _zoek_voorstellen(db, batch)
        if not voorstellen:
            print("Geen ontbrekende bron is elders op hetzelfde domein te vinden.")
            return 0

        print(f"\n{len(voorstellen)} organisatie(s) met een bron op het eigen domein:\n")
        for voorstel in voorstellen:
            jaar = voorstel.kandidaat.verslagjaar
            markering = (
                "actueel" if doeljaar is not None and (jaar or 0) >= doeljaar
                else "ouder"
            )
            print(f"  {voorstel.company.naam[:38]:<38} {voorstel.domein:<24} "
                  f"jaar={str(jaar):<6} {markering}")
            print(f"      {voorstel.kandidaat.url}")

        if not args.toepassen:
            print("\nDroogloop — er is niets gewijzigd. Draai met --toepassen "
                  "om deze bronnen vast te leggen.")
            return 0

        for voorstel in voorstellen:
            status = (
                db.query(JaarverslagMonitoring)
                .filter_by(company_id=voorstel.company.id)
                .one_or_none()
            )
            if status is None:
                status = JaarverslagMonitoring(company_id=voorstel.company.id)
                db.add(status)
            status.laatste_bron_url = voorstel.kandidaat.url
            status.laatste_verslagjaar = voorstel.kandidaat.verslagjaar
            # `laatst_gecontroleerd_op` bewust niet zetten: er is niets
            # gecontroleerd. De bron komt uit een eerdere researchrun en de
            # eerstvolgende monitoringronde mag hem gewoon hervalideren.
        db.commit()
        print(f"\n{len(voorstellen)} monitoringbron(nen) vastgelegd.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
