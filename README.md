# Vestigingsregister AI Platform

AI-pipeline en human-in-the-loop researchomgeving voor het verzamelen en
controleren van Werkzame Personen-data (WP) voor het Vestigingsregister van
Provincie Limburg.

- Huidige werking (bron van waarheid): [docs/applicatie-spec/](docs/applicatie-spec/00-overzicht.md) — architectuur, pipeline + LangGraph-agents, externe diensten & kosten, datamodel, confidence-/reconciliatieregels, bronnen-first review-UI, authenticatie & deployment.
- Autonome bronnenresearch: [ontwerp](docs/archief/superpowers/specs/2026-07-24-autonome-bronnenresearch-agent-design.md)
  en [implementatieplan](docs/archief/superpowers/plans/2026-07-24-autonome-bronnenresearch-agent.md).
- Status: backend pipeline, autonome bronontdekking, auth en React review-interface.

## Autonome bronnenresearch

De research-agent zoekt niet uitsluitend naar jaarverslagen. Per organisatie
onderzoekt hij drie bronfamilies:

1. de officiële website, onder meer organisatie-, team- en contactpagina's;
2. openbare documenten, zoals jaarverslagen, jaarrekeningen en bestuursverslagen;
3. recente media en onafhankelijke openbare bronnen.

De agent maakt meerdere zoekqueries, combineert resultaten van beschikbare
zoekproviders, verwijdert dubbele URL's en inspecteert de gevonden pagina's.
DuckDuckGo en Serper zijn de goedkope primaire zoeklaag. Als beide voor een
onderzoekspad leeg blijven, gebruikt de agent OpenAI hosted web search als
begrensde fallback: maximaal één call voor de officiële domeinresolutie en één
call per bronfamilie (dus maximaal vier per organisatie).
Vóór ranking beoordeelt een fail-closed bronreviewer iedere kandidaat op basis
van de daadwerkelijke pagina- of documentinhoud. Zoekresultaatsnippets tellen
niet als identiteitsbewijs. Evidente mismatches en sociale profielen worden
deterministisch verwijderd; plausibele niet-officiële bronnen krijgen een
gestructureerde LLM-review. Vervolgens rangschikt de agent alleen goedgekeurde
of expliciet als context gemarkeerde kandidaten op:

- juiste organisatie-identiteit;
- autoriteit van de bron;
- relevantie voor WP;
- actualiteit en gevraagd verslagjaar;
- aanwezigheid van controleerbaar bewijs.

De review legt beslissing, gevonden organisatie, identity class, scope en reden
vast in de auditdata. `possible_match`, `unknown` en `mismatch` gaan nooit naar
de menselijke top-3.

De hoogst gerangschikte drie kandidaten gaan naar een reviewer. De reviewer
accepteert één primaire bron, wijst kandidaten af of voegt handmatig een bron
toe. Een agentresultaat wordt dus nooit automatisch als definitieve registerbron
gebruikt.

Autonome bronnenresearch is ook de standaard batchworkflow. De batchpagina toont
per organisatie de voorgestelde bron, het bruikbare research-WP, het oude
pipeline-WP en de vergelijking. Een landelijk of concerncijfer blijft zichtbaar
als broncontext, maar wordt niet als vestigings-WP aangeboden. De oude pipeline
blijft apart beschikbaar voor gecontroleerde vergelijkingen.

Belangrijke code:

```text
backend/app/research/              discovery, validatie, ranking en supervisor
backend/app/routers/research.py    research- en review-API
frontend/src/components/ResearchPanel.jsx
backend/data/bronnenresearch_benchmark.csv
backend/scripts/evaluate_bronnenresearch.py
```

## Snel Starten

Backend:

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed_users
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Lokale URLs:

- API: `http://127.0.0.1:8000`
- API-docs: `http://127.0.0.1:8000/docs`
- Review-interface: `http://127.0.0.1:5173`

Demo-accounts worden aangemaakt met `python -m scripts.seed_users`. De command print de actuele wachtwoorden. Wil je vaste lokale demo-wachtwoorden, zet dan eerst `DEMO_ARMINA_PASSWORD`, `DEMO_ANITA_PASSWORD` en `DEMO_ADMIN_PASSWORD` in `backend/.env`.

Standaard e-mails:

- `armina@etil.nl`
- `anita@etil.nl`
- `admin@etil.nl`

## Demo-flow

Gebruik de review-interface voor de normale demo: login, CSV uploaden, run starten, voortgang volgen, records reviewen en exports downloaden.

Voor brononderzoek open je **Bronnenmonitoring**, filter je eventueel op
**Actie nodig** en kies je bij een organisatie **Brononderzoek**. Selecteer het
gewenste verslagjaar, start de agent en beoordeel daarna de voorgestelde
bronnen. Voor kleine organisaties zonder jaarverslag kan een officiële
websitepagina of recente openbare bron de juiste kandidaat zijn.

Via API:

```bash
# Login eerst en gebruik de Bearer token voor alle endpoints behalve /health.
curl -X POST localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=armina@etil.nl&password=<wachtwoord-uit-seed-output>"

# Testset uploaden
curl -F "file=@data/testset.csv" "localhost:8000/batches/upload?naam=demo&jaar=2026"

# Standaard: autonome bronnenresearch als achtergrondtaak
curl -X POST localhost:8000/batches/{batch_id}/run

# Alleen voor interne vergelijking: oude WP-pipeline
curl -X POST localhost:8000/batches/{batch_id}/run-legacy

# Voortgang pollen: verwerkt/totaal + research- en reviewstatussen
curl localhost:8000/batches/{batch_id}

# Bulk-goedkeuren en exports
curl -X POST localhost:8000/batches/{batch_id}/approve-all-green
curl localhost:8000/batches/{batch_id}/export.csv
curl localhost:8000/batches/{batch_id}/bellijst.csv
```

Research-API, eveneens met Bearer-token:

```bash
# Start een autonome researchrun
curl -X POST localhost:8000/research/companies/{company_id}/run \
  -H "Content-Type: application/json" \
  -d '{"gevraagd_jaar": 2025}'

# Poll runstatus en top-3
curl localhost:8000/research/runs/{run_id}

# Accepteer of wijs een kandidaat af
curl -X POST localhost:8000/research/candidates/{candidate_id}/review \
  -H "Content-Type: application/json" \
  -d '{"beslissing": "accepteren", "reden": "juiste organisatie en periode"}'
```

## Validatie & Tests

```bash
cd backend
python -m pytest tests/ -q
python -m scripts.validate
python -m scripts.evaluate_bronnenresearch --predictions data/research_predictions.json
python -m scripts.compare_research_workflows
```

De bronbenchmark telt alleen rijen met status `verified` mee. Nieuwe
benchmarkcases blijven `pending_review` totdat een menselijke reviewer de
verwachte bron heeft bevestigd.

Frontend:

```bash
cd frontend
npm run build
```

## Structuur

```text
backend/
  app/
    config.py
    models.py
    providers/
    pipeline/
    research/
    routers/
      research.py
  data/bronnenresearch_benchmark.csv
  data/testset.csv
  data/mock_data.json
  scripts/
  tests/
  railway.toml
frontend/
  src/
  package.json
  railway.toml
```

## Railway Deploy

Maak twee Railway services aan vanuit dezelfde repository.

Backend service:

- Root directory: `backend/`
- PostgreSQL: koppel een Railway PostgreSQL database
- Start/healthcheck: geregeld door `backend/railway.toml`

Backend env-vars:

```env
PROVIDER_MODE=mock
DATABASE_URL=${{Postgres.DATABASE_URL}}
JWT_SECRET=<lange-random-secret>
FRONTEND_ORIGIN=https://<frontend-service>.up.railway.app
REGISTER_PEILDATUM=2026-04-01
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.2
SERPER_API_KEY=
GOOGLE_PLACES_API_KEY=
KVK_API_KEY=
RESEARCH_MEDIA_VENSTER_MAANDEN=18
RESEARCH_MAX_QUERIES=12
RESEARCH_MAX_PAGES=30
RESEARCH_MAX_ROUNDS=3
```

Frontend service:

- Root directory: `frontend/`
- Static Vite build: geregeld door `frontend/railway.toml`

Frontend env-vars:

```env
VITE_API_URL=https://<backend-service>.up.railway.app
```

Na deploy:

1. Run een eenmalig backend shell command: `python -m scripts.seed_users`.
2. Controleer `https://<backend-service>.up.railway.app/health`.
3. Log in op de frontend met Armina of Anita.
4. Upload `backend/data/testset.csv` en start de batch.
5. Open Bronnenmonitoring en voer voor enkele organisaties een shadow run uit.

## Live-modus

`PROVIDER_MODE=live` vereist minimaal `OPENAI_API_KEY`. `SERPER_API_KEY` is
optioneel en geeft de research-agent een tweede zoekprovider naast DuckDuckGo.
Beschikbare providers worden parallel bevraagd en op canonieke URL
samengevoegd. Als beide indexen leeg zijn, gebruikt de agent
`OPENAI_WEB_SEARCH_MODEL` (standaard `gpt-4.1-mini`) als hosted zoekfallback.
Met `GOOGLE_PLACES_API_KEY` gebruikt de backend Places voor website, telefoon en
fuzzy locatiecount. Wanneer Places geen website oplevert, probeert de backend
eerst klassieke websearch en daarna dezelfde OpenAI-fallback; locatiecount kan
dan onbekend blijven en records krijgen daardoor lagere confidence.

De huidige research-agent is een eerste productiegerichte verticale slice.
Voor brede productie-uitrol moeten eerst 20–50 echte organisaties in shadow
mode worden beoordeeld. Daarna kunnen rankinggewichten, zoekbudgetten en
eventuele extra crawleradapters op basis van gemeten top-3-accuracy worden
gekalibreerd.
