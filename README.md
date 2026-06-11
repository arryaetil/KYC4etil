# Vestigingsregister AI Platform

AI-pipeline voor het verzamelen van Werkzame Personen-data (WP) voor het Vestigingsregister van Provincie Limburg.

- Documentatie: [docs/PLATFORM_DOCUMENTATIE_v2.md](docs/PLATFORM_DOCUMENTATIE_v2.md)
- Status: backend pipeline + auth + React review-interface, werkend in mock-modus.

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

Demo-accounts:

- `armina@etil.nl` / `ArminaDemo2026!`
- `anita@etil.nl` / `AnitaDemo2026!`
- `admin@etil.nl` / `AdminDemo2026!`

## Demo-flow

Gebruik de review-interface voor de normale demo: login, CSV uploaden, run starten, voortgang volgen, records reviewen en exports downloaden.

Via API:

```bash
# Login eerst en gebruik de Bearer token voor alle endpoints behalve /health.
curl -X POST localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=armina@etil.nl&password=ArminaDemo2026!"

# Testset uploaden
curl -F "file=@data/testset.csv" "localhost:8000/batches/upload?naam=demo&jaar=2026"

# Pipeline starten als achtergrondtaak
curl -X POST localhost:8000/batches/{batch_id}/run

# Voortgang pollen: verwerkt/totaal + labels
curl localhost:8000/batches/{batch_id}

# Bulk-goedkeuren en exports
curl -X POST localhost:8000/batches/{batch_id}/approve-all-green
curl localhost:8000/batches/{batch_id}/export.csv
curl localhost:8000/batches/{batch_id}/bellijst.csv
```

## Validatie & Tests

```bash
cd backend
python -m pytest tests/ -q
python -m scripts.validate
```

Streefwaarden in mock-modus op de testset: coverage 100%, MAPE groen 0%, kalibratie 100%.

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
    routers/
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
GOOGLE_PLACES_API_KEY=
KVK_API_KEY=
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

## Live-modus

`PROVIDER_MODE=live` vereist minimaal `OPENAI_API_KEY` en `GOOGLE_PLACES_API_KEY`. KvK kan worden ingeplugd zodra toegang beschikbaar is. Volgens de open punten in de documentatie moeten KvK-toegang, register-peildatum en Zuyderland ground truth nog door Arrya/Roger/Armina bevestigd worden voordat daar productie-aannames op worden gebaseerd.
