"""Veilige organisatiekoppeling en selectie van herbruikbare bronnen."""
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import BronKandidaat, Company, Organization
from .validation import WP_EXTRACTIE


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
        try:
            # Een savepoint, geen kale flush: sinds vestigingen gelijktijdig
            # worden onderzocht komen twee vestigingen van dezelfde organisatie
            # hier tegelijk langs, allebei met dezelfde identity_key. De één
            # wint, de ander krijgt de unique-constraint terug — en dat is geen
            # fout maar precies de bedoeling van die constraint. Zonder het
            # savepoint zou de afhandeling de hele transactie meenemen.
            with db.begin_nested():
                organisatie = Organization(
                    identity_key=sleutel,
                    naam=company.naam,
                    kvk_nummer=kvk,
                    website_domain=domein,
                )
                db.add(organisatie)
        except IntegrityError:
            organisatie = (
                db.query(Organization).filter_by(identity_key=sleutel).one()
            )
    if organisatie is not None and domein and not organisatie.website_domain:
        organisatie.website_domain = domein
    company.organization_id = organisatie.id
    return organisatie


@dataclass(frozen=True)
class BestaandeBron:
    """Een bron die er al ligt, mét wat er de vorige keer uit gelezen is.

    De extractie werd tot nu toe weggegooid en opnieuw gedaan: elke vestiging
    haalde hetzelfde jaarverslag opnieuw op en liet het opnieuw door het model
    lezen. In de lijst "Copy of Zorggroep" stonden 407 bronkaarten over 149
    unieke URL's — hetzelfde document dus gemiddeld 2,7 keer gelezen.

    Wat per vestiging écht verschilt is het oordeel (hoort deze bron bij déze
    vestiging, en waar gaat het getal over), niet het lezen. Vandaar dat de
    uitgelezen waarden meekomen en `scope_class` alleen geldt voor de vestiging
    die hem zelf heeft laten bepalen.
    """

    url: str
    titel: str
    brontype: str
    documenttype: str | None
    scope_class: str | None
    van_andere_vestiging: bool
    # Uit dezelfde lijstverwerking. Alleen dan staat vast dat de bron zojuist
    # is gelezen en er niets tussentijds veranderd kan zijn.
    zelfde_lijst: bool = False
    # Is er destijds daadwerkelijk in dit document naar een getal gezocht?
    gelezen: bool = False
    verslagjaar: int | None = None
    publicatiedatum: date | None = None
    informatie_peilmoment: str | None = None
    wp_gevonden: int | None = None
    eenheid: str | None = None
    bewijsfragment: str | None = None
    bron_pagina: int | None = None
    raw_data: dict | None = None


def _is_gelezen(bron: BronKandidaat) -> bool:
    """Is er destijds echt in dit document gezocht?

    `wp_extractie` is precies daarvoor gezet: het onderscheidt "gezocht en er
    staat geen getal in" van "hier is nog niet naar gekeken". Oudere kaarten
    hebben die sleutel niet, en daar is een getal of een citaat het bewijs dat
    er gelezen is.
    """
    if (bron.validaties or {}).get(WP_EXTRACTIE):
        return True
    return bron.wp_gevonden is not None or bool(bron.bewijsfragment)


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
    zelfde_lijst_ids: set[str] = set()
    if company.organization_id:
        zelfde_lijst_ids = {
            company_id
            for (company_id,) in db.query(Company.id).filter(
                Company.organization_id == company.organization_id,
                Company.batch_id == company.batch_id,
            )
        }
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
        van_andere_vestiging = bron.company_id != company.id
        resultaat.append(BestaandeBron(
            url=bron.url,
            titel=bron.titel or bron.url,
            brontype=bron.brontype,
            documenttype=bron.documenttype,
            scope_class=bron.scope_class,
            van_andere_vestiging=van_andere_vestiging,
            zelfde_lijst=bron.company_id in zelfde_lijst_ids,
            gelezen=_is_gelezen(bron),
            verslagjaar=bron.verslagjaar,
            publicatiedatum=bron.publicatiedatum,
            informatie_peilmoment=bron.informatie_peilmoment,
            wp_gevonden=bron.wp_gevonden,
            eenheid=bron.eenheid,
            bewijsfragment=bron.bewijsfragment,
            bron_pagina=bron.bron_pagina,
            raw_data=bron.raw_data,
        ))
        if len(resultaat) >= limiet:
            break
    return resultaat
