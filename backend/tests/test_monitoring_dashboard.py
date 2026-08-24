"""Tests voor de dashboard-niveau /monitoring-endpoints (geen batch_id in de URL)."""
from datetime import datetime, timezone
from io import BytesIO

from app.models import (
    BronKandidaat, Company, JaarverslagMonitoring, PipelineRun, ResearchRun,
    User,
)
from app.research.urls import canonicaliseer_url
from app.routers import monitoring as monitoring_router


def _zorg_voor_test_user(db_session):
    """Uploads koppelen geupload_door (FK naar users.id) aan de ingelogde
    testgebruiker; die rij bestaat niet automatisch in de testdatabase."""
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(id="test-user-id", naam="Test User", email="test@etil.nl",
                            rol="admin", password_hash=""))
        db_session.commit()


def test_monitoring_status_zonder_watchlist_geeft_lege_staat(client):
    response = client.get("/monitoring")

    assert response.status_code == 200
    assert response.json() == {
        "batch": None, "doeljaar": None, "totaal": 0, "gecontroleerd": 0,
        "bronnen_gevonden": 0, "bronnen_ontbreken": 0,
        "actueel": 0, "verouderd": 0, "ontbreekt": 0, "jaren_verdeling": [],
        "nieuwe_bevindingen": 0, "fouten": 0, "companies": [],
    }


def test_monitoring_status_met_actieve_watchlist(client, db_session):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(
            b"naam\nGecontroleerde Organisatie\nNog Niet Gecontroleerd\n"
        ), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    companies = {c.naam: c for c in db_session.query(Company).filter_by(batch_id=batch_id)}
    gecontroleerd = companies["Gecontroleerde Organisatie"]

    nu = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(JaarverslagMonitoring(
        company_id=gecontroleerd.id, laatste_bron_url="https://voorbeeld.test/jaarverslag.pdf",
        laatst_gecontroleerd_op=nu,
    ))
    db_session.add(PipelineRun(batch_id=batch_id, company_id=gecontroleerd.id,
                               stap="jaarverslag_monitoring", status="new", duur_ms=100))
    db_session.commit()

    response = client.get("/monitoring")

    assert response.status_code == 200
    data = response.json()
    assert data["batch"] == {"id": batch_id, "naam": "watchlist", "jaar": 2026}
    assert data["totaal"] == 2
    assert data["gecontroleerd"] == 1
    assert data["bronnen_gevonden"] == 1
    assert data["bronnen_ontbreken"] == 1
    assert data["nieuwe_bevindingen"] == 1
    assert data["fouten"] == 0

    per_naam = {c["naam"]: c for c in data["companies"]}
    assert per_naam["Gecontroleerde Organisatie"]["nieuwe_bevinding"] is True
    assert per_naam["Gecontroleerde Organisatie"]["bron_status"] == "gevonden"
    assert "wp_kandidaat" not in per_naam["Gecontroleerde Organisatie"]
    assert per_naam["Nog Niet Gecontroleerd"]["laatst_gecontroleerd_op"] is None
    assert per_naam["Nog Niet Gecontroleerd"]["bron_status"] == "ontbreekt"


def test_monitoring_dashboard_toont_alleen_laatste_controleuitkomst(
    client, db_session,
):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-latest&jaar=2026&monitoringlijst=true",
        files={"file": (
            "orgs.csv",
            BytesIO(b"naam\nOrganisatie X\n"),
            "text/csv",
        )},
    )
    batch_id = upload.json()["batch_id"]
    company = db_session.query(Company).filter_by(batch_id=batch_id).one()
    db_session.add_all([
        PipelineRun(
            batch_id=batch_id,
            company_id=company.id,
            stap="jaarverslag_monitoring",
            status="ok",
            duur_ms=100,
            created_at=datetime(2026, 7, 1),
        ),
        PipelineRun(
            batch_id=batch_id,
            company_id=company.id,
            stap="jaarverslag_monitoring",
            status="skipped",
            duur_ms=100,
            created_at=datetime(2026, 7, 8),
        ),
    ])
    db_session.commit()

    data = client.get("/monitoring").json()

    assert data["nieuwe_bevindingen"] == 0
    assert data["companies"][0]["nieuwe_bevinding"] is False


def test_monitoring_dashboard_noemt_betere_extractie_geen_nieuw_jaarverslag(
    client, db_session,
):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-update&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie X\n"), "text/csv")},
    )
    batch_id = upload.json()["batch_id"]
    company = db_session.query(Company).filter_by(batch_id=batch_id).one()
    db_session.add(PipelineRun(
        batch_id=batch_id,
        company_id=company.id,
        stap="jaarverslag_monitoring",
        status="updated",
        duur_ms=100,
    ))
    db_session.commit()

    data = client.get("/monitoring").json()

    assert data["nieuwe_bevindingen"] == 0
    assert data["companies"][0]["nieuwe_bevinding"] is False


def test_monitoring_run_zonder_watchlist_geeft_404(client):
    response = client.post("/monitoring/run")
    assert response.status_code == 404


def test_monitoring_run_start_achtergrondtaak(client, db_session, monkeypatch):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-run&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie X\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    gestart = []

    def fake_run_monitoring_watchlist_background(
        limit=None, offset=0, hercontroleer_actuele=False,
    ) -> None:
        gestart.append((limit, offset))

    monkeypatch.setattr(monitoring_router, "run_monitoring_watchlist_background",
                        fake_run_monitoring_watchlist_background)

    response = client.post("/monitoring/run")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch_id,
        "aantal_companies": 1,
        "offset": 0,
        "overgeslagen_actueel": 0,
    }
    assert gestart == [(None, 0)]


def test_monitoring_run_met_limit_beperkt_aantal_companies(client, db_session, monkeypatch):
    """Met ?limit=N wordt maar een deel van de watchlist gecontroleerd — bedoeld
    om tijdens ontwikkelen/testen niet steeds de volledige (kostbare) live-lijst
    te hoeven doorlopen."""
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-run-groot&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(
            b"naam\nOrganisatie A\nOrganisatie B\nOrganisatie C\n"
        ), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    gestart = []

    def fake_run_monitoring_watchlist_background(
        limit=None, offset=0, hercontroleer_actuele=False,
    ) -> None:
        gestart.append((limit, offset))

    monkeypatch.setattr(monitoring_router, "run_monitoring_watchlist_background",
                        fake_run_monitoring_watchlist_background)

    response = client.post("/monitoring/run?limit=2")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch_id,
        "aantal_companies": 2,
        "offset": 0,
        "overgeslagen_actueel": 0,
    }
    assert gestart == [(2, 0)]


def test_monitoring_run_met_limit_groter_dan_watchlist_gebruikt_totaal(client, db_session, monkeypatch):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-run-klein&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie X\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    monkeypatch.setattr(
        monitoring_router,
        "run_monitoring_watchlist_background",
        lambda limit=None, offset=0, hercontroleer_actuele=False: None,
    )

    response = client.post("/monitoring/run?limit=50")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch_id,
        "aantal_companies": 1,
        "offset": 0,
        "overgeslagen_actueel": 0,
    }


def test_monitoring_run_met_offset_start_bij_latere_organisatie(
    client, db_session, monkeypatch,
):
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-offset&jaar=2026&monitoringlijst=true",
        files={"file": (
            "orgs.csv",
            BytesIO(b"naam\nA\nB\nC\nD\n"),
            "text/csv",
        )},
    )
    batch_id = upload.json()["batch_id"]
    gestart = []
    monkeypatch.setattr(
        monitoring_router,
        "run_monitoring_watchlist_background",
        lambda limit=None, offset=0, hercontroleer_actuele=False:
            gestart.append((limit, offset)),
    )

    response = client.post("/monitoring/run?limit=2&offset=2")

    assert response.status_code == 200
    assert response.json() == {
        "batch_id": batch_id,
        "aantal_companies": 2,
        "offset": 2,
        "overgeslagen_actueel": 0,
    }
    assert gestart == [(2, 2)]


def test_monitoring_status_geeft_bewijsplek_van_de_gevonden_bron(client, db_session):
    """De monitoringvondst moet de reviewer naar de WP-plek in het PDF brengen.

    De monitoringronde legt paginanummer en bewijsfragment vast op de
    BronKandidaat die zij zelf aanmaakt. Zonder die twee velden in de payload
    bouwt de frontend een viewer-URL zonder `#page=`, en opent het jaarverslag
    op pagina 1 in plaats van bij het WP-getal.
    """
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-bewijs&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie Met Bewijs\n"), "text/csv")},
    )
    batch_id = upload.json()["batch_id"]
    company = db_session.query(Company).filter_by(batch_id=batch_id).one()

    url = "https://voorbeeld.test/jaarverslag-2025.pdf"
    nu = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(JaarverslagMonitoring(
        company_id=company.id, laatste_bron_url=url,
        laatste_verslagjaar=2025, laatst_gecontroleerd_op=nu,
    ))
    run = ResearchRun(
        company_id=company.id, batch_id=batch_id,
        doel="periodieke jaarverslagmonitoring", gevraagd_jaar=2025,
        status="completed", resultaat_status="review_nodig",
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(BronKandidaat(
        research_run_id=run.id, company_id=company.id, url=url,
        canonical_url=canonicaliseer_url(url), titel="Jaarverslag 2025",
        brontype="jaarverslag", documenttype="jaarverslag", verslagjaar=2025,
        wp_gevonden=47, eenheid="werkzame_personen",
        bewijsfragment="47 medewerkers in dienst", bron_pagina=14,
        status="voorgesteld", rang=1,
    ))
    db_session.commit()

    data = client.get("/monitoring").json()
    vondst = {c["naam"]: c for c in data["companies"]}["Organisatie Met Bewijs"]

    assert vondst["laatste_bron_url"] == url
    assert vondst["bron_pagina"] == 14
    assert vondst["bewijsfragment"] == "47 medewerkers in dienst"


def _watchlist_met_verslagjaren(
    client, db_session, naam, jaar, organisaties, met_bronkaart=(),
):
    """Zet een watchlist op waarin elke organisatie een bekend verslagjaar heeft.

    `organisaties` is een dict naam -> (bron_url, verslagjaar). Een lege URL
    betekent: nooit een bron gevonden.

    `met_bronkaart` noemt de organisaties die óók een beoordeelbare
    bronkandidaat hebben. Dat onderscheid doet ertoe: een verslag over het
    doeljaar zonder bronkaart moet nog wél gecontroleerd worden, anders krijgt
    de reviewer daar nooit iets te beoordelen.
    """
    _zorg_voor_test_user(db_session)
    csv = "naam\n" + "\n".join(organisaties) + "\n"
    upload = client.post(
        f"/batches/upload?naam={naam}&jaar={jaar}&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(csv.encode()), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]
    companies = {
        c.naam: c for c in db_session.query(Company).filter_by(batch_id=batch_id)
    }
    nu = datetime.now(timezone.utc).replace(tzinfo=None)
    for organisatie, (url, verslagjaar) in organisaties.items():
        company = companies[organisatie]
        db_session.add(JaarverslagMonitoring(
            company_id=company.id,
            laatste_bron_url=url or None,
            laatste_verslagjaar=verslagjaar,
            laatst_gecontroleerd_op=nu,
        ))
        if organisatie not in met_bronkaart or not url:
            continue
        run = ResearchRun(
            company_id=company.id, batch_id=batch_id,
            doel="periodieke jaarverslagmonitoring", gevraagd_jaar=jaar - 1,
            status="completed", resultaat_status="review_nodig",
        )
        db_session.add(run)
        db_session.flush()
        db_session.add(BronKandidaat(
            research_run_id=run.id, company_id=company.id,
            url=url, canonical_url=canonicaliseer_url(url),
            brontype="jaarverslag", documenttype="jaarverslag",
            verslagjaar=verslagjaar, status="voorgesteld", rang=1,
        ))
    db_session.commit()
    return batch_id, companies


def test_monitoring_deelt_organisaties_in_op_verslagjaar(client, db_session):
    """De hoofdvraag: van hoeveel hebben we het verslag over het doeljaar.

    Watchlistjaar 2026 betekent doeljaar 2025 — een jaarverslag over jaar X
    verschijnt pas in X+1. Een bron zonder herkenbaar jaartal telt niet als
    actueel: we weten dan niet of hij over het doeljaar gaat.
    """
    _watchlist_met_verslagjaren(client, db_session, "jaarbuckets", 2026, {
        "Actueel": ("https://x.test/jaarverslag-2025.pdf", 2025),
        "Ouder": ("https://x.test/jaarverslag-2024.pdf", 2024),
        "Zonder jaartal": ("https://x.test/jaarverslagsite/", None),
        "Niets gevonden": ("", None),
    })

    data = client.get("/monitoring").json()

    assert data["doeljaar"] == 2025
    assert data["actueel"] == 1
    assert data["verouderd"] == 2
    assert data["ontbreekt"] == 1
    assert data["jaren_verdeling"] == [
        {"verslagjaar": 2025, "aantal": 1},
        {"verslagjaar": 2024, "aantal": 1},
        {"verslagjaar": None, "aantal": 1},
    ]

    per_naam = {c["naam"]: c for c in data["companies"]}
    assert per_naam["Actueel"]["jaarstatus"] == "actueel"
    assert per_naam["Ouder"]["jaarstatus"] == "verouderd"
    assert per_naam["Zonder jaartal"]["jaarstatus"] == "verouderd"
    assert per_naam["Niets gevonden"]["jaarstatus"] == "ontbreekt"
    assert per_naam["Actueel"]["doeljaar"] == 2025


def test_verslag_nieuwer_dan_het_doeljaar_is_niet_verouderd(client, db_session):
    """DSV kwam op verslagjaar 2026 uit doordat `_documentjaar` de
    publicatiedatum uit de URL las (`/filings/3363/2026/RNS/..._2026-02-04_`).
    Zo'n bron in de bak "verouderd" zetten is aantoonbaar onjuist; hij blijft
    wel als los jaar zichtbaar in de verdeling."""
    _watchlist_met_verslagjaren(client, db_session, "toekomstjaar", 2026, {
        "Te nieuw gelezen": ("https://x.test/filings/2026/rns_2026-02-04", 2026),
    })

    data = client.get("/monitoring").json()

    assert data["actueel"] == 1
    assert data["verouderd"] == 0
    assert data["jaren_verdeling"] == [{"verslagjaar": 2026, "aantal": 1}]


def test_nieuwe_bevinding_bepaalt_de_jaarstatus_niet(client, db_session):
    """Een vondst die veranderde sinds de vorige ronde kan best een oud
    verslag zijn: op de watchlist van 10-08-2026 waren de enige twee
    organisaties met deze markering allebei van verslagjaar 2023. De markering
    blijft in de payload staan, maar mag de indeling niet sturen."""
    _, companies = _watchlist_met_verslagjaren(
        client, db_session, "delta-vs-jaar", 2026,
        {"Oude vondst": ("https://x.test/jaarverslag-2023.pdf", 2023)},
    )
    company = companies["Oude vondst"]
    db_session.add(PipelineRun(
        batch_id=company.batch_id, company_id=company.id,
        stap="jaarverslag_monitoring", status="new", duur_ms=100,
    ))
    db_session.commit()

    data = client.get("/monitoring").json()
    vondst = {c["naam"]: c for c in data["companies"]}["Oude vondst"]

    assert vondst["nieuwe_bevinding"] is True
    assert vondst["jaarstatus"] == "verouderd"
    assert data["actueel"] == 0
    assert data["verouderd"] == 1


def test_monitoring_run_slaat_organisaties_met_het_doeljaar_over(
    client, db_session, monkeypatch,
):
    """Wat binnen is hoeft niet opnieuw gezocht te worden.

    Een verslag over jaar X verschijnt in X+1, dus zodra het verslag over het
    doeljaar er is kan een volgende ronde niets nieuwers vinden. Op de
    watchlist van 10-08-2026 gold dat voor 51 van de 205 organisaties.

    Overslaan mag alleen als de reviewer die bron ook kan beoordelen; vandaar de
    bronkaart bij "Actueel".
    """
    _, companies = _watchlist_met_verslagjaren(
        client, db_session, "skip-actueel", 2026, {
            "Actueel": ("https://x.test/jaarverslag-2025.pdf", 2025),
            "Ouder": ("https://x.test/jaarverslag-2023.pdf", 2023),
            "Niets": ("", None),
        },
        met_bronkaart={"Actueel"},
    )
    gestart = []
    monkeypatch.setattr(
        monitoring_router, "run_monitoring_watchlist_background",
        lambda limit=None, offset=0, hercontroleer_actuele=False: gestart.append(
            (limit, offset, hercontroleer_actuele),
        ),
    )

    data = client.post("/monitoring/run").json()

    assert data["overgeslagen_actueel"] == 1
    assert data["aantal_companies"] == 2
    assert gestart == [(None, 0, False)]


def test_actueel_verslag_zonder_bronkaart_wordt_niet_overgeslagen(
    client, db_session, monkeypatch,
):
    """De skip mag de bronkaart-achterstand niet bevriezen.

    Gemeten op de watchlist van 17-08-2026: 66 van de 205 organisaties hebben
    een bekende bron-URL en 0 bronkandidaten, een deel daarvan met het verslag
    over het doeljaar. Alleen op verslagjaar filteren zou juist die organisaties
    voorgoed uitsluiten, want hun URL verandert niet meer.
    """
    _watchlist_met_verslagjaren(
        client, db_session, "skip-zonder-bronkaart", 2026, {
            "Met kaart": ("https://x.test/jaarverslag-2025.pdf", 2025),
            "Zonder kaart": ("https://y.test/jaarverslag-2025.pdf", 2025),
        },
        met_bronkaart={"Met kaart"},
    )
    monkeypatch.setattr(
        monitoring_router, "run_monitoring_watchlist_background",
        lambda limit=None, offset=0, hercontroleer_actuele=False: None,
    )

    data = client.post("/monitoring/run").json()

    assert data["overgeslagen_actueel"] == 1
    assert data["aantal_companies"] == 1


def test_monitoring_run_kan_actuele_organisaties_alsnog_hercontroleren(
    client, db_session, monkeypatch,
):
    _watchlist_met_verslagjaren(
        client, db_session, "hercontrole", 2026, {
            "Actueel": ("https://x.test/jaarverslag-2025.pdf", 2025),
        },
        met_bronkaart={"Actueel"},
    )
    gestart = []
    monkeypatch.setattr(
        monitoring_router, "run_monitoring_watchlist_background",
        lambda limit=None, offset=0, hercontroleer_actuele=False: gestart.append(
            (limit, offset, hercontroleer_actuele),
        ),
    )

    data = client.post("/monitoring/run?hercontroleer_actuele=true").json()

    assert data["overgeslagen_actueel"] == 0
    assert data["aantal_companies"] == 1
    assert gestart == [(None, 0, True)]


def test_monitoring_geeft_de_hele_bronkandidaat_mee(client, db_session):
    """De monitoring las het WP-getal al uit; het stond alleen niet in de respons.

    Daardoor toonde de vondstkaart alleen een link, terwijl het cijfer, het
    citaat en de scope allemaal al op de BronKandidaat stonden die dezelfde
    ronde had aangemaakt.
    """
    _zorg_voor_test_user(db_session)
    upload = client.post(
        "/batches/upload?naam=watchlist-bron&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nZorggroep Voorbeeld\n"), "text/csv")},
    )
    batch_id = upload.json()["batch_id"]
    company = db_session.query(Company).filter_by(batch_id=batch_id).one()

    url = "https://voorbeeld.test/jaarverslag-2025.pdf"
    db_session.add(JaarverslagMonitoring(
        company_id=company.id, laatste_bron_url=url, laatste_verslagjaar=2025,
        laatst_gecontroleerd_op=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    run = ResearchRun(
        company_id=company.id, batch_id=batch_id, doel="monitoring",
        status="completed",
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(BronKandidaat(
        research_run_id=run.id, company_id=company.id,
        url=url, canonical_url=url,
        brontype="jaarverslag", documenttype="jaarverslag",
        verslagjaar=2025, wp_gevonden=412, eenheid="werkzame_personen",
        bewijsfragment="412 medewerkers in dienst", bron_pagina=14,
        scope_class="vestiging", identity_class="exact_entity",
        status="voorgesteld",
    ))
    db_session.commit()

    vondst = client.get("/monitoring").json()["companies"][0]

    assert vondst["bron"]["wp_gevonden"] == 412
    assert vondst["bron"]["eenheid"] == "werkzame_personen"
    assert vondst["bron"]["bewijsfragment"] == "412 medewerkers in dienst"
    assert vondst["bron"]["scope_class"] == "vestiging"
    # De losse velden blijven bestaan: de bewijsviewer leidt daar zijn
    # #page= en search= uit af.
    assert vondst["bron_pagina"] == 14
