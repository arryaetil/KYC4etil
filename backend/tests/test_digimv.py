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
    assert "year=2025" in resultaten[0].url


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
