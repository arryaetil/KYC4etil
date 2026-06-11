# Handoff voor Claude Code

Project: Vestigingsregister AI Platform voor Etil Research Group / Provincie Limburg.

Deze notitie beschrijft wat er tot nu toe is gebouwd, hoe het systeem draait, wat al gevalideerd is en waar je moet opletten als je verdergaat.

## Korte status

- Backend is functioneel in mock- en live-modus.
- Auth is actief op bestaande `users`-tabel met JWT.
- Review-frontend is gebouwd in React + Vite + Tailwind.
- Background processing voor batches draait asynchroon.
- Railway-deploy staat op voor backend en frontend.
- Live fallback voor OpenAI web search is gefixt na een API-conflict met JSON-mode.

## Wat is gebouwd

### 1. Auth backend

- JWT-login op `users`.
- Endpoints:
  - `POST /auth/login`
  - `GET /auth/me`
- Seed-script voor demo-users:
  - `Armina`
  - `Anita`
  - `admin`
- Beveiliging:
  - alle bestaande endpoints zijn afgeschermd behalve `/health`.
- Review-actie-audit:
  - `goedgekeurd_door` wordt gevuld vanuit de ingelogde gebruiker bij approve/correct.

Belangrijk bestand:
- [`backend/app/auth.py`](../backend/app/auth.py)
- [`backend/app/routers/auth.py`](../backend/app/routers/auth.py)
- [`backend/scripts/seed_users.py`](../backend/scripts/seed_users.py)

### 2. Achtergrondverwerking

- `POST /batches/{id}/run` start een achtergrondtaak.
- De frontend kan voortgang pollen via `GET /batches/{id}`.
- `verwerkt` en `totaal` zijn al aanwezig.

Belangrijk bestand:
- [`backend/app/routers/batches.py`](../backend/app/routers/batches.py)
- [`backend/app/pipeline/runner.py`](../backend/app/pipeline/runner.py)

### 3. Review-interface frontend

React + Vite + Tailwind in één SPA.

Schermen:
- login
- dashboard met batches, voortgang, telling groen/geel/rood, upload en run
- batchoverzicht met filter op label/strategie
- detailpagina met vestigingsgegevens, context, bronlink, score_breakdown, reconciliatie_reden en review-acties
- bulk-acties voor groen goedkeuren en exports

Belangrijk bestand:
- [`frontend/src/App.jsx`](../frontend/src/App.jsx)
- [`frontend/src/api.js`](../frontend/src/api.js)
- [`frontend/src/main.jsx`](../frontend/src/main.jsx)

### 4. Railway-deploy

- `backend/railway.toml` voor FastAPI/uvicorn met `/health`
- `frontend/railway.toml` voor statische build
- CORS op backend is beperkt via `FRONTEND_ORIGIN`
- PostgreSQL via `DATABASE_URL`

Belangrijke bestanden:
- [`backend/railway.toml`](../backend/railway.toml)
- [`frontend/railway.toml`](../frontend/railway.toml)
- [`backend/app/main.py`](../backend/app/main.py)

## Live provider-gedrag

De live provider gebruikt dit gedrag:

- Als `GOOGLE_PLACES_API_KEY` aanwezig en werkend is:
  - Places voor website, telefoon en locatiecount.
- Als Google ontbreekt of faalt:
  - fallback naar OpenAI web search voor website/telefoon.
- Voor web search wordt geen JSON-mode gebruikt; dat gaf eerder een 400-error.
- `scripts.validate` hoort in `PROVIDER_MODE=mock` te draaien, niet in live-modus.

Belangrijk bestand:
- [`backend/app/providers/live.py`](../backend/app/providers/live.py)

## Validatie

Laatste bekende groene runs:

```bash
cd backend
python -m pytest tests/ -q
```

```bash
cd backend
$env:PYTHONIOENCODING='utf-8'
$env:PROVIDER_MODE='mock'
python -m scripts.validate
```

Resultaat op de testset:
- coverage: 100%
- MAPE op groene records: 0%
- kalibratie: 100%

Opmerking:
- `scripts.validate` in live-modus kan lang duren of vastlopen door echte web/LLM-calls. Gebruik mock-modus voor de vereiste validatie.

## Deploy-status

Railway services:
- frontend: live
- backend: live
- postgres: live

Bekende URLs:
- frontend: `https://frontend-production-3080.up.railway.app`
- backend: `https://backend-production-60fbc.up.railway.app`

Healthcheck:
- `GET /health` geeft `ok` terug in live-modus.

## Relevante commits

- `086497c` Fix OpenAI web search fallback
- `99d2e45` Add OpenAI web search contact fallback
- `70b675b` Use OpenAI for live extraction
- `c346e99` Serve frontend static build on Railway
- `016da8e` Fix Railway deployment dependencies
- `1db36c7` Add Railway deployment config
- `cb3edc5` Add review frontend
- `9dfe224` Run batches in background
- `68b5930` Add JWT authentication

## Domeinregels die blijven gelden

- Schatting mag nooit groen zijn.
- FTE is niet hetzelfde als WP.
- Chat-antwoorden gaan altijd via review, nooit direct naar het register.
- Gewichten en drempels horen in `app/config.py`, niet hardcoded in pipeline-code.
- LLM-prompts moeten de prompt-injection-clausule behouden.

Bron van waarheid voor de inhoudelijke domeinregels:
- [`CLAUDE.md`](../CLAUDE.md)
- [`docs/PLATFORM_DOCUMENTATIE_v2.md`](./PLATFORM_DOCUMENTATIE_v2.md)

## Open punten die nog bewust open staan

- KvK API-toegang voor exacte locatiecount
- exacte peildatum van het register
- validatie van de Zuyderland ground truth
- eventuele vervolgstap voor chat-module / reconciliatie-uitbreiding

## Hoe verder werken

1. Lees eerst [`CLAUDE.md`](../CLAUDE.md) en [`docs/PLATFORM_DOCUMENTATIE_v2.md`](./PLATFORM_DOCUMENTATIE_v2.md).
2. Voor backend-wijzigingen:
   - draai `python -m pytest tests/ -q`
   - draai `python -m scripts.validate` in `PROVIDER_MODE=mock`
3. Voor frontend-wijzigingen:
   - draai `npm run build` in `frontend/`
4. Deploy backend eerst als je provider- of auth-logica wijzigt.
5. Gebruik Railway env-vars expliciet, vooral:
   - `PROVIDER_MODE`
   - `DATABASE_URL`
   - `JWT_SECRET`
   - `FRONTEND_ORIGIN`
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `GOOGLE_PLACES_API_KEY`

## Praktische demo-flow

1. Log in met `armina@etil.nl` of `anita@etil.nl`.
2. Upload `backend/data/testset.csv`.
3. Start de batch-run.
4. Poll de voortgang.
5. Open batchdetail voor score-uitleg.
6. Gebruik bulk-goedkeuren voor groene records.
7. Exporteer CSV of bellijst.

