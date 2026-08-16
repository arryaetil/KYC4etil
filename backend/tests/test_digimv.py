import pytest

from app.research.digimv import zoek_digimv_documenten
from app.research.query_planner import QueryContext


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return [{
            "name": "Stichting Voorbeeldzorg",
            "town": "Heerlen",
            "externalOrganizationId": "12345678",
            "documents": [
                {"id": 11, "type": "Bestuursverslag", "fileName": "Verslag 2025.pdf"},
                # Hetzelfde bestand onder twee documenttypen maar één keer lezen.
                {"id": 12, "type": "Jaarrekening", "fileName": "Verslag 2025.pdf"},
                {"id": 13, "type": "Verslag interne toezichthouder", "fileName": "RvT.pdf"},
            ],
        }]


class _Client:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        return _Response()


@pytest.mark.asyncio
async def test_digimv_zoekt_direct_en_dedupliceert_bestanden(monkeypatch):
    monkeypatch.setattr("app.research.digimv.httpx.AsyncClient", _Client)

    resultaten = await zoek_digimv_documenten(QueryContext(
        naam="Stichting Voorbeeldzorg", gemeente="Heerlen",
        gevraagd_jaar=2025, kvk_nummer="12345678",
    ))

    assert len(resultaten) == 2
    assert resultaten[0].providers == ["digimv_direct"]
    assert "documentId=11" in resultaten[0].url
    # Peiljaar 2025 → boekjaar 2024: de jaarverantwoording over 2025 bestaat
    # pas na 31 mei 2026. Op het peiljaar zelf antwoordt DigiMV met HTTP 500.
    assert "year=2024" in resultaten[0].url


@pytest.mark.asyncio
async def test_digimv_weigert_ambigue_naam_zonder_exacte_identiteit(monkeypatch):
    class AmbigueResponse(_Response):
        def json(self):
            row = super().json()[0]
            return [row, {**row, "externalOrganizationId": "87654321"}]

    class AmbigueClient(_Client):
        async def get(self, *args, **kwargs):
            return AmbigueResponse()

    monkeypatch.setattr("app.research.digimv.httpx.AsyncClient", AmbigueClient)
    resultaten = await zoek_digimv_documenten(QueryContext(
        naam="Stichting Voorbeeldzorg", gevraagd_jaar=2025,
    ))
    assert resultaten == []


@pytest.mark.asyncio
async def test_digimv_vraagt_nooit_het_peiljaar_zelf_op(monkeypatch):
    """Regressie: `year=gevraagd_jaar` gaf altijd HTTP 500.

    `gevraagd_jaar` is `batch.jaar` (2026) en DigiMV archiveert per boekjaar.
    Daardoor faalde elke aanroep stil: 16 inzetten in productie, 0 bronnen.
    """
    bevraagde_jaren: list[str] = []

    class _JaarClient(_Client):
        async def get(self, *args, **kwargs):
            bevraagde_jaren.append(kwargs["params"]["year"])
            return _Response()

    monkeypatch.setattr("app.research.digimv.httpx.AsyncClient", _JaarClient)
    await zoek_digimv_documenten(QueryContext(
        naam="Stichting Voorbeeldzorg", gemeente="Heerlen",
        gevraagd_jaar=2026, kvk_nummer="12345678",
    ))

    assert bevraagde_jaren, "er moet minstens één zoekopdracht uitgaan"
    assert "2026" not in bevraagde_jaren
    assert bevraagde_jaren[0] == "2025"


@pytest.mark.asyncio
async def test_digimv_valt_terug_op_zoeken_zonder_gemeente(monkeypatch):
    """De statutaire plaats in DigiMV wijkt vaak af van de vestigingsgemeente.

    "Stichting Pergamijn" met town=Echt-Susteren gaf nul treffers; zonder
    gemeente één organisatie met vijf documenten.
    """
    plaatsen: list[str] = []

    class _PlaatsClient(_Client):
        async def get(self, *args, **kwargs):
            plaats = kwargs["params"]["town"]
            plaatsen.append(plaats)

            class _Leeg(_Response):
                def json(self):
                    # Alleen zonder gemeentefilter komt de organisatie boven.
                    return [] if plaats else _Response().json()

            return _Leeg()

    monkeypatch.setattr("app.research.digimv.httpx.AsyncClient", _PlaatsClient)
    resultaten = await zoek_digimv_documenten(QueryContext(
        naam="Stichting Voorbeeldzorg", gemeente="Echt-Susteren",
        gevraagd_jaar=2026, kvk_nummer="12345678",
    ))

    assert plaatsen[0] == "Echt-Susteren", "eerst scherp zoeken"
    assert "" in plaatsen, "daarna terugvallen zonder gemeente"
    assert len(resultaten) == 2


@pytest.mark.asyncio
async def test_digimv_herkent_naam_ondanks_rechtsvorm(monkeypatch):
    """Ons register kent "Mondriaan", het DigiMV-tableau "Stichting Mondriaan"."""
    class _StichtingResponse(_Response):
        def json(self):
            return [{**super().json()[0], "name": "Stichting Voorbeeldzorg"}]

    class _StichtingClient(_Client):
        async def get(self, *args, **kwargs):
            return _StichtingResponse()

    monkeypatch.setattr("app.research.digimv.httpx.AsyncClient", _StichtingClient)
    resultaten = await zoek_digimv_documenten(QueryContext(
        naam="Voorbeeldzorg", gemeente="Heerlen", gevraagd_jaar=2026,
    ))
    assert len(resultaten) == 2


@pytest.mark.asyncio
async def test_digimv_laat_een_falend_jaar_de_route_niet_slopen(monkeypatch):
    """Een HTTP-fout op één boekjaar mag geen exception naar de supervisor gooien."""
    class _StukClient(_Client):
        async def get(self, *args, **kwargs):
            raise RuntimeError("HTTP 500")

    monkeypatch.setattr("app.research.digimv.httpx.AsyncClient", _StukClient)
    assert await zoek_digimv_documenten(QueryContext(
        naam="Stichting Voorbeeldzorg", gevraagd_jaar=2026,
    )) == []
