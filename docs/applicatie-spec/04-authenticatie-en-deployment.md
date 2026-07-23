# Authenticatie en deployment

## Authenticatie

JWT-based, geen server-side sessions.

- Wachtwoorden worden gehasht met `passlib` + `bcrypt` (`backend/app/auth.py`).
- Login: `POST /auth/login` (form-based) → geeft een `access_token` (JWT, HS256,
  ondertekend met `settings.jwt_secret`, 12 uur geldig) plus het gebruikersobject terug.
  De token bevat `sub` (user-id), `email` en `rol`.
- Elke request met een `Authorization: Bearer <token>`-header wordt gedecodeerd door
  `get_current_user`; ongeldige/verlopen tokens geven een 401.
- `GET /auth/me` — huidige ingelogde gebruiker ophalen (voor de frontend om na een
  refresh te weten wie er is ingelogd).
- Eén `User`-model, geen apart admin-model — de rol (`"reviewer"` is de default) is een
  gewoon stringveld. De publieke chatflow (`chat.py`) gebruikt een apart, token-based
  mechanisme (geen login) specifiek voor de externe respondent van een chat-sessie.

## Provider-modus: mock vs. live

`PROVIDER_MODE` (environment-variabele, default `"mock"`) bepaalt welke implementatie van
elke externe afhankelijkheid wordt gebruikt — locatie-lookup, website-agent,
jaarverslag-agent, identity/scope-classifier. Elke afhankelijkheid zit achter een
`Protocol`-interface (`backend/app/providers/base.py`) met een `Mock*`- en een
`Live*`-implementatie; `get_providers()` (`backend/app/providers/__init__.py`) kiest op
basis van `PROVIDER_MODE` welke vier providers teruggegeven worden.

- **Mock-modus**: volledig deterministisch, geen enkel netwerkverkeer. Gebruikt voor de
  20 testbedrijven in `data/testset.csv`, en voor de hele testsuite
  (`pytest tests/ -q`, 190 tests) en het validatiescript
  (`python -m scripts.validate`, dat coverage/MAPE/kalibratie tegen streefwaarden zet).
  Omdat de mock-classifier bijvoorbeeld geen API-calls doet, blijft
  `scripts.validate` reproduceerbaar tussen runs.
- **Live-modus**: roept de echte diensten aan (OpenAI, Serper, Google Places, crawl4ai).

## Deployment (Railway)

Twee losse Railway-services binnen hetzelfde project (`kyc-vestigingsregister`), plus een
Postgres-database:

- **backend** (`backend/railway.toml`): buildCommand installeert de Python-dependencies
  en draait `crawl4ai-setup` (voor de Playwright/Chromium-browserinstallatie); start
  `uvicorn app.main:app`; healthcheck op `/health`.
- **frontend** (`frontend/railway.toml`): `npm run build` (Vite), geserveerd als
  statische build.

Lokaal draait de database op SQLite (lege `DATABASE_URL`); op Railway is dat PostgreSQL.
Kolomwijzigingen lopen via het lichtgewicht migratiemechanisme in
`backend/app/database.py`, niet via Alembic.

**Deploy-geschiedenis, kort:** de belangrijkste terugkerende bron van deploy-issues was
het correct krijgen van Playwright's Chromium-binary op Railway (env-var
`PLAYWRIGHT_BROWSERS_PATH=0` om de browser in de virtualenv te laten installeren i.p.v.
een aparte custom build-stap) — dit is inmiddels stabiel opgelost en bevestigd via de
`/health`-endpoint na elke deploy.

## Wat nog niet geverifieerd is

- De daadwerkelijke visuele werking van de bronnen-first-UI (bronnenkaarten,
  zekerheidsbadge, PDF-modal) in een echte browser tegen echte reviewersdata is nog niet
  handmatig doorlopen.
- Of jaarverslag-PDF's van externe hosts daadwerkelijk laden in de PDF-modal (afhankelijk
  van of die hosts CORS-headers meesturen) is architectuur-technisch een open vraag, geen
  bevestigd werkend gedrag.
- Er bestaat nog geen daadwerkelijk gemeten kostendata per batch/company — alleen de
  ruwe schatting uit de documentatie (zie
  [01-pipeline-en-agents.md](01-pipeline-en-agents.md)).
