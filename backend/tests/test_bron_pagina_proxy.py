"""De bron-pagina-route deelt de SSRF-allowlist met de PDF-proxy (zie
test_bron_pdf_proxy.py) en mag alleen bronnen tonen die de agent zelf vond.
"""
from app.models import Batch, BronKandidaat, Company, ResearchRun


def _maak_kandidaat(db_session, url: str) -> BronKandidaat:
    batch = Batch(naam="pagina-proxy-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(
        batch_id=batch.id, naam="Voorbeeld Zorg", vestigingsnummer="PAGPROXY-1",
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
        brontype="officiele_website",
        status="voorgesteld",
        rang=1,
    )
    db_session.add(kandidaat)
    db_session.commit()
    return kandidaat


def test_onbekende_url_wordt_geweigerd(client, db_session):
    _maak_kandidaat(db_session, "https://voorbeeldzorg.nl/team")

    response = client.get(
        "/research/bron-pagina",
        params={"url": "http://169.254.169.254/latest/meta-data/"},
    )

    assert response.status_code == 404


def test_niet_http_schema_wordt_geweigerd(client, db_session):
    response = client.get(
        "/research/bron-pagina", params={"url": "file:///etc/passwd"},
    )

    assert response.status_code == 400


def test_bekende_kandidaat_url_levert_gemarkeerde_leesweergave(
    client, db_session, monkeypatch,
):
    url = "https://voorbeeldzorg.nl/team"
    _maak_kandidaat(db_session, url)

    async def fake_haal_pagina_op(_url):
        return {"tekst": "Ons team bestaat uit 12 medewerkers.", "links": []}

    import app.routers.research as research_router
    monkeypatch.setattr(research_router, "_haal_pagina_op", fake_haal_pagina_op)

    response = client.get(
        "/research/bron-pagina",
        params={"url": url, "citaat": "Ons team bestaat uit 12 medewerkers."},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<mark id="citaat">Ons team bestaat uit 12 medewerkers.</mark>' in response.text


def test_response_zet_een_strikte_content_security_policy(
    client, db_session, monkeypatch,
):
    """De pagina bevat nooit eigen script's, dus mag CSP dat hard afdwingen."""
    url = "https://voorbeeldzorg.nl/team"
    _maak_kandidaat(db_session, url)

    async def fake_haal_pagina_op(_url):
        return {"tekst": "Tekst.", "links": []}

    import app.routers.research as research_router
    monkeypatch.setattr(research_router, "_haal_pagina_op", fake_haal_pagina_op)

    response = client.get("/research/bron-pagina", params={"url": url})

    assert response.headers["content-security-policy"] == (
        "default-src 'none'; style-src 'unsafe-inline'"
    )
