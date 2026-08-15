from app.models import Batch, BronKandidaat, Company, ResearchRun
from app.research.organizations import (
    koppel_organisatie,
    vind_bestaande_bronnen,
)


def test_organisaties_worden_alleen_deterministisch_gekoppeld(db_session):
    batch = Batch(naam="test", jaar=2026)
    db_session.add(batch)
    db_session.flush()
    eerste = Company(
        batch_id=batch.id, naam="Zorggroep locatie A", kvk_nummer="12 34 56 78",
    )
    tweede = Company(
        batch_id=batch.id, naam="Volledig andere naam", kvk_nummer="12345678",
    )
    naamgenoot = Company(batch_id=batch.id, naam="Zorggroep locatie A")
    db_session.add_all([eerste, tweede, naamgenoot])
    db_session.flush()

    org_eerste = koppel_organisatie(db_session, eerste)
    org_tweede = koppel_organisatie(db_session, tweede)
    org_naamgenoot = koppel_organisatie(db_session, naamgenoot)

    assert org_eerste.id == org_tweede.id
    assert org_naamgenoot.id != org_eerste.id
    assert org_eerste.identity_key == "kvk:12345678"


def test_zustervestiging_deelt_alleen_brede_bronnen(db_session):
    batch = Batch(naam="test", jaar=2026)
    db_session.add(batch)
    db_session.flush()
    eerste = Company(batch_id=batch.id, naam="Groep A", kvk_nummer="12345678")
    tweede = Company(batch_id=batch.id, naam="Groep B", kvk_nummer="12345678")
    db_session.add_all([eerste, tweede])
    db_session.flush()
    koppel_organisatie(db_session, eerste)
    koppel_organisatie(db_session, tweede)
    run = ResearchRun(
        company_id=eerste.id, batch_id=batch.id, doel="test", status="completed",
    )
    db_session.add(run)
    db_session.flush()
    db_session.add_all([
        BronKandidaat(
            research_run_id=run.id, company_id=eerste.id,
            url="https://groep.test/jaarverslag.pdf",
            canonical_url="https://groep.test/jaarverslag.pdf",
            titel="Jaarverslag", brontype="jaarverslag", scope_class="concern",
        ),
        BronKandidaat(
            research_run_id=run.id, company_id=eerste.id,
            url="https://groep.test/locatie-a/team",
            canonical_url="https://groep.test/locatie-a/team",
            titel="Team A", brontype="officiele_website", scope_class="vestiging",
        ),
    ])
    db_session.flush()

    bronnen = vind_bestaande_bronnen(db_session, tweede)

    assert [bron.url for bron in bronnen] == ["https://groep.test/jaarverslag.pdf"]
    assert bronnen[0].van_andere_vestiging is True
