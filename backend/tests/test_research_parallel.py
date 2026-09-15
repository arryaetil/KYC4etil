"""Meerdere organisaties tegelijk, en bronnen die niet twee keer gelezen worden.

Een lijst was precies zo lang als de som van haar runs — op productie gemeten
100% bezetting, dus 108 vestigingen betekende 6 uur 19. Deze tests leggen vast
dat er nu meerdere naast elkaar lopen, dat de voortgang daar niet onder lijdt,
en dat een zusterbron uit dezelfde lijst wordt overgenomen in plaats van
opnieuw opgehaald.
"""
import asyncio

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import Batch, BronKandidaat, Company, ResearchRun
from app.research import service
from app.research.organizations import koppel_organisatie, vind_bestaande_bronnen


@pytest.fixture
def gedeelde_sessies(db_session, monkeypatch):
    """`run_research_batch` opent zijn eigen sessies via `SessionLocal`.

    Die wijst naar de echte database en niet naar de testdatabase van de
    fixtures, dus zonder dit ziet de code onder test de lijst niet staan en
    valt hij meteen terug — een test die niets test.
    """
    maker = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, expire_on_commit=False,
    )
    monkeypatch.setattr(service, "SessionLocal", maker)
    return maker


def _lijst(db_session, aantal: int, kvk_gedeeld: bool = False) -> Batch:
    batch = Batch(naam="parallel", jaar=2026, totaal=aantal)
    db_session.add(batch)
    db_session.flush()
    for nummer in range(aantal):
        db_session.add(Company(
            batch_id=batch.id,
            naam=f"Vestiging {nummer}",
            vestigingsnummer=f"P-{nummer}",
            kvk_nummer="12345678" if kvk_gedeeld else f"1234{nummer:04d}",
            website_url="https://concern.example" if kvk_gedeeld
            else f"https://vestiging-{nummer}.example",
        ))
    db_session.commit()
    return batch


@pytest.mark.asyncio
async def test_organisaties_lopen_naast_elkaar(db_session, monkeypatch, gedeelde_sessies):
    batch = _lijst(db_session, aantal=6)
    monkeypatch.setattr(
        get_settings(), "research_max_parallel_companies", 3, raising=False,
    )
    tegelijk = 0
    hoogste = 0

    async def nep_run(run_id: str):
        nonlocal tegelijk, hoogste
        tegelijk += 1
        hoogste = max(hoogste, tegelijk)
        await asyncio.sleep(0.05)
        tegelijk -= 1

    monkeypatch.setattr(service, "run_research_run", nep_run)

    await service.run_research_batch(batch.id)

    assert hoogste == 3, f"er liepen er {hoogste} tegelijk, verwacht 3"


@pytest.mark.asyncio
async def test_voortgang_telt_elke_organisatie_ondanks_gelijktijdigheid(
    db_session, monkeypatch, gedeelde_sessies,
):
    """`verwerkt += 1` in Python is lezen, optellen en terugschrijven.

    Zolang er één organisatie tegelijk draaide kon daar niets tussen komen. Nu
    wel, en dan verdwijnt er stilletjes voortgang uit de teller.
    """
    batch = _lijst(db_session, aantal=8)
    monkeypatch.setattr(
        get_settings(), "research_max_parallel_companies", 8, raising=False,
    )

    async def nep_run(run_id: str):
        await asyncio.sleep(0.02)

    monkeypatch.setattr(service, "run_research_run", nep_run)

    await service.run_research_batch(batch.id)

    db_session.expire_all()
    ververst = db_session.get(Batch, batch.id)
    assert ververst.verwerkt == 8
    assert ververst.status == "review"


@pytest.mark.asyncio
async def test_geannuleerde_lijst_blijft_geannuleerd(db_session, monkeypatch, gedeelde_sessies):
    """De oude lus verliet de functie bij "cancelled" en kwam nooit bij de
    afronding; de gather komt daar altijd langs."""
    batch = _lijst(db_session, aantal=3)
    monkeypatch.setattr(
        get_settings(), "research_max_parallel_companies", 1, raising=False,
    )

    async def annuleer_tussendoor(run_id: str):
        with gedeelde_sessies() as db:
            lopende = db.get(Batch, batch.id)
            lopende.status = "cancelled"
            db.commit()

    monkeypatch.setattr(service, "run_research_run", annuleer_tussendoor)

    await service.run_research_batch(batch.id)

    db_session.expire_all()
    assert db_session.get(Batch, batch.id).status == "cancelled"


def _zusterbron(db_session, batch: Batch) -> tuple[Company, Company]:
    eerste, tweede = (
        db_session.query(Company).filter_by(batch_id=batch.id)
        .order_by(Company.vestigingsnummer).all()[:2]
    )
    for company in (eerste, tweede):
        koppel_organisatie(db_session, company, company.website_url)
    run = ResearchRun(company_id=eerste.id, batch_id=batch.id,
                      doel="bron", status="completed")
    db_session.add(run)
    db_session.flush()
    db_session.add(BronKandidaat(
        research_run_id=run.id, company_id=eerste.id,
        url="https://concern.example/jaarverslag-2025.pdf",
        canonical_url="https://concern.example/jaarverslag-2025.pdf",
        titel="Jaarverslag 2025", brontype="jaarverslag",
        documenttype="jaarverslag", verslagjaar=2025,
        wp_gevonden=852, eenheid="werkzame_personen",
        bewijsfragment="Er werken 852 medewerkers.",
        scope_class="concern", status="voorgesteld", rang=1,
        validaties={"wp_extractie": "gevonden"},
    ))
    db_session.commit()
    return eerste, tweede


def test_zusterbron_komt_met_uitgelezen_waarden_mee(db_session):
    batch = _lijst(db_session, aantal=2, kvk_gedeeld=True)
    _, tweede = _zusterbron(db_session, batch)

    bronnen = vind_bestaande_bronnen(db_session, tweede)

    assert len(bronnen) == 1
    bron = bronnen[0]
    assert bron.van_andere_vestiging is True
    assert bron.zelfde_lijst is True
    assert bron.gelezen is True
    # Zonder deze waarden zou de bron opnieuw opgehaald en uitgelezen moeten
    # worden; dát is precies wat we willen overslaan.
    assert bron.wp_gevonden == 852
    assert bron.bewijsfragment == "Er werken 852 medewerkers."
    assert bron.verslagjaar == 2025


@pytest.mark.asyncio
async def test_zusterbron_uit_dezelfde_lijst_wordt_niet_opnieuw_gelezen(db_session):
    from app.research.query_planner import QueryContext
    from app.research.seeds import verzamel_seed_documenten

    batch = _lijst(db_session, aantal=2, kvk_gedeeld=True)
    _, tweede = _zusterbron(db_session, batch)
    bronnen = vind_bestaande_bronnen(db_session, tweede)

    gelezen: list[str] = []

    class Tools:
        async def inspect(self, context, query, result):
            gelezen.append(result.url)
            return None

        async def find_officiele_website(self, context):
            return None

        async def find_nieuwste_officiele_document(self, context):
            return None

        async def find_jaarverslag(self, context):
            return None

    documenten = await verzamel_seed_documenten(
        Tools(),
        QueryContext(naam=tweede.naam, gevraagd_jaar=2025,
                     website_url=tweede.website_url),
        {"website"},
        bestaande_bronnen=bronnen,
    )

    assert gelezen == [], f"deze bron is toch opgehaald: {gelezen}"
    hergebruikt = [
        document for document in documenten
        if (document.raw_data or {}).get("hergebruikt_zonder_herlezen")
    ]
    assert len(hergebruikt) == 1
    assert hergebruikt[0].wp_gevonden == 852
    # Waar het getal over gaat is een vraag over déze vestiging; die wordt
    # opnieuw beantwoord en niet van de zuster overgenomen.
    assert hergebruikt[0].scope_class is None


@pytest.mark.asyncio
async def test_bron_uit_een_andere_lijst_wordt_wel_opnieuw_gelezen(db_session):
    """Alleen binnen dezelfde lijstverwerking staat vast dat de bron zojuist
    gelezen is. Een kaart uit een oudere lijst kan achterhaald zijn."""
    from app.research.query_planner import QueryContext
    from app.research.seeds import verzamel_seed_documenten

    batch = _lijst(db_session, aantal=2, kvk_gedeeld=True)
    eerste, tweede = _zusterbron(db_session, batch)
    # Zet de zuster in een andere lijst; de organisatie blijft dezelfde.
    andere = Batch(naam="oudere lijst", jaar=2025, totaal=1)
    db_session.add(andere)
    db_session.flush()
    eerste.batch_id = andere.id
    db_session.commit()

    bronnen = vind_bestaande_bronnen(db_session, tweede)
    assert bronnen and bronnen[0].zelfde_lijst is False

    gelezen: list[str] = []

    class Tools:
        async def inspect(self, context, query, result):
            gelezen.append(result.url)
            return None

        async def find_officiele_website(self, context):
            return None

        async def find_nieuwste_officiele_document(self, context):
            return None

        async def find_jaarverslag(self, context):
            return None

    await verzamel_seed_documenten(
        Tools(),
        QueryContext(naam=tweede.naam, gevraagd_jaar=2025,
                     website_url=tweede.website_url),
        {"website"},
        bestaande_bronnen=bronnen,
    )

    assert gelezen == ["https://concern.example/jaarverslag-2025.pdf"]

def test_browserrem_groeit_mee_met_het_aantal_organisaties():
    """De semafoor in fetch.py geldt voor het hele proces, dus alle
    organisaties delen die plaatsen. Toen dit een vast getal was kregen vier
    organisaties samen nog steeds drie renders tegelijk, en stond het
    parallelle werk alsnog in de rij. Dat verband is nergens af te lezen aan
    de code die hem gebruikt, vandaar deze test."""
    settings = get_settings()
    per_organisatie = settings.crawl4ai_max_parallel_per_organisatie
    origineel = settings.research_max_parallel_companies
    try:
        settings.research_max_parallel_companies = 4
        assert settings.crawl4ai_max_parallel == per_organisatie * 4

        # Op 1 is het gedrag exact als vóór het parallelliseren: de rem is
        # dan weer precies het getal per organisatie.
        settings.research_max_parallel_companies = 1
        assert settings.crawl4ai_max_parallel == per_organisatie

        # 0 of minder mag de browser niet stilzetten.
        settings.research_max_parallel_companies = 0
        assert settings.crawl4ai_max_parallel == per_organisatie
    finally:
        settings.research_max_parallel_companies = origineel
