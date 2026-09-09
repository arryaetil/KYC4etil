from unittest.mock import AsyncMock

import pytest

import app.research.source_reviewer as source_reviewer
from app.research.query_planner import QueryContext
from app.research.source_reviewer import IntelligentSourceReviewer
from app.research.validation import SourceDocument


def _context(naam: str, gemeente: str = "Heerlen") -> QueryContext:
    return QueryContext(naam=naam, gemeente=gemeente, gevraagd_jaar=2025)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("naam", "titel", "url", "bewijs"),
    [
        (
            "Mondriaan",
            "Financieel jaarverslag 2024–2025 - Rotterdam",
            "https://iffr.com/annual-report-2025.pdf",
            "In boekjaar 2024–2025 waren er 36 medewerkers.",
        ),
        (
            "Stichting Pergamijn",
            "JAARVERANTWOORDING 2022",
            "https://zorgboog.nl/jaarverantwoording-2023.pdf",
            "Onze 2.400 medewerkers ondersteunen cliënten.",
        ),
        (
            "DSM-Firmenich",
            "Annual report",
            "https://brenntag.com/annual-report-2025.pdf",
            "With its workforce of over 17,300 employees.",
        ),
    ],
)
async def test_live_mismatches_worden_fail_closed_afgewezen(
    naam, titel, url, bewijs,
):
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock(return_value={
        "beslissing": "afwijzen",
        "identity_class": "mismatch",
        "scope_class": "unknown",
        "gevonden_organisatie": titel,
        "reden": "De bron gaat over een andere organisatie.",
    })
    document = SourceDocument(
        naam=naam,
        company_website_url=None,
        url=url,
        titel=titel,
        tekst="",
        bewijsfragment=bewijs,
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        wp_gevonden=100,
        eenheid="werkzame_personen",
    )

    reviewed = await reviewer.review(_context(naam), document)

    assert reviewed.is_afgewezen is True
    assert reviewed.identity_class == "mismatch"
    assert (
        "verkeerde organisatie" in reviewed.afwijsredenen
        or "intelligente_review_afgewezen" in reviewed.afwijsredenen
    )


@pytest.mark.asyncio
async def test_persoonlijk_linkedinprofiel_wordt_zonder_llm_afgewezen():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    document = SourceDocument(
        naam="Okechamp B.V.",
        company_website_url=None,
        url="https://nl.linkedin.com/in/een-medewerker",
        titel="Coördinator Warehousing Okéchamp",
        tekst="Werkzaam bij Okéchamp",
        brontype="website",
    )

    reviewed = await reviewer.review(_context("Okechamp B.V."), document)

    assert reviewed.is_afgewezen is True
    assert "sociaal_profiel_geen_primaire_wp_bron" in reviewed.afwijsredenen
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_llm_goedgekeurde_onafhankelijke_media_mag_naar_ranking():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock(return_value={
        "beslissing": "tonen_aan_reviewer",
        "identity_class": "exact_entity",
        "scope_class": "limburg",
        "gevonden_organisatie": "Zuyderland Medisch en Zorgconcern",
        "reden": "Naam en werkgeverscijfer staan expliciet in het artikel.",
    })
    document = SourceDocument(
        naam="Zuyderland Medisch en Zorgconcern",
        company_website_url=None,
        url="https://l1nieuws.nl/zuyderland",
        titel="Vestigingsklimaat in Limburg",
        tekst="Zuyderland is met bijna 11.000 banen de grootste werkgever.",
        bewijsfragment="De grootste werkgever blijft Zuyderland.",
        brontype="media",
        wp_gevonden=11000,
        eenheid="werkzame_personen",
    )

    reviewed = await reviewer.review(
        _context("Zuyderland Medisch en Zorgconcern", "Sittard-Geleen"),
        document,
    )

    assert reviewed.is_afgewezen is False
    assert reviewed.identity_class == "exact_entity"
    assert reviewed.document.scope_class == "limburg"
    assert reviewed.validaties["intelligente_review"]["beslissing"] == (
        "tonen_aan_reviewer"
    )


@pytest.mark.asyncio
async def test_correcte_externe_pdf_wordt_niet_door_woordmatch_geblokkeerd():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock(return_value={
        "beslissing": "tonen_aan_reviewer",
        "identity_class": "exact_entity",
        "scope_class": "limburg",
        "gevonden_organisatie": "Stichting Pergamijn",
        "reden": "Titel en documentmetadata identificeren Stichting Pergamijn.",
    })
    document = SourceDocument(
        naam="Stichting Pergamijn",
        company_website_url=None,
        url="https://publicaties.example/pergamijn-jaarverslag-2025.pdf",
        titel="Jaarverslag 2025",
        tekst="",
        bewijsfragment="In totaal waren 1.250 medewerkers in dienst.",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        wp_gevonden=1250,
        eenheid="werkzame_personen",
    )

    reviewed = await reviewer.review(_context("Stichting Pergamijn"), document)

    assert reviewed.is_afgewezen is False
    assert reviewed.identity_class == "exact_entity"
    reviewer._llm_review.assert_awaited_once()


@pytest.mark.asyncio
async def test_kleine_organisatiepagina_zonder_wp_mag_semantisch_beoordeeld():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock(return_value={
        "beslissing": "context_only",
        "identity_class": "exact_entity",
        "scope_class": "vestiging",
        "gevonden_organisatie": "Hallux Podotherapie",
        "reden": "Juiste organisatiepagina, maar zonder expliciet WP-cijfer.",
    })
    document = SourceDocument(
        naam="Hallux Podotherapie",
        company_website_url=None,
        url="https://halluxpodotherapie.nl/ons-team",
        titel="Ons team",
        tekst="Hallux Podotherapie in Roermond stelt het behandelteam voor.",
        brontype="website",
        documenttype="teampagina",
    )

    reviewed = await reviewer.review(
        _context("Hallux Podotherapie", "Roermond"),
        document,
    )

    assert reviewed.is_afgewezen is False
    assert "geen_concreet_wp_bewijs" in reviewed.waarschuwingen
    assert "alleen_context_geen_wp_voorstel" in reviewed.waarschuwingen
    assert (
        reviewed.validaties["intelligente_review"]["beslissing"]
        == "context_only"
    )
    reviewer._llm_review.assert_awaited_once()


@pytest.mark.asyncio
async def test_correcte_bron_vorig_jaar_blijft_als_context_beschikbaar():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock(return_value={
        "beslissing": "tonen_aan_reviewer",
        "identity_class": "exact_entity",
        "scope_class": "limburg",
        "gevonden_organisatie": "Mondriaan",
        "reden": "Juiste organisatie, maar het verslag gaat over 2024.",
    })
    document = SourceDocument(
        naam="Mondriaan",
        company_website_url=None,
        url="https://mondriaan.eu/jaarverslag-2024.pdf",
        titel="Jaarverslag Mondriaan 2024",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2024,
        wp_gevonden=2500,
        eenheid="werkzame_personen",
        bewijsfragment="In 2024 werkten gemiddeld 2.500 medewerkers bij Mondriaan.",
    )

    reviewed = await reviewer.review(_context("Mondriaan"), document)

    assert reviewed.is_afgewezen is False
    assert "afwijkend_verslagjaar" in reviewed.waarschuwingen
    assert (
        reviewed.validaties["intelligente_review"]["beslissing"]
        == "context_only"
    )


@pytest.mark.asyncio
async def test_officieel_groepsdocument_is_niet_automatisch_exacte_vestiging(
    monkeypatch,
):
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    # De scope wordt op het eigen domein apart geclassificeerd; die call werd
    # hier nooit vervangen en ging dus echt het netwerk op. Wat deze test
    # vastlegt is de bedrading: de tak neemt `document.scope_class` niet blind
    # over (dat wás de regressie) maar vraagt het na, en gebruikt het antwoord.
    scope_call = AsyncMock(return_value="concern")
    monkeypatch.setattr(
        "app.research.source_reviewer._llm_classify_scope", scope_call,
    )
    document = SourceDocument(
        naam="Zorglocatie Binnenhof",
        company_website_url="https://zorggroep.example/locaties/binnenhof",
        url="https://zorggroep.example/jaarverslag-2025.pdf",
        titel="Jaarverslag Zorggroep",
        tekst="De zorggroep heeft 4.900 medewerkers.",
        bewijsfragment="De zorggroep heeft 4.900 medewerkers.",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        wp_gevonden=4900,
        eenheid="werkzame_personen",
    )

    reviewed = await reviewer.review(_context("Zorglocatie Binnenhof"), document)

    assert reviewed.is_afgewezen is False
    assert reviewed.identity_class == "same_brand_or_group"
    # 4.900 is het groepstotaal en niet het aantal van déze locatie. Het
    # onderscheid doet er ook echt toe: kandidaten met scope "concern" zaten in
    # de productiedata 9% van de tijd binnen 10% van de waarheid, tegen 65%
    # voor scope "limburg".
    scope_call.assert_awaited_once()
    assert reviewed.document.scope_class == "concern"
    assert reviewed.validaties["intelligente_review"]["beslissing"] == "context_only"
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_exacte_bekende_locatiepagina_blijft_exacte_entiteit():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    document = SourceDocument(
        naam="Zorglocatie Binnenhof",
        company_website_url="https://zorggroep.example/locaties/binnenhof/",
        url="https://www.zorggroep.example/locaties/binnenhof",
        titel="Zorglocatie Binnenhof",
        tekst="Welkom bij Zorglocatie Binnenhof.",
        brontype="officiele_website",
        documenttype="organisatiepagina",
    )

    reviewed = await reviewer.review(_context("Zorglocatie Binnenhof"), document)

    assert reviewed.identity_class == "exact_entity"
    assert reviewed.validaties["intelligente_review"]["beslissing"] == "context_only"
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_vestigingspagina_op_eigen_domein_wordt_daadwerkelijk_geclassificeerd(
    monkeypatch,
):
    """
    Regressie: Hallux Podotherapie Roermond. De juiste vestigingspagina werd
    gevonden, maar scope_class bleef "unknown" omdat deze tak nooit zelf
    classificeerde — het nam alleen (het bijna nooit gevulde) document.scope_class
    over. Zonder een als "vestiging" herkende kandidaat kan
    behoud_vestigingsanker (research/ranking.py) niets beschermen.
    """
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    aangeroepen_met = {}

    async def fake_classify_scope(naam, adres, gemeente, context):
        aangeroepen_met.update(naam=naam, gemeente=gemeente, context=context)
        return "vestiging"

    monkeypatch.setattr(
        source_reviewer, "_llm_classify_scope", fake_classify_scope,
    )
    document = SourceDocument(
        naam="Hallux Podotherapie",
        company_website_url="https://hallux.nl",
        url="https://hallux.nl/vestigingen/limburg/roermond/podotherapie-roermond-bredeweg/",
        titel="Podotherapie Roermond Bredeweg",
        tekst="In Roermond werken vier podotherapeuten voor u klaar.",
        brontype="officiele_website",
        documenttype="teampagina",
        wp_gevonden=4,
        eenheid="werkzame_personen",
        bewijsfragment="In Roermond werken vier podotherapeuten voor u klaar.",
    )

    reviewed = await reviewer.review(
        _context("Hallux Podotherapie", gemeente="Roermond"), document,
    )

    assert aangeroepen_met["context"] == (
        "In Roermond werken vier podotherapeuten voor u klaar."
    )
    assert reviewed.document.scope_class == "vestiging"
    assert reviewed.validaties["intelligente_review"]["beslissing"] == (
        "tonen_aan_reviewer"
    )


@pytest.mark.asyncio
async def test_eigen_domein_zonder_enige_context_slaat_scopeclassificatie_over(
    monkeypatch,
):
    """Een lege organisatiepagina heeft niets te classificeren — geen zinloze LLM-call."""
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    classify = AsyncMock()
    monkeypatch.setattr(source_reviewer, "_llm_classify_scope", classify)
    document = SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url="https://voorbeeldzorg.nl/contact",
        titel="Contact",
        tekst="",
        brontype="officiele_website",
    )

    reviewed = await reviewer.review(_context("Voorbeeld Zorg"), document)

    classify.assert_not_awaited()
    assert reviewed.validaties["intelligente_review"]["scope_class"] == "unknown"


@pytest.mark.asyncio
async def test_andere_locatie_op_zelfde_groepsdomein_wordt_afgewezen():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    document = SourceDocument(
        naam="Woonzorgcentrum Rozenhof",
        company_website_url=(
            "https://careyn.example/locaties/westland/careyn-rozenhof"
        ),
        url="https://careyn.example/locaties/wijkteam-breukelen-buiten",
        titel="Wijkteam Breukelen Buiten",
        tekst="Maak kennis met het wijkteam in Breukelen.",
        brontype="officiele_website",
        documenttype="teampagina",
    )

    reviewed = await reviewer.review(
        _context("Woonzorgcentrum Rozenhof"),
        document,
    )

    assert reviewed.is_afgewezen is True
    assert reviewed.identity_class == "mismatch"
    assert (
        "zelfde_domein_maar_geen_relevante_doelorganisatie"
        in reviewed.afwijsredenen
    )
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_algemene_productpagina_op_groepsdomein_wordt_afgewezen():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    document = SourceDocument(
        naam="Woonzorgcentrum Rozenhof",
        company_website_url=(
            "https://careyn.example/locaties/westland/careyn-rozenhof"
        ),
        url="https://careyn.example/ons-aanbod/volledig-pakket-thuis",
        titel="Volledig pakket thuis",
        tekst="Informatie over zorg aan huis.",
        brontype="officiele_website",
        documenttype="organisatiepagina",
    )

    reviewed = await reviewer.review(
        _context("Woonzorgcentrum Rozenhof"),
        document,
    )

    assert reviewed.is_afgewezen is True
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_relevant_locatienieuws_op_groepsdomein_blijft_context():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    document = SourceDocument(
        naam="Woonzorgcentrum Rozenhof",
        company_website_url=(
            "https://careyn.example/locaties/westland/careyn-rozenhof"
        ),
        url="https://careyn.example/nieuws/nieuwbouw-rozenhof",
        titel="Nieuwbouw Rozenhof weer een stap dichterbij",
        tekst="De nieuwbouw van Rozenhof is gestart.",
        brontype="officiele_website",
        documenttype="nieuwsartikel",
    )

    reviewed = await reviewer.review(
        _context("Woonzorgcentrum Rozenhof"),
        document,
    )

    assert reviewed.is_afgewezen is False
    assert reviewed.identity_class == "exact_entity"
    assert (
        reviewed.validaties["intelligente_review"]["beslissing"]
        == "context_only"
    )
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_vacaturepagina_zonder_wp_bewijs_wordt_afgewezen():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    document = SourceDocument(
        naam="Groene Kruis Kraamzorg",
        company_website_url="https://kraamzorg.example/",
        url="https://kraamzorg.example/vacature-medewerker-e-consult",
        titel="Vacature medewerker E-consult",
        tekst="Kom werken bij Groene Kruis Kraamzorg.",
        brontype="officiele_website",
        documenttype="organisatiepagina",
    )

    reviewed = await reviewer.review(
        _context("Groene Kruis Kraamzorg"),
        document,
    )

    assert reviewed.is_afgewezen is True
    assert "vacaturepagina_zonder_wp_bewijs" in reviewed.afwijsredenen
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_locatienaam_alleen_in_sitefooter_maakt_nieuws_niet_exact():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    document = SourceDocument(
        naam="Rooyhof",
        company_website_url=(
            "https://zorggroep.example/locaties/revalidatiecentrum-rooyhof"
        ),
        url="https://zorggroep.example/nieuws/samen-werken-aan-betere-zorg",
        titel="Samen werken aan betere zorg",
        tekst="Algemeen nieuws. Bekijk ook onze locaties: Rooyhof.",
        brontype="officiele_website",
        documenttype="nieuwsartikel",
    )

    reviewed = await reviewer.review(_context("Rooyhof"), document)

    assert reviewed.is_afgewezen is True
    assert (
        "zelfde_domein_maar_geen_relevante_doelorganisatie"
        in reviewed.afwijsredenen
    )
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_andere_revalidatielocatie_is_geen_match_op_generiek_woord():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    document = SourceDocument(
        naam="Revalidatiecentrum Solidus",
        company_website_url=(
            "https://zorggroep.example/locaties/revalidatiecentrum-solidus"
        ),
        url=(
            "https://zorggroep.example/locaties/"
            "revalidatiecentrum-vita-nova"
        ),
        titel="Revalidatiecentrum Vita Nova",
        tekst="Informatie over Vita Nova.",
        brontype="officiele_website",
        documenttype="organisatiepagina",
    )

    reviewed = await reviewer.review(
        _context("Revalidatiecentrum Solidus"),
        document,
    )

    assert reviewed.is_afgewezen is True
    assert (
        "zelfde_domein_maar_geen_relevante_doelorganisatie"
        in reviewed.afwijsredenen
    )
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_groepshomepage_is_geen_exacte_vestiging_zonder_naamsbewijs():
    reviewer = IntelligentSourceReviewer()
    reviewer._llm_review = AsyncMock()
    document = SourceDocument(
        naam="Woonzorgcentrum Amaliahof",
        company_website_url="https://zorggroep.example/",
        url="https://www.zorggroep.example/",
        titel="De Zorggroep",
        tekst="Welkom bij onze zorgorganisatie.",
        brontype="officiele_website",
        documenttype="organisatiepagina",
    )

    reviewed = await reviewer.review(
        _context("Woonzorgcentrum Amaliahof"),
        document,
    )

    assert reviewed.is_afgewezen is False
    assert reviewed.identity_class == "same_brand_or_group"
    assert (
        reviewed.validaties["intelligente_review"]["beslissing"]
        == "context_only"
    )
    reviewer._llm_review.assert_not_awaited()


@pytest.mark.asyncio
async def test_bronreview_draait_op_temperatuur_nul(monkeypatch):
    """De bronreview bepaalt identity_class, scope_class en de afwijzingen.

    Op OpenAI's default-temperatuur (1.0) kreeg dezelfde URL tussen twee runs
    een ander oordeel: gemeten op productiedata wisselde scope_class bij 77%
    van de opnieuw beoordeelde URL's. De call moet daarom via
    llm._create_response lopen, die openai_temperature (0.0) afdwingt.
    """
    import openai

    doorgegeven: dict = {}

    class _Response:
        output_text = '{"identity_class": "exact_entity", "scope_class": "limburg"}'
        usage = None

    class _Responses:
        async def create(self, **kwargs):
            doorgegeven.update(kwargs)
            return _Response()

    class _FakeClient:
        # Onderschept één laag lager dan _create_response, zodat de echte
        # wrapper draait en zijn temperature-default aantoonbaar toepast.
        def __init__(self, *args, **kwargs):
            self.responses = _Responses()

    monkeypatch.setattr(openai, "AsyncOpenAI", _FakeClient)
    settings = source_reviewer.get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "test-key", raising=False)

    reviewer = IntelligentSourceReviewer()
    document = SourceDocument(
        naam="Mondriaan",
        company_website_url="https://www.mondriaan.eu/",
        url="https://www.mondriaan.eu/jaarverslag-2025.pdf",
        titel="Jaarverantwoording 2025",
        brontype="jaarverslag",
        tekst="Er waren 2294 medewerkers actief.",
    )
    await reviewer._llm_review(_context("Mondriaan"), document)

    assert doorgegeven, "_llm_review moet via llm._create_response lopen"
    assert doorgegeven.get("temperature", 1.0) == 0.0


def test_geen_enkele_openai_call_omzeilt_de_wrapper():
    """Structurele bewaking tegen drift.

    llm._create_response zet de temperatuur en telt het tokenverbruik. Een
    nieuwe call-site die rechtstreeks client.responses.create aanroept, mist
    allebei — stil, zonder foutmelding. Dat is precies hoe de bronreview
    maandenlang op temperatuur 1.0 draaide.
    """
    from pathlib import Path

    app_dir = Path(__file__).resolve().parent.parent / "app"
    overtreders = []
    for pad in app_dir.rglob("*.py"):
        # llm.py bevat de wrapper zelf en mag als enige direct aanroepen.
        if pad.name == "llm.py" and pad.parent.name == "providers":
            continue
        for nummer, regel in enumerate(
            pad.read_text(encoding="utf-8").splitlines(), start=1,
        ):
            if "responses.create(" in regel and "_create_response" not in regel:
                overtreders.append(f"{pad.relative_to(app_dir)}:{nummer}")
    assert not overtreders, (
        "Deze call-sites omzeilen llm._create_response en draaien dus op "
        f"temperatuur 1.0 zonder tokentelling: {overtreders}"
    )
