"""Seed-documentverzameling: parallellisatie + jaarverslag-dedup."""
import asyncio

import pytest

from app.research.query_planner import QueryContext
from app.research.seeds import verzamel_seed_documenten
from app.research.validation import SourceDocument


def _document(**overrides) -> SourceDocument:
    basis = dict(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
        titel="Jaarverslag 2025",
        brontype="jaarverslag",
        documenttype="jaarverslag",
        gevraagd_jaar=2025,
        verslagjaar=2025,
        wp_gevonden=47,
        eenheid="werkzame_personen",
        bewijsfragment="47 medewerkers.",
    )
    basis.update(overrides)
    return SourceDocument(**basis)


class TragereTraceerTools:
    """Registreert de volgorde/timing van aanroepen zodat parallellisatie
    aantoonbaar is, zonder een echte netwerkvertraging nodig te hebben."""

    def __init__(
        self,
        website_document=None,
        nieuwste_document=None,
        jaarverslag_document=None,
    ):
        self._website_document = website_document
        self._nieuwste_document = nieuwste_document
        self._jaarverslag_document = jaarverslag_document
        self.aangeroepen: list[str] = []
        self.jaarverslag_aangeroepen = False

    async def find_officiele_website(self, context):
        self.aangeroepen.append("website")
        await asyncio.sleep(0.05)
        return self._website_document

    async def find_nieuwste_officiele_document(self, context):
        self.aangeroepen.append("nieuwste_document")
        await asyncio.sleep(0.05)
        return self._nieuwste_document

    async def find_jaarverslag(self, context):
        self.jaarverslag_aangeroepen = True
        return self._jaarverslag_document


@pytest.mark.asyncio
async def test_website_en_nieuwste_document_lopen_parallel():
    tools = TragereTraceerTools(
        website_document=_document(
            url="https://voorbeeldzorg.nl", brontype="officiele_website",
            verslagjaar=None, wp_gevonden=None,
        ),
        nieuwste_document=_document(),
    )
    context = QueryContext(
        naam="Voorbeeld Zorg", gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
    )

    loop = asyncio.get_event_loop()
    start = loop.time()
    await verzamel_seed_documenten(tools, context)
    duur = loop.time() - start

    # Sequentieel zou dit >= 0.10s duren (2x 0.05s); parallel < 0.09s.
    assert duur < 0.09


@pytest.mark.asyncio
async def test_jaarverslag_agent_wordt_overgeslagen_bij_exacte_match_met_wp():
    tools = TragereTraceerTools(
        nieuwste_document=_document(verslagjaar=2025, wp_gevonden=47),
    )
    context = QueryContext(
        naam="Voorbeeld Zorg", gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
    )

    documenten = await verzamel_seed_documenten(tools, context)

    assert tools.jaarverslag_aangeroepen is False
    assert len(documenten) == 1
    assert documenten[0].wp_gevonden == 47


@pytest.mark.asyncio
async def test_jaarverslag_agent_draait_alsnog_zonder_wp_gevonden():
    tools = TragereTraceerTools(
        nieuwste_document=_document(verslagjaar=2025, wp_gevonden=None),
        jaarverslag_document=_document(url="https://voorbeeldzorg.nl/anders.pdf"),
    )
    context = QueryContext(
        naam="Voorbeeld Zorg", gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
    )

    documenten = await verzamel_seed_documenten(tools, context)

    assert tools.jaarverslag_aangeroepen is True
    assert len(documenten) == 2


@pytest.mark.asyncio
async def test_jaarverslag_agent_draait_alsnog_bij_fte_cijfer():
    """FTE ≠ WP: een gevonden FTE-getal mag de jaarverslag-agent niet
    onderdrukken, ook al kloppen verslagjaar en wp_gevonden verder."""
    tools = TragereTraceerTools(
        nieuwste_document=_document(
            verslagjaar=2025, wp_gevonden=47, eenheid="fte",
        ),
        jaarverslag_document=_document(url="https://voorbeeldzorg.nl/anders.pdf"),
    )
    context = QueryContext(
        naam="Voorbeeld Zorg", gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
    )

    documenten = await verzamel_seed_documenten(tools, context)

    assert tools.jaarverslag_aangeroepen is True
    assert len(documenten) == 2


@pytest.mark.asyncio
async def test_jaarverslag_agent_draait_alsnog_bij_afwijkend_jaar():
    tools = TragereTraceerTools(
        nieuwste_document=_document(verslagjaar=2024, wp_gevonden=47),
        jaarverslag_document=_document(url="https://voorbeeldzorg.nl/2025.pdf"),
    )
    context = QueryContext(
        naam="Voorbeeld Zorg", gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
    )

    documenten = await verzamel_seed_documenten(tools, context)

    assert tools.jaarverslag_aangeroepen is True
    assert len(documenten) == 2


@pytest.mark.asyncio
async def test_uitzonderingen_per_stap_worden_genegeerd():
    class FoutieveTools(TragereTraceerTools):
        async def find_officiele_website(self, context):
            raise RuntimeError("netwerkfout")

    tools = FoutieveTools(
        nieuwste_document=_document(verslagjaar=2025, wp_gevonden=47),
    )
    context = QueryContext(
        naam="Voorbeeld Zorg", gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
    )

    documenten = await verzamel_seed_documenten(tools, context)

    assert len(documenten) == 1


@pytest.mark.asyncio
async def test_duo_wordt_alleen_als_directe_seed_op_de_duo_route_opgehaald(
    monkeypatch,
):
    duo_bron = _document(
        url="https://duo.nl/personeel-vo.xlsx",
        brontype="overheid",
        documenttype="duo_personeel_personen",
        eenheid="onderwijspersoneel_personen",
        research_route="duo",
    )

    async def fake_duo(context):
        return duo_bron

    monkeypatch.setattr(
        "app.research.seeds.vind_duo_personeelsbron", fake_duo,
    )
    documenten = await verzamel_seed_documenten(
        TragereTraceerTools(),
        QueryContext(naam="Voorbeeldschool", sbi_code="85311"),
        {"website", "duo", "media"},
    )

    assert documenten == [duo_bron]
