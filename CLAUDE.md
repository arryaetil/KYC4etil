# Vestigingsregister AI Platform — projectcontext

AI-pipeline die WP-data (Werkzame Personen) verzamelt voor het Vestigingsregister van Provincie Limburg (Etil Research Group). Gebruikers: Armina en Anita (reviewers), Roger Vaessens (PO).

**Lees eerst `docs/PLATFORM_DOCUMENTATIE_v2.md`** — dit is de bron van waarheid voor architectuur, datamodel, confidence-formule (§9), reconciliatieregels (§7) en fasering (§14).

## Huidige staat (Fase 1 af)

- `backend/` — FastAPI-pipeline, werkend in mock-modus: verrijking → website/jaarverslag-agents → reconciliatie → confidence scoring → review-endpoints → CSV-export + bellijst.
- Provider-pattern: `PROVIDER_MODE=mock|live` (`app/providers/`). Mock is deterministisch voor de 20 testbedrijven in `data/testset.csv`.
- 17 unit tests (`pytest tests/ -q`) en validatiescript (`python -m scripts.validate`): coverage 100%, MAPE 🟢 0%, kalibratie 100%.
- SQLite lokaal (DATABASE_URL leeg), PostgreSQL op Railway.

## Conventies

- Python 3.10+-compatibel, SQLAlchemy 2 (Mapped/mapped_column), async pipeline.
- Domeintaal Nederlands (wp_kandidaat, bellijst, goedgekeurd_door) — consistent houden.
- Gewichten/drempels in `app/config.py`, nooit hardcoden in pipeline-code.
- Mock én live providers achter dezelfde Protocol-interfaces; nieuwe externe afhankelijkheden ook.
- Elke pipeline-stap logt naar `pipeline_runs`.
- LLM-prompts bevatten altijd de prompt-injection-clausule (externe tekst = onbetrouwbare input).
- Bij wijzigingen: tests draaien én `python -m scripts.validate` moet op streefwaarden blijven.

## Belangrijke domeinregels

- Een proportionele schatting (`is_schatting=True`) mag NOOIT label 🟢 krijgen.
- LLM-zekerheid kan een confidence-score alleen begrenzen (cap), nooit verhogen.
- `count_lb == count_nl` (alles in Limburg) telt als locatie-eenduidig.
- Chat-antwoorden gaan altijd via de review-wachtrij, nooit direct het register in.
- FTE ≠ WP: nooit stilzwijgend omrekenen.

## Openstaand (niet zelf oplossen, vragen aan Arrya)

- KvK API-key (kritieke afhankelijkheid voor locatiecount)
- Peildatum register (REGISTER_PEILDATUM staat op aanname 2026-04-01)
- Zuyderland ground truth (10.444 is placeholder, verifiëren)
