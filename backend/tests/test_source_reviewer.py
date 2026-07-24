from unittest.mock import AsyncMock

import pytest

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
        "beslissing": "tonen_aan_reviewer",
        "identity_class": "exact_entity",
        "scope_class": "vestiging",
        "gevonden_organisatie": "Hallux Podotherapie",
        "reden": "De pagina noemt naam, plaats en het behandelteam.",
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
    reviewer._llm_review.assert_awaited_once()
