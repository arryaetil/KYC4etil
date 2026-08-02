# Research-agent efficiëntie- en kostentracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De researchagent laat de reviewer meer bronkandidaten zien (3→8), stopt met dubbel zoekwerk naar hetzelfde jaarverslag, wordt sneller door onafhankelijke stappen parallel te laten lopen, en houdt voortaan daadwerkelijk OpenAI-tokenverbruik en -kosten per run bij.

**Architecture:** Vier los te reviewen wijzigingen in de bestaande `backend/app/research/`-pipeline. Geen nieuwe externe afhankelijkheden, geen databasemigraties (kostenvelden bestaan al op `ResearchRun`). Eén nieuwe module (`app/research/seeds.py`) voor de seed-documentlogica die nu inline in `service.py` staat, en één nieuwe module (`app/research/usage.py`) voor tokentracking via `contextvars` (correct werkend over `asyncio.gather`-taken heen).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, pytest + pytest-asyncio, bestaande OpenAI Responses API-integratie.

## Global Constraints

- Elke taak moet na afloop groen zijn op `pytest tests/ -q` (huidige baseline: 244 passed) vóór de volgende taak begint.
- Geen wijziging aan de bronstrategie zelf (welke queries, welke paden) — alleen aan hoeveelheid getoonde kandidaten, volgorde/parallellisatie van bestaande stappen, en observability.
- Het media-pad (nieuws/reorganisatie-queries) blijft ongewijzigd altijd meelopen — niet aanraken.
- Nederlandse domeintaal aanhouden in nieuwe functienamen/comments, consistent met de rest van de codebase.
- Na elke taak: `git add` + commit met een beschrijvende Nederlandstalige boodschap, in lijn met de bestaande commit-conventie in dit project.

---

## Task 1: Kandidaten-limiet configureerbaar maken (3 → 8)

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/research/supervisor.py`
- Modify: `backend/app/research/service.py`
- Test: `backend/tests/test_research_supervisor.py`

**Interfaces:**
- Produces: `ResearchSupervisor.__init__(..., max_kandidaten: int = 3)` — nieuwe keyword-parameter, bestaand gedrag (default 3) blijft ongewijzigd voor bestaande call sites die 'm niet expliciet meegeven.
- Produces: `Settings.research_max_kandidaten: int = 8` op `app/config.py`.

- [ ] **Step 1: Schrijf de falende test voor een hogere, configureerbare cap**

Voeg toe aan `backend/tests/test_research_supervisor.py` (na de bestaande `ManyResultsResearchTools`-klasse, vóór `test_klein_paginabudget_wordt_over_onderzoekspaden_verdeeld`):

```python
class VeleKandidatenResearchTools(FakeResearchTools):
    """Levert 3 unieke, goedgekeurde documenten per pad (9 totaal) om de
    kandidaten-cap te kunnen testen los van het paginabudget."""

    async def search(self, query: PlannedQuery, max_results: int):
        return [
            CombinedSearchResult(
                title=f"{query.pad} bron {index}",
                url=f"https://voorbeeldzorg.nl/{query.pad}/{index}",
                canonical_url=f"https://voorbeeldzorg.nl/{query.pad}/{index}",
                snippets=[f"{index} medewerkers."],
                providers=["serper"],
                queries=[query.query],
            )
            for index in range(3)
        ]

    async def inspect(self, context, query, result):
        return SourceDocument(
            naam=context.naam,
            company_website_url=context.website_url,
            url=result.url,
            titel=result.title,
            tekst=f"Voorbeeld Zorg telde {result.title}.",
            brontype="officiele_website" if query.pad == "website" else (
                "jaarverslag" if query.pad == "document" else "media"
            ),
            documenttype="teampagina",
            wp_gevonden=47,
            eenheid="werkzame_personen",
            bewijsfragment=f"Voorbeeld Zorg telde {result.title}.",
        )


@pytest.mark.asyncio
async def test_kandidaten_limiet_is_configureerbaar():
    tools = VeleKandidatenResearchTools()

    outcome_default = await ResearchSupervisor(
        tools, max_queries=12, max_pages=9,
    ).run(QueryContext(
        naam="Voorbeeld Zorg",
        website_url="https://voorbeeldzorg.nl",
        huidig_jaar=2026,
    ))
    assert len(outcome_default.kandidaten) == 3

    outcome_ruim = await ResearchSupervisor(
        tools, max_queries=12, max_pages=9, max_kandidaten=8,
    ).run(QueryContext(
        naam="Voorbeeld Zorg",
        website_url="https://voorbeeldzorg.nl",
        huidig_jaar=2026,
    ))
    assert len(outcome_ruim.kandidaten) == 8
```

- [ ] **Step 2: Run de test om te bevestigen dat hij faalt**

Run: `cd backend && python3 -m pytest tests/test_research_supervisor.py::test_kandidaten_limiet_is_configureerbaar -v`
Expected: FAIL met `TypeError: ResearchSupervisor.__init__() got an unexpected keyword argument 'max_kandidaten'`

- [ ] **Step 3: Voeg de parameter toe aan `ResearchSupervisor`**

In `backend/app/research/supervisor.py`, vervang:

```python
class ResearchSupervisor:
    def __init__(
        self,
        tools: ResearchTools,
        max_queries: int,
        max_pages: int,
        max_results_per_query: int = 8,
        reviewer=None,
    ):
        self.tools = tools
        self.max_queries = max_queries
        self.max_pages = max_pages
        self.max_results_per_query = max_results_per_query
        self.reviewer = reviewer
```

door:

```python
class ResearchSupervisor:
    def __init__(
        self,
        tools: ResearchTools,
        max_queries: int,
        max_pages: int,
        max_results_per_query: int = 8,
        max_kandidaten: int = 3,
        reviewer=None,
    ):
        self.tools = tools
        self.max_queries = max_queries
        self.max_pages = max_pages
        self.max_results_per_query = max_results_per_query
        self.max_kandidaten = max_kandidaten
        self.reviewer = reviewer
```

En verderop in dezelfde klasse, in de `run()`-methode, vervang:

```python
        ranked = rank_bronnen(validaties)[:3]
```

door:

```python
        ranked = rank_bronnen(validaties)[:self.max_kandidaten]
```

- [ ] **Step 4: Run de test opnieuw om te bevestigen dat hij slaagt**

Run: `cd backend && python3 -m pytest tests/test_research_supervisor.py -v`
Expected: alle tests in dit bestand PASS, inclusief de nieuwe.

- [ ] **Step 5: Voeg de setting toe en gebruik 'm in de aanroep vanuit `service.py`**

In `backend/app/config.py`, voeg toe direct na de regel `research_max_rounds: int = 3` (regel 26):

```python
    research_max_kandidaten: int = 8
```

In `backend/app/research/service.py`, in `run_research_run`, vervang:

```python
        outcome = await ResearchSupervisor(
            tools,
            max_queries=settings.research_max_queries,
            max_pages=effectief_max_paginas,
            reviewer=(
                IntelligentSourceReviewer()
                if settings.provider_mode == "live"
                else None
            ),
```

door:

```python
        outcome = await ResearchSupervisor(
            tools,
            max_queries=settings.research_max_queries,
            max_pages=effectief_max_paginas,
            max_kandidaten=settings.research_max_kandidaten,
            reviewer=(
                IntelligentSourceReviewer()
                if settings.provider_mode == "live"
                else None
            ),
```

- [ ] **Step 6: Run de volledige testsuite**

Run: `cd backend && python3 -m pytest tests/ -q`
Expected: alle tests PASS (245, één meer dan de baseline van 244).

- [ ] **Step 7: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add backend/app/config.py backend/app/research/supervisor.py backend/app/research/service.py backend/tests/test_research_supervisor.py
git commit -m "feat(research): configureerbare kandidaten-limiet, standaard 8 i.p.v. 3"
```

---

## Task 2: Seed-documentverzameling extraheren, dedupliceren en parallelliseren

**Files:**
- Create: `backend/app/research/seeds.py`
- Modify: `backend/app/research/service.py`
- Test: `backend/tests/test_research_seeds.py`

**Interfaces:**
- Consumes: `QueryContext` (`app/research/query_planner.py`), `SourceDocument` (`app/research/validation.py`), `LiveResearchTools` (`app/research/live_tools.py`).
- Produces: `async def verzamel_seed_documenten(tools: LiveResearchTools, context: QueryContext) -> list[SourceDocument]` — vervangt de drie losse `try/except`-blokken die nu inline in `run_research_run` staan.

- [ ] **Step 1: Schrijf de falende tests**

Maak `backend/tests/test_research_seeds.py`:

```python
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
```

- [ ] **Step 2: Run de tests om te bevestigen dat ze falen**

Run: `cd backend && python3 -m pytest tests/test_research_seeds.py -v`
Expected: FAIL met `ModuleNotFoundError: No module named 'app.research.seeds'`

- [ ] **Step 3: Implementeer `app/research/seeds.py`**

```python
"""Seed-documenten voor de researchsupervisor: officiële website, nieuwste
formele document en (indien nodig) het jaarverslag-agent-pad.

Website- en documentzoektocht zijn onderling onafhankelijk (beide werken op
de al bekende context.website_url) en lopen daarom parallel. De
jaarverslag-agent (LangGraph, met eigen retries) wordt alleen nog aangeroepen
als de documentzoektocht nog geen document met zowel het gevraagde
verslagjaar als een WP-getal heeft opgeleverd — anders proberen twee
onafhankelijke strategieën hetzelfde te vinden."""
import asyncio

from .live_tools import LiveResearchTools
from .query_planner import QueryContext
from .validation import SourceDocument


def _is_volledige_match(document: SourceDocument | None, gevraagd_jaar: int | None) -> bool:
    return (
        document is not None
        and gevraagd_jaar is not None
        and document.verslagjaar == gevraagd_jaar
        and document.wp_gevonden is not None
    )


async def verzamel_seed_documenten(
    tools: LiveResearchTools,
    context: QueryContext,
) -> list[SourceDocument]:
    seed_documents: list[SourceDocument] = []

    async def _veilig(coroutine):
        try:
            return await coroutine
        except Exception:
            return None

    officiele_website, nieuwste_document = await asyncio.gather(
        _veilig(tools.find_officiele_website(context)),
        _veilig(tools.find_nieuwste_officiele_document(context)),
    )
    if officiele_website is not None:
        seed_documents.append(officiele_website)
    if nieuwste_document is not None:
        seed_documents.append(nieuwste_document)

    if not _is_volledige_match(nieuwste_document, context.gevraagd_jaar):
        jaarverslag = await _veilig(tools.find_jaarverslag(context))
        if jaarverslag is not None:
            seed_documents.append(jaarverslag)

    return seed_documents
```

- [ ] **Step 4: Run de tests opnieuw om te bevestigen dat ze slagen**

Run: `cd backend && python3 -m pytest tests/test_research_seeds.py -v`
Expected: alle 5 tests PASS.

- [ ] **Step 5: Vervang de inline seed-logica in `service.py` door de nieuwe helper**

In `backend/app/research/service.py`, vervang het blok:

```python
        seed_documents = []
        if settings.provider_mode == "live":
            try:
                officiele_website = await tools.find_officiele_website(context)
                if officiele_website is not None:
                    seed_documents.append(officiele_website)
            except Exception:
                pass
            try:
                nieuwste_document = (
                    await tools.find_nieuwste_officiele_document(context)
                )
                if nieuwste_document is not None:
                    seed_documents.append(nieuwste_document)
            except Exception:
                pass
            try:
                jaarverslag = await tools.find_jaarverslag(context)
                if jaarverslag is not None:
                    seed_documents.append(jaarverslag)
            except Exception:
                # De brede autonome zoekpaden blijven beschikbaar als het
                # gespecialiseerde documentpad niets oplevert.
                pass
```

door:

```python
        seed_documents = (
            await verzamel_seed_documenten(tools, context)
            if settings.provider_mode == "live"
            else []
        )
```

En voeg de import toe bovenaan `backend/app/research/service.py`, bij de andere `from .`-imports:

```python
from .seeds import verzamel_seed_documenten
```

- [ ] **Step 6: Run de volledige testsuite**

Run: `cd backend && python3 -m pytest tests/ -q`
Expected: alle tests PASS (250, vijf meer dan na Task 1).

- [ ] **Step 7: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add backend/app/research/seeds.py backend/app/research/service.py backend/tests/test_research_seeds.py
git commit -m "refactor(research): seed-documenten parallel ophalen, jaarverslag-agent overslaan bij exacte match"
```

---

## Task 3: Bronreview-calls concurrent maken

**Files:**
- Modify: `backend/app/research/supervisor.py`
- Test: `backend/tests/test_research_supervisor.py`

**Interfaces:**
- Geen wijziging aan publieke signaturen; alleen intern gedrag van `ResearchSupervisor.run()`.

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `backend/tests/test_research_supervisor.py`:

```python
class TrageReviewTools(FakeResearchTools):
    """3 documenten (1 per pad), elk met een kunstmatige vertraging in
    inspect() zodat sequentieel vs. concurrent review meetbaar is."""

    async def inspect(self, context, query, result):
        await asyncio.sleep(0.05)
        return await super().inspect(context, query, result)


class TrageReviewer:
    async def review(self, context, document):
        from app.research.validation import valideer_bron
        await asyncio.sleep(0.05)
        return valideer_bron(document)


@pytest.mark.asyncio
async def test_bronreview_calls_lopen_concurrent():
    tools = TrageReviewTools()

    loop = asyncio.get_event_loop()
    start = loop.time()
    outcome = await ResearchSupervisor(
        tools, max_queries=12, max_pages=20, reviewer=TrageReviewer(),
    ).run(QueryContext(
        naam="Voorbeeld Zorg",
        gevraagd_jaar=2025,
        website_url="https://voorbeeldzorg.nl",
        huidig_jaar=2026,
    ))
    duur = loop.time() - start

    # 3 documenten x (0.05s ophalen + 0.05s review) sequentieel zou >= 0.30s
    # duren. Met concurrent ophalen (bestaand gedrag) én concurrent review
    # (nieuw) moet dit ruim onder die grens blijven.
    assert duur < 0.20
    assert len(outcome.kandidaten) == 3
```

Voeg `import asyncio` toe bovenaan `backend/tests/test_research_supervisor.py` als die er nog niet staat (controleer eerst — `date` en `pytest` staan er al, `asyncio` niet).

- [ ] **Step 2: Run de test om te bevestigen dat hij faalt**

Run: `cd backend && python3 -m pytest tests/test_research_supervisor.py::test_bronreview_calls_lopen_concurrent -v`
Expected: FAIL — `duur` is >= 0.30s omdat de review-lus nu nog sequentieel is.

- [ ] **Step 3: Maak de review-lus concurrent**

In `backend/app/research/supervisor.py`, in `run()`, vervang het blok:

```python
        inspected = await asyncio.gather(*[
            self.tools.inspect(context, query, result)
            for query, result in te_inspecteren
        ], return_exceptions=True)
        validaties = []
        afwijzingen = []
        documenten = 0
        for item in [*seed_documents, *inspected]:
            if isinstance(item, BaseException):
                fouten.append(f"inspectie: {item}")
                continue
            if item is not None:
                documenten += 1
                if self.reviewer is not None:
                    try:
                        validatie = await self.reviewer.review(context, item)
                        validaties.append(validatie)
                    except Exception as exc:
                        fouten.append(f"bronreview: {exc}")
                        continue
                else:
                    validatie = valideer_bron(item)
                    validaties.append(validatie)
                if validatie.is_afgewezen and len(afwijzingen) < 12:
                    intelligente_review = validatie.validaties.get(
                        "intelligente_review", {}
                    )
                    afwijzingen.append({
                        "titel": item.titel,
                        "url": item.url,
                        "identity_class": validatie.identity_class,
                        "redenen": list(validatie.afwijsredenen),
                        "review_reden": intelligente_review.get("reden"),
                    })
```

door:

```python
        inspected = await asyncio.gather(*[
            self.tools.inspect(context, query, result)
            for query, result in te_inspecteren
        ], return_exceptions=True)
        documenten_om_te_beoordelen = [
            item for item in [*seed_documents, *inspected]
            if item is not None and not isinstance(item, BaseException)
        ]
        for item in inspected:
            if isinstance(item, BaseException):
                fouten.append(f"inspectie: {item}")

        async def _beoordeel(document):
            if self.reviewer is not None:
                try:
                    return await self.reviewer.review(context, document)
                except Exception as exc:
                    return exc
            return valideer_bron(document)

        beoordelingen = await asyncio.gather(*[
            _beoordeel(document) for document in documenten_om_te_beoordelen
        ])

        validaties = []
        afwijzingen = []
        documenten = len(documenten_om_te_beoordelen)
        for item, validatie in zip(documenten_om_te_beoordelen, beoordelingen):
            if isinstance(validatie, BaseException):
                fouten.append(f"bronreview: {validatie}")
                continue
            validaties.append(validatie)
            if validatie.is_afgewezen and len(afwijzingen) < 12:
                intelligente_review = validatie.validaties.get(
                    "intelligente_review", {}
                )
                afwijzingen.append({
                    "titel": item.titel,
                    "url": item.url,
                    "identity_class": validatie.identity_class,
                    "redenen": list(validatie.afwijsredenen),
                    "review_reden": intelligente_review.get("reden"),
                })
```

Let op: dit verandert de betekenis van `documenten` niet (nog steeds het aantal succesvol geïnspecteerde documenten, inclusief seeds), maar telt 'm nu vóór de review-lus i.p.v. tijdens — functioneel gelijk, want elk item in `documenten_om_te_beoordelen` werd voorheen ook precies één keer meegeteld.

- [ ] **Step 4: Run de nieuwe test en de rest van het bestand**

Run: `cd backend && python3 -m pytest tests/test_research_supervisor.py -v`
Expected: alle tests PASS, inclusief `test_bronreview_calls_lopen_concurrent`.

- [ ] **Step 5: Run de volledige testsuite**

Run: `cd backend && python3 -m pytest tests/ -q`
Expected: alle tests PASS (251, één meer dan na Task 2).

- [ ] **Step 6: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add backend/app/research/supervisor.py backend/tests/test_research_supervisor.py
git commit -m "perf(research): bronreview-calls concurrent i.p.v. sequentieel"
```

---

## Task 4: Kostentracking-module + instrumentatie van LLM-call-sites

**Files:**
- Create: `backend/app/research/usage.py`
- Modify: `backend/app/providers/live.py`
- Modify: `backend/app/research/source_reviewer.py`
- Test: `backend/tests/test_research_usage.py`

**Interfaces:**
- Produces: `start_usage_tracking() -> None`
- Produces: `record_response_usage(response) -> None`
- Produces: `get_usage_totals() -> tuple[int, int]` (tokens_in, tokens_out)
- Produces: `bereken_kosten_cents(tokens_in: int, tokens_out: int) -> int`
- Produces (intern in `live.py`): `async def _create_response(client, **kwargs)` — vervangt directe `client.responses.create(...)`-aanroepen.

- [ ] **Step 1: Schrijf de falende tests voor de usage-module**

Maak `backend/tests/test_research_usage.py`:

```python
"""Per-run tokenverbruik: contextvar-gebaseerde teller, ook over
gelijktijdige asyncio-taken heen."""
import asyncio
from types import SimpleNamespace

import pytest

from app.research.usage import (
    bereken_kosten_cents,
    get_usage_totals,
    record_response_usage,
    start_usage_tracking,
)


def _response(input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=input_tokens, output_tokens=output_tokens,
        ),
    )


def test_zonder_actieve_tracking_blijft_totaal_op_nul():
    assert get_usage_totals() == (0, 0)
    record_response_usage(_response(100, 20))
    assert get_usage_totals() == (0, 0)


def test_telt_meerdere_responses_op():
    start_usage_tracking()
    record_response_usage(_response(100, 20))
    record_response_usage(_response(50, 10))
    assert get_usage_totals() == (150, 30)


def test_response_zonder_usage_veld_wordt_genegeerd():
    start_usage_tracking()
    record_response_usage(SimpleNamespace())
    assert get_usage_totals() == (0, 0)


@pytest.mark.asyncio
async def test_contextvar_isoleert_gelijktijdige_taken():
    async def taak(tokens_in: int) -> tuple[int, int]:
        start_usage_tracking()
        record_response_usage(_response(tokens_in, 5))
        await asyncio.sleep(0.01)
        return get_usage_totals()

    resultaten = await asyncio.gather(taak(100), taak(200), taak(300))

    assert resultaten == [(100, 5), (200, 5), (300, 5)]


def test_bereken_kosten_cents():
    # 1000 input- + 1000 output-tokens tegen de standaardprijzen in config.py.
    cents = bereken_kosten_cents(1000, 1000)
    assert cents > 0
    assert cents == round(1000 / 1000 * 1.5 + 1000 / 1000 * 6.0)
```

- [ ] **Step 2: Run de tests om te bevestigen dat ze falen**

Run: `cd backend && python3 -m pytest tests/test_research_usage.py -v`
Expected: FAIL met `ModuleNotFoundError: No module named 'app.research.usage'`

- [ ] **Step 3: Voeg de prijssettings toe aan `config.py`**

In `backend/app/config.py`, voeg toe direct na de nieuwe regel `research_max_kandidaten: int = 8` (toegevoegd in Task 1):

```python
    # Indicatieve OpenAI-prijzen (cent per 1000 tokens) — controleer tegen de
    # actuele OpenAI-pricingpagina voor het geconfigureerde model vóórdat
    # kosten_cents als harde budgetbron wordt gebruikt.
    openai_prijs_in_cent_per_1k: float = 1.5
    openai_prijs_out_cent_per_1k: float = 6.0
```

- [ ] **Step 4: Implementeer `app/research/usage.py`**

```python
"""Per-run OpenAI-tokenverbruik bijhouden, correct over concurrente
asyncio-taken heen via contextvars (nodig sinds seed-stappen en
bronreview-calls parallel lopen — zie Task 2/3)."""
from contextvars import ContextVar
from dataclasses import dataclass

from ..config import get_settings


@dataclass
class _UsageTotalen:
    tokens_in: int = 0
    tokens_out: int = 0


_huidige_totalen: ContextVar["_UsageTotalen | None"] = ContextVar(
    "_huidige_totalen", default=None,
)


def start_usage_tracking() -> None:
    """Start (of reset) de teller voor de huidige asyncio-context."""
    _huidige_totalen.set(_UsageTotalen())


def record_response_usage(response) -> None:
    """Telt het tokenverbruik van één OpenAI Responses-call op bij de lopende
    tracking. Geen effect zonder actieve tracking (bv. losse scripts) of als
    de response geen bruikbaar usage-veld heeft."""
    totalen = _huidige_totalen.get()
    if totalen is None:
        return
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    totalen.tokens_in += getattr(usage, "input_tokens", None) or 0
    totalen.tokens_out += getattr(usage, "output_tokens", None) or 0


def get_usage_totals() -> tuple[int, int]:
    totalen = _huidige_totalen.get()
    if totalen is None:
        return (0, 0)
    return (totalen.tokens_in, totalen.tokens_out)


def bereken_kosten_cents(tokens_in: int, tokens_out: int) -> int:
    settings = get_settings()
    cents = (
        tokens_in / 1000 * settings.openai_prijs_in_cent_per_1k
        + tokens_out / 1000 * settings.openai_prijs_out_cent_per_1k
    )
    return round(cents)
```

- [ ] **Step 5: Run de usage-tests opnieuw**

Run: `cd backend && python3 -m pytest tests/test_research_usage.py -v`
Expected: alle 5 tests PASS.

- [ ] **Step 6: Schrijf de falende tests voor instrumentatie van de call-sites**

Voeg toe aan `backend/tests/test_live_openai.py` (zelfde bestand, zelfde monkeypatch-conventie als de bestaande `test_openai_extract_parseert_json`-test — bekijk die test bovenin het bestand voor de `_FakeOpenAI`-fixture-stijl vóórdat je dit schrijft):

```python
@pytest.mark.asyncio
async def test_llm_extract_registreert_tokenverbruik(monkeypatch):
    from app.research import usage

    class UsageResponse:
        output_text = '{"wp_gevonden": 47}'
        usage = type("Usage", (), {"input_tokens": 120, "output_tokens": 30})()

    class UsageResponses:
        async def create(self, **kwargs):
            return UsageResponse()

    class UsageOpenAI:
        def __init__(self, api_key):
            self.responses = UsageResponses()

    import openai
    monkeypatch.setattr(live.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(openai, "AsyncOpenAI", UsageOpenAI)

    usage.start_usage_tracking()
    await live._llm_extract("Voorbeeld Zorg", "Adres 1", "47 medewerkers.")

    assert usage.get_usage_totals() == (120, 30)
```

Voeg toe aan `backend/tests/test_live_openai.py` (controleer eerst of `IntelligentSourceReviewer` al ergens getest wordt in dit bestand of elders — zo niet, maak dit een los testbestand `backend/tests/test_source_reviewer_usage.py` met de juiste imports):

```python
"""Tokenverbruik van de bronreviewer wordt bijgehouden."""
import pytest

from app.research import usage
from app.research.query_planner import QueryContext
from app.research.source_reviewer import IntelligentSourceReviewer
from app.research.validation import SourceDocument


@pytest.mark.asyncio
async def test_bronreview_registreert_tokenverbruik(monkeypatch):
    from app.config import get_settings

    class UsageResponse:
        output_text = (
            '{"beslissing": "tonen_aan_reviewer", "identity_class": '
            '"exact_entity", "scope_class": "vestiging", '
            '"gevonden_organisatie": "Voorbeeld Zorg", "reden": "match"}'
        )
        usage = type("Usage", (), {"input_tokens": 200, "output_tokens": 40})()

    class UsageResponses:
        async def create(self, **kwargs):
            return UsageResponse()

    class UsageOpenAI:
        def __init__(self, api_key):
            self.responses = UsageResponses()

    import openai
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(openai, "AsyncOpenAI", UsageOpenAI)

    usage.start_usage_tracking()
    document = SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://anderdomein.nl",
        url="https://onbekend.nl/artikel",
        titel="Artikel",
        tekst="Voorbeeld Zorg heeft 47 medewerkers.",
        brontype="media",
        wp_gevonden=47,
        eenheid="werkzame_personen",
        bewijsfragment="47 medewerkers.",
    )
    context = QueryContext(
        naam="Voorbeeld Zorg", website_url="https://voorbeeldzorg.nl",
    )

    await IntelligentSourceReviewer().review(context, document)

    assert usage.get_usage_totals() == (200, 40)
```

- [ ] **Step 7: Run de nieuwe tests om te bevestigen dat ze falen**

Run: `cd backend && python3 -m pytest tests/test_live_openai.py backend/tests/test_source_reviewer_usage.py -v`
Expected: FAIL — `get_usage_totals()` blijft `(0, 0)` omdat de call-sites nog niet instrumenteren.

- [ ] **Step 8: Voeg de wrapper toe in `providers/live.py` en gebruik 'm overal**

Voeg de import toe bovenaan `backend/app/providers/live.py`, bij de bestaande relatieve imports:

```python
from ..research.usage import record_response_usage
```

Voeg direct na de constante `PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"` een nieuwe helper toe:

```python
async def _create_response(client, **kwargs):
    """Wrapper om elke OpenAI Responses-call zodat tokenverbruik van élke
    aanroep in dit bestand altijd wordt geteld, zonder elke call-site apart
    te hoeven aanpassen als de trackinglogica zelf verandert."""
    response = await client.responses.create(**kwargs)
    record_response_usage(response)
    return response
```

Vervang vervolgens **elk** van de volgende 6 voorkomens van `await client.responses.create(` in `backend/app/providers/live.py` door `await _create_response(client,` (laat de rest van elke aanroep exact ongewijzigd — alleen de functienaam en het toevoegen van `client,` als eerste argument veranderen):

1. Regel ~107, in `_llm_classify_scope`
2. Regel ~124, in `_llm_classify_identity_and_scope`
3. Regel ~692, in `_parse_json_met_herstel` (de herstel-aanroep)
4. Regel ~705, in `_llm_extract`
5. Regel ~1172, in `_tool_use_loop` (eerste aanroep)
6. Regel ~1208, in `_tool_use_loop` (vervolg-aanroep in de lus)

Zoek exact op de string `client.responses.create(` om alle 6 voorkomens te vinden — regelnummers kunnen licht verschoven zijn door eerdere taken in dit plan.

- [ ] **Step 9: Instrumenteer de aanroep in `source_reviewer.py`**

In `backend/app/research/source_reviewer.py`, voeg de import toe:

```python
from .usage import record_response_usage
```

De aanroep van `client.responses.create(...)` zelf in `_llm_review` blijft
ongewijzigd (geen wrapper hier — dit bestand heeft maar één call-site, dus
een aparte `_create_response`-helper zoals in `live.py` voegt niets toe).
Vervang alleen de laatste regel van de methode, direct na de
`client.responses.create(...)`-aanroep:

```python
        return json.loads(response.output_text)
```

door:

```python
        record_response_usage(response)
        return json.loads(response.output_text)
```

- [ ] **Step 10: Run de instrumentatietests opnieuw**

Run: `cd backend && python3 -m pytest tests/test_live_openai.py tests/test_source_reviewer_usage.py -v`
Expected: alle tests PASS.

- [ ] **Step 11: Run de volledige testsuite**

Run: `cd backend && python3 -m pytest tests/ -q`
Expected: alle tests PASS (259, acht meer dan na Task 3: 5 usage-tests + 1 extract-test + 1 reviewer-test + bestaande baseline).

- [ ] **Step 12: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add backend/app/config.py backend/app/research/usage.py backend/app/providers/live.py backend/app/research/source_reviewer.py backend/tests/test_research_usage.py backend/tests/test_live_openai.py backend/tests/test_source_reviewer_usage.py
git commit -m "feat(research): tokenverbruik per OpenAI-call bijhouden via contextvar-teller"
```

---

## Task 5: Kostentracking wegschrijven op `ResearchRun`

**Files:**
- Modify: `backend/app/research/service.py`
- Test: `backend/tests/test_research_service_usage.py`

**Interfaces:**
- Consumes: `start_usage_tracking`, `get_usage_totals`, `bereken_kosten_cents` uit `app/research/usage.py` (Task 4).
- Geen nieuwe publieke interface — vult drie bestaande, tot nu toe ongebruikte kolommen op `ResearchRun`: `tokens_in`, `tokens_out`, `kosten_cents`.

- [ ] **Step 1: Schrijf de falende test**

Maak `backend/tests/test_research_service_usage.py`. Dit bestand gebruikt een eigen, geïsoleerde in-memory database (los van de `conftest.py`-fixtures, omdat `run_research_run` zijn eigen `SessionLocal` uit `app.database` gebruikt, niet de testclient-sessie):

```python
"""Kostentracking wordt na een researchrun weggeschreven op ResearchRun."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Batch, Company, ResearchRun
import app.models  # noqa: F401 — zorgt dat alle modellen geregistreerd zijn


@pytest.fixture
def geisoleerde_sessionmaker():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_run_research_run_vult_tokentracking(
    monkeypatch, geisoleerde_sessionmaker,
):
    from app.research import service, usage

    monkeypatch.setattr(service, "SessionLocal", geisoleerde_sessionmaker)

    with geisoleerde_sessionmaker() as db:
        batch = Batch(naam="usage-test", jaar=2026, totaal=1)
        db.add(batch)
        db.flush()
        company = Company(
            batch_id=batch.id, naam="Voorbeeld Zorg",
            vestigingsnummer="USAGE-1",
        )
        db.add(company)
        db.flush()
        run = ResearchRun(
            company_id=company.id, batch_id=batch.id,
            doel="test", status="pending",
        )
        db.add(run)
        db.commit()
        run_id = run.id

    monkeypatch.setattr(
        service.get_settings(), "provider_mode", "mock",
    )

    def fake_get_usage_totals():
        return (321, 45)

    monkeypatch.setattr(usage, "get_usage_totals", fake_get_usage_totals)
    monkeypatch.setattr(service, "get_usage_totals", fake_get_usage_totals)

    await service.run_research_run(run_id)

    with geisoleerde_sessionmaker() as db:
        opgeslagen = db.get(ResearchRun, run_id)
        assert opgeslagen.status == "completed"
        assert opgeslagen.tokens_in == 321
        assert opgeslagen.tokens_out == 45
        assert opgeslagen.kosten_cents == usage.bereken_kosten_cents(321, 45)
```

- [ ] **Step 2: Run de test om te bevestigen dat hij faalt**

Run: `cd backend && python3 -m pytest tests/test_research_service_usage.py -v`
Expected: FAIL — `opgeslagen.tokens_in` is `None` in plaats van `321` (de kolommen worden nog nergens gevuld).

- [ ] **Step 3: Wire de tracking in `run_research_run`**

In `backend/app/research/service.py`, voeg de import toe bij de andere `from .`-imports:

```python
from .usage import bereken_kosten_cents, get_usage_totals, start_usage_tracking
```

Vervang de openingsregels van `run_research_run`:

```python
async def run_research_run(run_id: str) -> None:
    context = None
    website_resolution = {
        "status": "niet_gevonden",
        "website_url": None,
        "bron": None,
    }
    try:
```

door:

```python
async def run_research_run(run_id: str) -> None:
    context = None
    website_resolution = {
        "status": "niet_gevonden",
        "website_url": None,
        "bron": None,
    }
    start_usage_tracking()
    try:
```

En vervang, in het `with SessionLocal() as db:`-blok dat de run afsluit, de regels:

```python
            run.status = "completed"
            run.resultaat_status = outcome.status
            run.completed_at = _now()
            run.configuratie = {
```

door:

```python
            tokens_in, tokens_out = get_usage_totals()
            run.status = "completed"
            run.resultaat_status = outcome.status
            run.completed_at = _now()
            run.tokens_in = tokens_in
            run.tokens_out = tokens_out
            run.kosten_cents = bereken_kosten_cents(tokens_in, tokens_out)
            run.configuratie = {
```

- [ ] **Step 4: Run de test opnieuw om te bevestigen dat hij slaagt**

Run: `cd backend && python3 -m pytest tests/test_research_service_usage.py -v`
Expected: PASS.

- [ ] **Step 5: Run de volledige testsuite**

Run: `cd backend && python3 -m pytest tests/ -q`
Expected: alle tests PASS (260, één meer dan na Task 4).

- [ ] **Step 6: Draai het validatiescript om te bevestigen dat niets anders is geraakt**

Run: `cd backend && python3 -m scripts.validate`
Expected: coverage, MAPE en kalibratie blijven op de streefwaarden uit `CLAUDE.md` (coverage 100%, MAPE 🟢 0%, kalibratie 100%) — deze taken raken geen confidence-formule of reconciliatielogica, dus geen wijziging verwacht.

- [ ] **Step 7: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add backend/app/research/service.py backend/tests/test_research_service_usage.py
git commit -m "feat(research): tokens_in/tokens_out/kosten_cents daadwerkelijk vullen op ResearchRun"
```

---

## Na afloop

Na Task 5 zijn alle vijf werkitems uit
[2026-07-25-research-agent-efficientie-design.md](../specs/2026-07-25-research-agent-efficientie-design.md)
geïmplementeerd. Aanbevolen vervolgstap: een testbatch draaien tegen
`data/testset.csv` (zoals eerder deze sessie handmatig gedaan) om te
verifiëren dat `kosten_cents` een realistische waarde teruggeeft, en die
waarde te vergelijken met de daadwerkelijke Serper/OpenAI-facturatie om de
prijssettings in `config.py` (Task 4, Step 3) zo nodig bij te stellen.
