# Autonome Bronnenresearch-agent Implementation Plan

**Goal:** Per organisatie autonoom meerdere actuele en relevante bronnen voor
WP-informatie vinden, valideren en ranken, met aparte website-, document- en
recente-mediapaden en een verplichte human-in-the-loop beslissing.

**Architecture:** De bestaande KYC4etil FastAPI/LangGraph-app blijft leidend.
Een nieuwe research supervisor gebruikt het iteratieve patroon uit Open Deep
Research en laat gespecialiseerde onderzoekers hetzelfde
`BronKandidaat`-object produceren. Bronranking blijft gescheiden van
WP-confidence. Bestaande extractie-, identity/scope- en reviewlogica wordt
hergebruikt.

**Tech stack:** Python 3.10+, FastAPI, SQLAlchemy 2 sync-sessies volgens het
bestaande projectpatroon, LangGraph, httpx/BeautifulSoup/Playwright,
optioneel Crawl4AI achter een adapter, React, pytest.

## Global constraints

- TDD: eerst een falende test, daarna minimale implementatie.
- Bestaande `mock|live` providers blijven werken.
- Gewichten, budgetten en drempels staan in `app/config.py`.
- Externe tekst is onbetrouwbare input.
- Geen definitieve bron- of WP-acceptatie zonder reviewer.
- Verslagjaar, publicatiedatum en informatiepeilmoment blijven gescheiden.
- Bronranking en bestaande WP-confidence blijven gescheiden.
- Iedere researchfase logt naar `pipeline_runs`.
- Bestaande tests en `python -m scripts.validate` blijven slagen.
- Geen Open Deep Research-, GPT Researcher- of Crawl4AI-code kopiëren zonder
  licentie- en attributieregistratie.

---

## Fase 1 — Fundament en benchmark

### Task 1.1 — Uniform `BronKandidaat`-model

**Files**

- Modify: `backend/app/models.py`
- Modify: `backend/app/database.py`
- Test: `backend/tests/test_bronkandidaten.py`

**Modelvelden**

- identiteit: `id`, `company_id`, `research_run_id`;
- bron: `url`, `canonical_url`, `titel`, `brontype`, `documenttype`;
- tijd: `verslagjaar`, `publicatiedatum`, `informatie_peilmoment`;
- bewijs: `wp_gevonden`, `eenheid`, `bewijsfragment`, `bron_pagina`;
- classificatie: `identity_class`, `scope_class`;
- scores: autoriteit, actualiteit, identiteit, relevantie, ranking;
- metadata: `validaties`, `waarschuwingen`, `raw_data`;
- review: `status`, `rang`, `reviewed_by`, `reviewed_at`,
  `review_reason`;
- timestamps.

**Tests**

- model kan in SQLite worden aangemaakt;
- meerdere kandidaten per company zijn toegestaan;
- canonical URL is per researchrun uniek;
- JSON-validaties en waarschuwingen roundtrippen;
- verwijderen van een company verwijdert/ruimt kandidaten veilig op volgens
  het bestaande deletepad.

### Task 1.2 — `ResearchRun`-model

**Files**

- Modify: `backend/app/models.py`
- Modify: `backend/app/database.py`
- Test: `backend/tests/test_bronkandidaten.py`

**Velden**

- company/batch;
- doel en gevraagde periode;
- status en onderzoekspad;
- gebruikte configuratie/budgetten;
- start/eindtijd;
- fout en kosten/tokens;
- resultaatstatus (`gevonden|niet_gevonden|review_nodig|error`).

### Task 1.3 — Benchmarkformaat en evaluator

**Files**

- Create: `backend/data/bronnenresearch_benchmark.csv`
- Create: `backend/scripts/evaluate_bronnenresearch.py`
- Test: `backend/tests/test_bronnenresearch_evaluatie.py`

**Metrics**

- top-1 accuracy;
- top-3 recall;
- wrong-entity-at-1;
- verslagjaar/publicatiejaar accuracy;
- brondiversiteit;
- no-result accuracy;
- gemiddelde duur en, indien beschikbaar, kosten.

Begin met representatieve, reeds bekende voorbeelden uit de monitoringlijst.
Markeer nog niet handmatig geverifieerde regels expliciet als `pending_review`;
gebruik ze niet als golden truth.

---

## Fase 2 — Discovery

### Task 2.1 — Zoekproviderinterface en resultaatnormalisatie

**Files**

- Create: `backend/app/research/types.py`
- Create: `backend/app/research/search.py`
- Modify: `backend/app/providers/live.py`
- Test: `backend/tests/test_research_search.py`

**Interface**

```python
class SearchResult(TypedDict):
    title: str
    url: str
    snippet: str
    provider: str
    query: str
```

`search_all()` voert beschikbare providers uit, voegt resultaten samen en
dedupliceert. DuckDuckGo en Serper zijn geen exclusieve fallbacks meer.

### Task 2.2 — Queryplanner

**Files**

- Create: `backend/app/research/query_planner.py`
- Test: `backend/tests/test_research_query_planner.py`

Produceert deterministisch queryfamilies voor:

- officieel domein;
- documenten;
- website/WP;
- recente media;
- Nederlandse en Engelse termen;
- verslagjaar N plus publicatiejaar N+1.

Een LLM mag later aanvullende queries voorstellen, maar de basisqueries zijn
deterministisch en altijd beschikbaar.

### Task 2.3 — URL-canonicalisatie en deduplicatie

**Files**

- Create: `backend/app/research/urls.py`
- Test: `backend/tests/test_research_urls.py`

Normaliseer trackingparameters, fragmenten, host casing, redirects en
equivalente PDF-links. Bewaar zowel originele als canonieke URL.

---

## Fase 3 — Validatie en ranking

### Task 3.1 — Bronmetadata ophalen

**Files**

- Create: `backend/app/research/fetch.py`
- Test: `backend/tests/test_research_fetch.py`

Retourneert status, contenttype, final URL, titel, datumkandidaten, tekst,
PDF-metadata en fetchfout. Browserfallback staat achter een interface.

### Task 3.2 — Deterministische validatie

**Files**

- Create: `backend/app/research/validation.py`
- Reuse: `backend/app/pipeline/identity_scope.py`
- Test: `backend/tests/test_research_validation.py`

Valideert:

- organisatie/domein;
- documenttype;
- verslagjaar;
- publicatiedatum;
- bereikbaarheid;
- WP versus FTE;
- organisatorische scope;
- aanwezigheid van herleidbaar bewijs.

### Task 3.3 — Verklaarbare ranking

**Files**

- Create: `backend/app/research/ranking.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_research_ranking.py`

Pure functie zonder LLM. Geeft score, factorbreakdown, waarschuwingen en harde
afwijzing. Zorgt voor brondiversiteit in de top 3.

---

## Fase 4 — Gespecialiseerde onderzoekers

### Task 4.1 — Websiteonderzoeker

**Files**

- Create: `backend/app/research/website_researcher.py`
- Test: `backend/tests/test_website_researcher.py`

Start met bestaande fetch/Playwright-logica achter een `Crawler`-protocol.
Crawl4AI wordt pas na een aparte spike en licentiecheck als adapter toegevoegd.

### Task 4.2 — Documentonderzoeker

**Files**

- Create: `backend/app/research/document_researcher.py`
- Reuse: `LiveJaarverslagAgent.run_with_pdf`
- Test: `backend/tests/test_document_researcher.py`

Verzamelt meerdere documenten; stopt niet na het eerste document met een
getal. Houdt verslagjaar, publicatiejaar, documenttype en identity/scope apart.

### Task 4.3 — Recente-mediaonderzoeker

**Files**

- Create: `backend/app/research/media_researcher.py`
- Test: `backend/tests/test_media_researcher.py`

Gebruikt een configureerbaar actualiteitsvenster, legt publicatie- en
informatiepeilmoment vast en labelt media als aanvullend bewijs.

### Task 4.4 — Research supervisor

**Files**

- Create: `backend/app/research/supervisor.py`
- Test: `backend/tests/test_research_supervisor.py`

Implementeert:

- initiële scan;
- parallelle gespecialiseerde paden;
- evidence gap/reflection;
- maximaal aantal rondes;
- kosten-/pagina-/tijdbudget;
- top-3 selectie;
- expliciet `niet_gevonden`.

De state en routing worden gebaseerd op het Open Deep Research-patroon, maar
geïmplementeerd met eigen KYC4etil-types en domeinregels.

---

## Fase 5 — API en human review

### Task 5.1 — Research API

**Files**

- Create: `backend/app/routers/research.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_research_api.py`

Endpoints:

- `POST /research/companies/{company_id}/run`;
- `GET /research/runs/{run_id}`;
- `GET /research/companies/{company_id}/candidates`;
- `POST /research/candidates/{candidate_id}/review`;
- `POST /research/companies/{company_id}/manual-source`.

### Task 5.2 — Reviewregels

**Tests**

- alleen geauthenticeerde reviewer;
- accepteren, afwijzen en alternatief kiezen;
- maximaal één geaccepteerde primaire bron per run;
- extractiecorrectie blijft apart van bronacceptatie;
- auditvelden worden altijd gevuld;
- geen directe WPRecord-mutatie zonder bestaande reviewflow.

### Task 5.3 — Frontend

**Files**

- Create/modify: research/reviewcomponenten onder `frontend/src/`
- Modify: `frontend/src/api.js`
- Integrate: `frontend/src/views/MonitoringView.jsx`

Toon:

- researchvoortgang per pad;
- aanbevolen bron en twee alternatieven;
- bewijsfragment/pagina;
- tijdsvelden, scope en identiteit;
- scorebreakdown en waarschuwingen;
- accept/afwijs/handmatige-bronacties.

---

## Fase 6 — Kalibratie en uitrol

### Task 6.1 — Benchmark draaien

Vergelijk baseline met nieuwe agent en publiceer:

- top-1/top-3;
- foutcategorieën;
- kosten/duur;
- kleine versus grote organisaties;
- bronsoortverdeling.

### Task 6.2 — Shadow mode

Laat de nieuwe agent naast de bestaande monitoring draaien zonder bestaande
resultaten te overschrijven. Reviewers beoordelen beide uitkomsten.

### Task 6.3 — Gecontroleerde omschakeling

Omschakelen wanneer acceptatiecriteria zijn gehaald. Eerst een kleine
watchlist, daarna volledige monitoring. Rollback blijft mogelijk via
configuratie.

---

## Verificatie per task

Na iedere backendtask:

```bash
cd backend
python -m pytest <relevante-test> -q
python -m pytest tests/ -q
python -m scripts.validate
```

Na iedere frontendtask:

```bash
cd frontend
npm test -- --run
npm run build
```

Wanneer een bestaand commando niet beschikbaar is, documenteer dat en gebruik
het dichtstbijzijnde projectcommando. Geen nieuwe testtool toevoegen zonder
noodzaak.
