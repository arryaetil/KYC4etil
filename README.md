# Vestigingsregister AI Platform

AI-pipeline voor het verzamelen van Werkzame Personen-data (WP) voor het Vestigingsregister — Etil Research Group / Provincie Limburg.

- **Documentatie:** [`docs/PLATFORM_DOCUMENTATIE_v2.md`](docs/PLATFORM_DOCUMENTATIE_v2.md) (v2.0, vervangt v1.0)
- **Status:** Fase 1 (pipeline backend) — werkend in mock-modus, gevalideerd op de testset van 20 bedrijven

## Snel starten

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env                 # PROVIDER_MODE=mock werkt zonder keys
uvicorn app.main:app --reload        # API op http://localhost:8000/docs
```

## Demo-flow (via API of /docs)

```bash
# 1. Testset uploaden
curl -F "file=@data/testset.csv" "localhost:8000/batches/upload?naam=demo&jaar=2026"
# 2. Pipeline draaien (verrijking -> agents -> reconciliatie -> confidence)
curl -X POST localhost:8000/batches/{batch_id}/run
# 3. Resultaten: 15x groen (auto), 2x geel (gerichte chat), 3x rood (bellijst)
curl localhost:8000/batches/{batch_id}
# 4. Bulk-goedkeuren van groene records + exports
curl -X POST localhost:8000/batches/{batch_id}/approve-all-green
curl localhost:8000/batches/{batch_id}/export.csv
curl localhost:8000/batches/{batch_id}/bellijst.csv
```

## Validatie & tests

```bash
cd backend
python -m pytest tests/ -q          # 17 unit tests (strategie, schatting, reconciliatie, confidence)
python -m scripts.validate          # metrics tegen ground truth: coverage 100%, MAPE groen 0%, kalibratie 100%
```

De kalibratie doet wat hij moet: single-locatie bedrijven worden 🟢, CB-ers met alleen een nationaal totaal (NS, DSM, BAM) worden terecht 🔴 — hun proportionele schattingen zitten er 200–500% naast en gaan naar de bellijst i.p.v. het register.

## Structuur

```
backend/
├── app/
│   ├── config.py            # gewichten & drempels (kalibratie zonder code-wijziging)
│   ├── models.py            # gecorrigeerd datamodel (doc §6)
│   ├── providers/           # mock & live achter dezelfde interfaces (doc §5)
│   ├── pipeline/            # confidence (§9), reconciliatie (§7), runner
│   └── routers/             # batches, review, exports
├── data/testset.csv         # 20 testbedrijven (LET OP: Zuyderland-waarde verifiëren)
├── data/mock_data.json      # deterministische mock-responses
├── scripts/validate.py      # validatiemetrics
└── tests/
```

## Live-modus

`PROVIDER_MODE=live` + `ANTHROPIC_API_KEY` en `GOOGLE_PLACES_API_KEY` in `.env`. Website agent en Places-verrijking zijn live geïmplementeerd; jaarverslag-PDF-discovery vergt nog een search-API-keuze (zie doc §7) — `run_with_pdf()` werkt al met een aangeleverde PDF-URL. KvK API inpluggen zodra toegang er is (kritieke afhankelijkheid, doc §3).

## Volgende stappen

1. Zuyderland ground truth + kanaalcijfers verifiëren bij Armina (doc §16, vraag 9)
2. KvK API-toegang regelen (vraag 1) · peildatum bevestigen met Roger (vraag 2)
3. Search-API kiezen voor jaarverslag-discovery, live-run op subset
4. Fase 2: React review-interface · daarna Railway-deploy
