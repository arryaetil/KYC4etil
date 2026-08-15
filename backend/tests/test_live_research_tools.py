from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.providers import fetch, live, search
from app.research.live_tools import LiveResearchTools
from app.research.query_planner import QueryContext
from app.research.types import CombinedSearchResult, PlannedQuery
from app.research.validation import SourceDocument


@pytest.mark.asyncio
async def test_opgeloste_officiele_website_wordt_altijd_seed(monkeypatch):
    async def fake_haal_pagina_op(url):
        return {"tekst": "OKECHAMP B.V. verwerkt champignons in Velden.", "links": []}

    monkeypatch.setattr(live.settings, "openai_api_key", "")
    monkeypatch.setattr(fetch, "_haal_pagina_op", fake_haal_pagina_op)

    document = await LiveResearchTools().find_officiele_website(QueryContext(
        naam="Okechamp B.V.",
        gemeente="Horst aan de Maas",
        website_url="https://www.okechamp.eu/",
        gevraagd_jaar=2025,
    ))

    assert document is not None
    assert document.url == "https://www.okechamp.eu/"
    assert document.brontype == "officiele_website"


@pytest.mark.asyncio
async def test_inspect_gebruikt_crawl4ai_fallback_voor_js_zware_paginas(
    monkeypatch,
):
    """
    Regressie: Aviko Lomm leverde in de VR-testbatch (batch f575fc9c) een
    relevant nieuwsartikel op zonder medewerkerstal/bewijsfragment, omdat
    inspect() een platte HTTP-poging (_fetch_text) gebruikte die bij een
    JS-zware pagina alleen de lege paginaschil oplevert. _haal_pagina_op valt
    bij te weinig platte tekst zelf terug op Crawl4AI's browser-rendering.
    """
    aangeroepen_met = []

    async def fake_haal_pagina_op(url):
        aangeroepen_met.append(url)
        return {
            "tekst": "Aviko Lomm telt momenteel 400 medewerkers, aldus de directie.",
            "links": [],
        }

    monkeypatch.setattr(live.settings, "openai_api_key", "")
    monkeypatch.setattr(fetch, "_haal_pagina_op", fake_haal_pagina_op)
    monkeypatch.setattr(
        fetch, "_fetch_text",
        AsyncMock(side_effect=AssertionError(
            "inspect() moet _haal_pagina_op gebruiken, niet _fetch_text",
        )),
    )

    document = await LiveResearchTools().inspect(
        QueryContext(naam="Aviko Lomm", gemeente="Lomm", gevraagd_jaar=2025),
        PlannedQuery("media", "Aviko Lomm medewerkers nieuws", "reden"),
        CombinedSearchResult(
            title="Aviko Lomm nieuws",
            url="https://www.omroepvenlo.nl/nieuws/aviko-lomm",
            canonical_url="https://omroepvenlo.nl/nieuws/aviko-lomm",
            snippets=["Aviko Lomm in het nieuws"],
            providers=["serper"],
            queries=["Aviko Lomm medewerkers nieuws"],
        ),
    )

    assert aangeroepen_met == ["https://www.omroepvenlo.nl/nieuws/aviko-lomm"]
    assert document is not None
    assert document.tekst == (
        "Aviko Lomm telt momenteel 400 medewerkers, aldus de directie."
    )


@pytest.mark.asyncio
async def test_inspect_geeft_naamlijst_telling_door_in_raw_data(monkeypatch):
    """
    Regressie: Dreessen Advocaten en Poulissen noemen medewerkers bij naam
    zonder los getal. EXTRACT_PROMPT laat het model die lijst tellen; inspect()
    moet die telling en de gevonden namen doorgeven zodat de reviewer ziet dat
    het aantal is afgeleid, niet letterlijk genoemd.
    """
    async def fake_haal_pagina_op(url):
        return {"tekst": "Vier advocaten: Jan, Marie, Piet en Anna.", "links": []}

    async def fake_llm_extract(naam, gemeente, tekst):
        return {
            "wp_gevonden": 4,
            "context": "Vier advocaten: Jan, Marie, Piet en Anna.",
            "is_fte": False,
            "wp_afgeleid_uit_naamlijst": True,
            "genoemde_namen": ["Jan", "Marie", "Piet", "Anna"],
        }

    from app.providers import llm as llm_module
    from app.research import live_tools as live_tools_module

    # Rechtstreeks live_tools.get_settings monkeypatchen (i.p.v. het gedeelde
    # settings-singleton) maakt deze test onafhankelijk van of een andere test
    # get_settings.cache_clear() aanriep vóór deze draait.
    monkeypatch.setattr(
        live_tools_module, "get_settings",
        lambda: SimpleNamespace(openai_api_key="dummy"),
    )
    monkeypatch.setattr(fetch, "_haal_pagina_op", fake_haal_pagina_op)
    monkeypatch.setattr(llm_module, "_llm_extract", fake_llm_extract)

    document = await LiveResearchTools().inspect(
        QueryContext(naam="Dreessen Advocaten", gevraagd_jaar=2025),
        PlannedQuery("website", "Dreessen Advocaten team", "reden"),
        CombinedSearchResult(
            title="Onze advocaten",
            url="https://dreessenadvocaten.nl/advocaten",
            canonical_url="https://dreessenadvocaten.nl/advocaten",
            snippets=[],
            providers=["serper"],
            queries=["Dreessen Advocaten team"],
        ),
    )

    assert document is not None
    assert document.wp_gevonden == 4
    assert document.raw_data["wp_afgeleid_uit_naamlijst"] is True
    assert document.raw_data["genoemde_namen"] == ["Jan", "Marie", "Piet", "Anna"]


@pytest.mark.asyncio
async def test_lege_zoekindex_gebruikt_maximaal_een_fallback_per_pad(
    monkeypatch,
):
    calls = []

    async def fake_web_search(query, max_results=8):
        return []

    async def fake_openai_search(query, max_results=8):
        calls.append(query)
        return [{
            "title": "Officiële website",
            "url": "https://example.test",
            "snippet": "Example",
            "bron": "openai_web_search",
        }]

    monkeypatch.setattr(search, "_web_search", fake_web_search)
    monkeypatch.setattr(search, "_openai_web_search", fake_openai_search)
    tools = LiveResearchTools()

    first, second = await __import__("asyncio").gather(
        tools.search(
            PlannedQuery("website", "query één", "reden"),
            max_results=8,
        ),
        tools.search(
            PlannedQuery("website", "query twee", "reden"),
            max_results=8,
        ),
    )

    assert len(calls) == 1
    assert first[0].url == "https://example.test"
    assert second[0].url == "https://example.test"


@pytest.mark.asyncio
async def test_nieuwste_officiele_document_krijgt_eigen_site_search(
    monkeypatch,
):
    async def fake_web_search(query, max_results=8):
        return [{
            "title": "Jaarrekening en Maatschappelijk Verslag",
            "url": "https://www.mondriaan.eu/jaarrekening-en-maatschappelijk-verslag",
            "snippet": "Mondriaan Jaarrekening 2025",
            "bron": "serper",
        }]

    tools = LiveResearchTools()
    tools.inspect = AsyncMock(return_value=SourceDocument(
        naam="Mondriaan",
        company_website_url="https://www.mondriaan.eu",
        url="https://www.mondriaan.eu/jaarrekening-en-maatschappelijk-verslag",
        titel="Jaarrekening en Maatschappelijk Verslag",
        brontype="officiele_website",
        documenttype="jaarrekening",
        gevraagd_jaar=2025,
        verslagjaar=2025,
    ))
    monkeypatch.setattr(search, "_web_search", fake_web_search)

    document = await tools.find_nieuwste_officiele_document(QueryContext(
        naam="Mondriaan",
        gemeente="Heerlen",
        website_url="https://www.mondriaan.eu",
        gevraagd_jaar=2025,
    ))

    assert document is not None
    assert document.verslagjaar == 2025
    assert "site:mondriaan.eu" in tools.inspect.await_args.args[1].query


@pytest.mark.asyncio
async def test_documentjaar_mag_uit_zoeksnippet_komen(monkeypatch):
    async def fake_haal_pagina_op(url):
        return {
            "tekst": "Navigatie en algemene informatie zonder zichtbaar jaartal.",
            "links": [],
        }

    monkeypatch.setattr(live.settings, "openai_api_key", "")
    monkeypatch.setattr(fetch, "_haal_pagina_op", fake_haal_pagina_op)

    document = await LiveResearchTools().inspect(
        QueryContext(
            naam="Mondriaan",
            website_url="https://www.mondriaan.eu",
            gevraagd_jaar=2025,
        ),
        PlannedQuery("document", "site:mondriaan.eu 2025", "nieuwste"),
        CombinedSearchResult(
            title="Jaarrekening en Maatschappelijk Verslag",
            url="https://www.mondriaan.eu/jaarrekening-en-maatschappelijk-verslag",
            canonical_url="https://mondriaan.eu/jaarrekening-en-maatschappelijk-verslag",
            snippets=["Mondriaan Jaarrekening 2025"],
            providers=["serper"],
            queries=["site:mondriaan.eu 2025"],
        ),
    )

    assert document is not None
    assert document.verslagjaar == 2025


@pytest.mark.asyncio
async def test_nieuwste_officiele_document_probeert_stabiele_publicatiepagina(
    monkeypatch,
):
    async def fake_web_search(query, max_results=8):
        return []

    tools = LiveResearchTools()

    async def fake_inspect(context, query, result):
        if result.url.endswith("/jaarrekening-en-maatschappelijk-verslag"):
            return SourceDocument(
                naam=context.naam,
                company_website_url=context.website_url,
                url=result.url,
                titel="Jaarrekening en Maatschappelijk Verslag",
                brontype="officiele_website",
                documenttype="jaarrekening",
                gevraagd_jaar=2025,
                verslagjaar=2025,
            )
        return None

    tools.inspect = AsyncMock(side_effect=fake_inspect)
    monkeypatch.setattr(search, "_web_search", fake_web_search)

    document = await tools.find_nieuwste_officiele_document(QueryContext(
        naam="Mondriaan",
        website_url="https://www.mondriaan.eu/over-ons",
        gevraagd_jaar=2025,
    ))

    assert document is not None
    assert (
        document.url
        == "https://www.mondriaan.eu/jaarrekening-en-maatschappelijk-verslag"
    )


@pytest.mark.asyncio
async def test_publicatiepagina_leidt_naar_pdf_van_gevraagde_jaargang(
    monkeypatch,
):
    async def fake_web_search(query, max_results=8):
        return []

    async def fake_page(url):
        if url.endswith("/jaarrekening-en-maatschappelijk-verslag"):
            return {
                "tekst": "Terugblik 2025",
                "links": [{
                    "tekst": "Mondriaan Jaarrekening 2025",
                    "url": (
                        "https://www.mondriaan.eu/sites/mondriaan/files/"
                        "2026-05/Mondriaan-Jaarverantwoording-2025.pdf"
                    ),
                }],
            }
        raise RuntimeError("geen publicatiepagina")

    async def fake_inspect(context, query, result):
        return SourceDocument(
            naam=context.naam,
            company_website_url=context.website_url,
            url=result.url,
            titel=result.title,
            brontype="jaarverslag",
            documenttype="jaarverslag",
            gevraagd_jaar=2025,
            verslagjaar=2025,
            wp_gevonden=2200,
        )

    tools = LiveResearchTools()
    tools.inspect = AsyncMock(side_effect=fake_inspect)
    monkeypatch.setattr(search, "_web_search", fake_web_search)
    monkeypatch.setattr(fetch, "_haal_pagina_op", fake_page)

    document = await tools.find_nieuwste_officiele_document(QueryContext(
        naam="Mondriaan",
        website_url="https://www.mondriaan.eu",
        gevraagd_jaar=2025,
    ))

    assert document is not None
    assert document.url.endswith(
        "/2026-05/Mondriaan-Jaarverantwoording-2025.pdf"
    )
    assert document.wp_gevonden == 2200
