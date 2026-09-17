"""Een bron die de reviewer aandraagt wordt gelezen, niet alleen opgeschreven.

Twee ingangen, hetzelfde principe: een URL toevoegen bij een vestiging, en een
jaarverslag uploaden bij de monitoring. Allebei leverden voorheen een kaart op
zonder WP-getal, zonder citaat en zonder paginanummer — een bewijsstuk dat
niets bewijst.
"""
from io import BytesIO

import fitz
import pytest

from app import documenten
from app.config import get_settings
from app.models import Batch, BronKandidaat, Company, JaarverslagMonitoring, User
from app.research.validation import SourceDocument


@pytest.fixture
def opslag(tmp_path, monkeypatch):
    monkeypatch.setattr(
        get_settings(), "brondocumenten_pad", str(tmp_path / "brondocumenten"),
    )
    return tmp_path


@pytest.fixture
def vestiging(db_session):
    if db_session.get(User, "test-user-id") is None:
        db_session.add(User(id="test-user-id", naam="Test", email="t@etil.nl",
                            rol="admin", password_hash=""))
    batch = Batch(id="batch-1", naam="Lijst", jaar=2026, totaal=1)
    company = Company(id="company-1", batch_id=batch.id, naam="Koraal Groep",
                      gemeente="Sittard")
    db_session.add_all([batch, company])
    db_session.commit()
    return company


def _uitgelezen_document(url: str) -> SourceDocument:
    return SourceDocument(
        naam="Koraal Groep",
        company_website_url="https://koraal.nl",
        url=url,
        titel="Jaarverslag 2025",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        wp_gevonden=2400,
        eenheid="werkzame_personen",
        bewijsfragment="Koraal telt 2.400 medewerkers.",
        bron_pagina=12,
        scope_class="limburg",
        wp_extractie_gedaan=True,
    )


def test_toegevoegde_bron_wordt_uitgelezen(client, db_session, vestiging, monkeypatch):
    """De kern van de klacht: de knop legde alleen een URL vast.

    Wat er op de kaart hoort te staan — het aantal, het citaat, de pagina en een
    weging — komt uit dezelfde lezing die een gevonden bron krijgt.
    """
    async def nep_lees_bron(context, url, titel=None, route="document"):
        assert context.naam == "Koraal Groep"
        # Het peiljaar van de lijst, niet het lopende jaar: een verslag over
        # jaar X verschijnt pas in X+1.
        assert context.gevraagd_jaar == 2025
        return _uitgelezen_document(url)

    monkeypatch.setattr("app.routers.research.lees_bron", nep_lees_bron)

    response = client.post(
        "/research/companies/company-1/manual-source",
        json={"url": "https://koraal.nl/jaarverslag-2025.pdf"},
    )

    assert response.status_code == 201
    assert response.json()["melding"] is None
    bron = response.json()["bron"]
    assert bron["wp_gevonden"] == 2400
    assert bron["bewijsfragment"] == "Koraal telt 2.400 medewerkers."
    assert bron["bron_pagina"] == 12

    kandidaat = db_session.query(BronKandidaat).filter_by(
        company_id="company-1").one()
    # Het brontype blijft "handmatig": daar hangt aan op dat het bronnenpaneel
    # deze kaart altijd toont, los van welke run de laatste is.
    assert kandidaat.brontype == "handmatig"
    assert kandidaat.status == "geaccepteerd"
    assert kandidaat.ranking_score is not None
    assert kandidaat.validaties["aangedragen_door_reviewer"] is True


def test_bron_die_niet_te_lezen_is_blijft_wel_staan(client, db_session, vestiging, monkeypatch):
    """Een onbereikbare bron mag het toevoegen niet ongedaan maken.

    De reviewer heeft die bron bewust aangedragen. Verdwijnt hij bij een
    time-out of een 404, dan klikt iemand op toevoegen en gebeurt er zichtbaar
    niets.
    """
    async def geen_document(context, url, titel=None, route="document"):
        return None

    monkeypatch.setattr("app.routers.research.lees_bron", geen_document)

    response = client.post(
        "/research/companies/company-1/manual-source",
        json={"url": "https://koraal.nl/weg.pdf"},
    )

    assert response.status_code == 201
    assert "niet worden opgehaald" in response.json()["melding"]
    assert db_session.query(BronKandidaat).filter_by(
        company_id="company-1").count() == 1


def test_uitlezen_is_uit_te_zetten(client, db_session, vestiging, monkeypatch):
    """Alleen vastleggen dat deze bron is gebruikt, zonder hem op te halen."""
    async def nooit(context, url, titel=None, route="document"):
        raise AssertionError("er mocht niet gelezen worden")

    monkeypatch.setattr("app.routers.research.lees_bron", nooit)

    response = client.post(
        "/research/companies/company-1/manual-source",
        json={"url": "https://koraal.nl/jv.pdf", "uitlezen": False},
    )

    assert response.status_code == 201
    assert response.json()["bron"]["wp_gevonden"] is None


def test_aangedragen_bron_wordt_niet_weggegooid_op_verkeerd_jaar(monkeypatch):
    """Wat het zoeken afwijst, wordt hier een voorbehoud.

    `valideer_bron` wijst een afwijkend verslagjaar hard af en `rank_bronnen`
    slaat een afgewezen bron over. Voor het zoeken is dat juist; voor een bron
    die de reviewer zelf aandraagt betekent het dat er geen kaart komt.
    """
    from app.research.losse_bron import weeg_reviewersbron

    document = SourceDocument(
        naam="Koraal Groep",
        company_website_url="https://koraal.nl",
        url="https://koraal.nl/jaarverslag-2022.pdf",
        titel="Koraal Groep jaarverslag 2022",
        gevraagd_jaar=2025,
        verslagjaar=2022,
        brontype="jaarverslag",
        documenttype="jaarverslag",
        wp_gevonden=2200,
        eenheid="werkzame_personen",
        bewijsfragment="Koraal Groep telt 2.200 medewerkers.",
        wp_extractie_gedaan=True,
    )

    ranked = weeg_reviewersbron(document)

    assert ranked is not None
    # Dezelfde sleutel als de batchflow en de monitoring zetten, zodat de
    # reviewer één begrip ziet in plaats van twee.
    assert "afwijkend_verslagjaar" in ranked.waarschuwingen
    assert ranked.validaties["voorbehoud_bij_aangedragen_bron"] == [
        "verkeerd verslagjaar",
    ]


def test_naamheuristiek_op_een_bestandsnaam_zegt_niet_ander_bedrijf():
    """"Deze bron lijkt bij een ander bedrijf te horen" is hier geen vaststelling.

    Het oordeel komt van een naamvergelijking tussen titel en citaat. Bij een
    geüpload verslag is de titel de bestandsnaam en staat de naam vaak nergens
    in de geciteerde zin — dezelfde situatie als een DigiMV-archiefbestand dat
    `Jaardocument.pdf` heet. De koppeling komt van de reviewer, dus wordt het
    "mogelijk ander bedrijf" en niet "afwijkend".
    """
    from app.research.losse_bron import weeg_reviewersbron

    document = SourceDocument(
        naam="Koraal Groep",
        company_website_url=None,
        url="https://upload.kyc4etil.intern/company-1/abc.pdf",
        titel="Jaarverslag_2025.pdf",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        brontype="jaarverslag",
        documenttype="jaarverslag",
        wp_gevonden=2400,
        eenheid="werkzame_personen",
        bewijsfragment="telt 2400 medewerkers in dienst",
        wp_extractie_gedaan=True,
    )

    ranked = weeg_reviewersbron(document)

    assert ranked.identity_class == "possible_match"
    assert ranked.validaties["aangedragen_identificatie"]["heuristiek"] == "mismatch"


def _jaarverslag_pdf(tekst: str) -> bytes:
    doc = fitz.open()
    pagina = doc.new_page()
    pagina.insert_text((50, 100), tekst)
    return doc.tobytes()


def test_geupload_jaarverslag_wordt_een_bronkaart(client, db_session, vestiging, opslag):
    """Koraal Groep staat op "niet gevonden" terwijl de reviewer het verslag heeft.

    Zonder model draait de deterministische terugval; die vindt de expliciete
    headcountzin en levert daarmee hetzelfde soort kaart op als een gevonden
    verslag.
    """
    inhoud = _jaarverslag_pdf("Koraal telt 2400 medewerkers in dienst.")

    response = client.post(
        "/monitoring/companies/company-1/jaarverslag",
        files={"file": ("Jaarverslag_2025.pdf", BytesIO(inhoud), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    bron = response.json()["bron"]
    assert bron["wp_gevonden"] == 2400
    assert bron["verslagjaar"] == 2025
    assert bron["bron_pagina"] == 1
    # Het document wordt bewaard, want het bestaat nergens anders: zonder onze
    # kopie is er geen bewijs meer te tonen.
    assert documenten.lees(bron["url"]) == inhoud
    assert documenten.is_upload_url(bron["url"])
    # De bewijsviewer herkent een PDF aan de extensie.
    assert bron["url"].endswith(".pdf")

    status = db_session.query(JaarverslagMonitoring).filter_by(
        company_id="company-1").one()
    assert status.laatste_bron_url == bron["url"]
    assert status.laatste_verslagjaar == 2025


def test_geupload_jaarverslag_zonder_getal_meldt_dat(client, vestiging, opslag):
    inhoud = _jaarverslag_pdf("Over ons personeel valt weinig te zeggen.")

    response = client.post(
        "/monitoring/companies/company-1/jaarverslag",
        files={"file": ("verslag.pdf", BytesIO(inhoud), "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["bron"]["wp_gevonden"] is None
    assert "geen WP-getal" in response.json()["melding"]


def test_ouder_geupload_verslag_verdringt_een_nieuwere_baseline_niet(
    client, db_session, vestiging, opslag,
):
    """Een reviewer die 2023 aanlevert mag 2025 niet terugzetten."""
    db_session.add(JaarverslagMonitoring(
        company_id="company-1",
        laatste_bron_url="https://koraal.nl/jaarverslag-2025.pdf",
        laatste_verslagjaar=2025,
    ))
    db_session.commit()

    response = client.post(
        "/monitoring/companies/company-1/jaarverslag?",
        files={"file": ("Jaarverslag_2023.pdf",
                        BytesIO(_jaarverslag_pdf("Wij hebben 100 medewerkers in dienst.")),
                        "application/pdf")},
    )

    assert response.status_code == 201
    status = db_session.query(JaarverslagMonitoring).filter_by(
        company_id="company-1").one()
    assert status.laatste_verslagjaar == 2025
    assert status.laatste_bron_url == "https://koraal.nl/jaarverslag-2025.pdf"
    # De kaart komt er wél: het verslag is beoordeelbaar, ook al is het ouder.
    assert db_session.query(BronKandidaat).filter_by(
        company_id="company-1").count() == 1


def test_alleen_pdf(client, vestiging, opslag):
    response = client.post(
        "/monitoring/companies/company-1/jaarverslag",
        files={"file": ("verslag.docx", BytesIO(b"geen pdf"), "application/octet-stream")},
    )
    assert response.status_code == 422


def test_zonder_documentopslag_geen_halve_kaart(client, vestiging, monkeypatch):
    """Zonder volume is het bewijs bij de volgende deploy weg.

    Dan liever hier stoppen met de reden dan een kaart die naar een document
    verwijst dat nergens meer bestaat.
    """
    monkeypatch.setattr(get_settings(), "brondocumenten_pad", "")

    response = client.post(
        "/monitoring/companies/company-1/jaarverslag",
        files={"file": ("verslag.pdf",
                        BytesIO(_jaarverslag_pdf("Wij hebben 10 medewerkers in dienst.")),
                        "application/pdf")},
    )

    assert response.status_code == 503
