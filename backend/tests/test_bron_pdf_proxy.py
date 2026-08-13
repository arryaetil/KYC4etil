"""De bron-PDF-proxy mag uitsluitend bronnen ophalen die de agent zelf vond.

Zonder die begrenzing zou een ingelogde gebruiker de backend elk willekeurig
adres kunnen laten benaderen (server-side request forgery), inclusief interne
diensten die van buitenaf onbereikbaar zijn.
"""
from app.models import (
    Batch, BronKandidaat, Company, JaarverslagMonitoring, ResearchRun,
)


def _maak_kandidaat(db_session, url: str) -> BronKandidaat:
    batch = Batch(naam="proxy-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(
        batch_id=batch.id, naam="Voorbeeld Zorg", vestigingsnummer="PROXY-1",
    )
    db_session.add(company)
    db_session.flush()
    run = ResearchRun(
        company_id=company.id, batch_id=batch.id, doel="test", status="completed",
    )
    db_session.add(run)
    db_session.flush()
    kandidaat = BronKandidaat(
        research_run_id=run.id,
        company_id=company.id,
        url=url,
        canonical_url=url,
        brontype="jaarverslag",
        status="voorgesteld",
        rang=1,
    )
    db_session.add(kandidaat)
    db_session.commit()
    return kandidaat


def test_onbekende_url_wordt_geweigerd(client, db_session):
    _maak_kandidaat(db_session, "https://voorbeeldzorg.nl/jaarverslag.pdf")

    response = client.get(
        "/research/bron-pdf", params={"url": "http://169.254.169.254/latest/meta-data/"},
    )

    assert response.status_code == 404


def test_interne_adressen_zijn_niet_bereikbaar_via_de_proxy(client, db_session):
    _maak_kandidaat(db_session, "https://voorbeeldzorg.nl/jaarverslag.pdf")

    for intern in (
        "http://127.0.0.1:8000/health",
        "http://postgres.railway.internal:5432/",
        "http://localhost/admin",
    ):
        assert client.get("/research/bron-pdf", params={"url": intern}).status_code == 404


def test_niet_http_schema_wordt_geweigerd(client, db_session):
    response = client.get(
        "/research/bron-pdf", params={"url": "file:///etc/passwd"},
    )

    assert response.status_code == 400


def test_bekende_kandidaat_url_passeert_de_allowlist(client, db_session, monkeypatch):
    url = "https://voorbeeldzorg.nl/jaarverslag-2025.pdf"
    _maak_kandidaat(db_session, url)
    gevraagd = {}

    class FakeResponse:
        headers = {"content-type": "application/pdf"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"%PDF-1.7 nep"

        async def aclose(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def build_request(self, methode, doel, headers=None):
            gevraagd["url"] = doel
            return object()

        async def send(self, request, stream=False):
            return FakeResponse()

        async def aclose(self):
            return None

    import app.routers.research as research_router
    monkeypatch.setattr(research_router.httpx, "AsyncClient", FakeClient)

    response = client.get("/research/bron-pdf", params={"url": url})

    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 nep"
    assert gevraagd["url"] == url


def test_monitoringbron_passeert_de_allowlist_ook(client, db_session, monkeypatch):
    url = "https://sintjozef.nl/jaarrekening-2025.pdf"
    kandidaat = _maak_kandidaat(db_session, "https://ander.nl/iets.pdf")
    db_session.add(JaarverslagMonitoring(
        company_id=kandidaat.company_id, laatste_bron_url=url,
    ))
    db_session.commit()

    class FakeResponse:
        headers = {"content-type": "application/pdf"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self):
            yield b"%PDF"

        async def aclose(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def build_request(self, methode, doel, headers=None):
            return object()

        async def send(self, request, stream=False):
            return FakeResponse()

        async def aclose(self):
            return None

    import app.routers.research as research_router
    monkeypatch.setattr(research_router.httpx, "AsyncClient", FakeClient)

    assert client.get("/research/bron-pdf", params={"url": url}).status_code == 200
