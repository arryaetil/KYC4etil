"""Veilige organisatiekoppeling en selectie van herbruikbare bronnen."""
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from ..models import BronKandidaat, Company, Organization


_NIET_ORGANISATIEDOMEINEN = {
    "facebook.com", "instagram.com", "linkedin.com", "x.com",
}


def normaliseer_kvk(value: str | None) -> str | None:
    cijfers = re.sub(r"\D", "", value or "")
    return cijfers.zfill(8) if cijfers and len(cijfers) <= 8 else cijfers or None


def bevestigd_domein(url: str | None) -> str | None:
    if not url:
        return None
    kandidaat = url if "://" in url else f"https://{url}"
    domein = (urlsplit(kandidaat).hostname or "").lower().removeprefix("www.")
    if not domein or domein in _NIET_ORGANISATIEDOMEINEN:
        return None
    return domein


def organisatie_sleutel(
    company: Company,
    website_url: str | None = None,
) -> tuple[str, str | None, str | None]:
    kvk = normaliseer_kvk(company.kvk_nummer)
    domein = bevestigd_domein(website_url or company.website_url)
    if kvk:
        return f"kvk:{kvk}", kvk, domein
    if domein:
        return f"domain:{domein}", None, domein
    return f"company:{company.id}", None, None


def koppel_organisatie(
    db: Session,
    company: Company,
    website_url: str | None = None,
) -> Organization:
    """Koppel idempotent; nooit op een fuzzy naamvergelijking."""
    sleutel, kvk, domein = organisatie_sleutel(company, website_url)
    organisatie = db.query(Organization).filter_by(identity_key=sleutel).one_or_none()
    if organisatie is None:
        organisatie = Organization(
            identity_key=sleutel,
            naam=company.naam,
            kvk_nummer=kvk,
            website_domain=domein,
        )
        db.add(organisatie)
        db.flush()
    elif domein and not organisatie.website_domain:
        organisatie.website_domain = domein
    company.organization_id = organisatie.id
    return organisatie


@dataclass(frozen=True)
class BestaandeBron:
    url: str
    titel: str
    brontype: str
    documenttype: str | None
    scope_class: str | None
    van_andere_vestiging: bool


def vind_bestaande_bronnen(
    db: Session,
    company: Company,
    limiet: int = 12,
) -> list[BestaandeBron]:
    """Eigen bronnen plus uitsluitend brede bronnen van exacte zusterlocaties."""
    eigen = (
        db.query(BronKandidaat)
        .filter(
            BronKandidaat.company_id == company.id,
            BronKandidaat.bron_relevant.is_not(False),
        )
        .order_by(BronKandidaat.created_at.desc())
        .all()
    )
    gedeeld: list[BronKandidaat] = []
    if company.organization_id:
        gedeeld = (
            db.query(BronKandidaat)
            .join(Company, Company.id == BronKandidaat.company_id)
            .filter(
                Company.organization_id == company.organization_id,
                Company.id != company.id,
                BronKandidaat.scope_class.in_(("concern", "nederland")),
                BronKandidaat.bron_relevant.is_not(False),
            )
            .order_by(BronKandidaat.created_at.desc())
            .all()
        )

    resultaat: list[BestaandeBron] = []
    geziene_urls: set[str] = set()
    for bron in [*eigen, *gedeeld]:
        if bron.canonical_url in geziene_urls:
            continue
        geziene_urls.add(bron.canonical_url)
        resultaat.append(BestaandeBron(
            url=bron.url,
            titel=bron.titel or bron.url,
            brontype=bron.brontype,
            documenttype=bron.documenttype,
            scope_class=bron.scope_class,
            van_andere_vestiging=bron.company_id != company.id,
        ))
        if len(resultaat) >= limiet:
            break
    return resultaat
