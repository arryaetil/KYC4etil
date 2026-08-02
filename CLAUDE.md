# Vestigingsregister AI Platform — projectcontext

AI-pipeline die WP-data (Werkzame Personen) verzamelt voor het Vestigingsregister van Provincie Limburg (Etil Research Group). Gebruikers: Armina en Anita (reviewers), Roger Vaessens (PO).

**Lees eerst `docs/applicatie-spec/00-overzicht.md`** — dit is de bron van waarheid voor architectuur, datamodel, scoring en review-UI. `docs/PLATFORM_DOCUMENTATIE_v2.md` is de oorspronkelijke opzet uit juni 2026 en is sindsdien niet bijgewerkt: raadpleeg het als achtergrond bij de §-verwijzingen in oudere code-commentaren, niet als beschrijving van de huidige staat.

## Huidige staat

Het systeem draait live op Railway (aparte frontend- en backend-service, PostgreSQL) met OpenAI, Google Places, Serper/DuckDuckGo, Playwright en Resend als externe afhankelijkheden.

Er lopen **twee generaties naast elkaar**; generatie 2 is de richting, generatie 1 wordt uitgefaseerd:

- **Generatie 2 — `backend/app/research/` (de onderzoekswerkbank).** Bronnenresearch per organisatie → `BronKandidaat` → verklaarbare bronranking (`research/ranking.py`, vier dimensies incl. actualiteit) → reviewbeslissing. Dit is waar de frontend op draait (`OnderzoekView`, `MonitoringView`).
- **Generatie 1 — `backend/app/pipeline/` (de batch-pipeline).** verrijking → website/jaarverslag-agents → reconciliatie → confidence scoring → `Candidate`. Draait nog, maar de bijbehorende UI is per 2026-07-26 verwijderd. Nieuwe functionaliteit hoort in generatie 2.
- `pipeline/monitoring.py` schrijft naar beide en is daarmee de brug tussen de generaties.

Provider-pattern: `PROVIDER_MODE=mock|live` (`app/providers/`). Mock is deterministisch voor de 20 testbedrijven in `data/testset.csv`. SQLite lokaal (DATABASE_URL leeg), PostgreSQL op Railway.

### Bewust inactief — niet verwijderen, niet "repareren"

De scope is batchonderzoek plus de jaarverslag-agent. Deze onderdelen zijn met de
frontend-rewrite van 2026-07-26 uit gebruik genomen. De code blijft staan; de endpoints
zijn bereikbaar via de API maar geen enkel scherm roept ze aan. Dat is een keuze, geen bug:

- **Chatuitnodiging aan contactpersonen** — `routers/chat.py`, `routers/chat_admin.py`,
  `chat_service.py`, `email.py`, `POST /candidates/{id}/create-chat` in `routers/review.py`.
  `create-chat` is de enige plek die een `ChatSession` aanmaakt; zonder aanroeper worden er
  dus geen chatsessies meer gemaakt.
- **Bellijst** — de `bellijst`-endpoints in `routers/review.py`. `pipeline/runner.py` schrijft
  nog wel `CallListItem`-regels bij een laag label; die worden nergens meer getoond.
- **Handmatige jaarverslag-upload en -chat** — `routers/jaarverslagen.py`. Let op: dit is iets
  anders dan de jaarverslag-*agent* in `providers/live.py`, die wél actief is en automatisch
  jaarverslagen zoekt en uitleest.
- **WP-review op `Candidate`** — approve/correct/approve-all-green in `routers/review.py`.
  De review loopt nu via `BronKandidaat` in `routers/research.py`.

Gevolg om rekening mee te houden: `pipeline/reconcile.py` kent nog steeds de strategieën
`gerichte_chat` en `volledige_chat_of_bellijst` toe. Die labels verwijzen naar acties die
niemand meer uitvoert — ze betekenen in de praktijk "niet automatisch doorvoeren".

## Testen

- Backend: `cd backend && .venv/bin/python -m pytest -q` — 349 tests.
- Frontend: `cd frontend && npx vitest run` — 51 tests.
- Validatie: `cd backend && .venv/bin/python -m scripts.validate` — streefwaarden coverage ≥70%, MAPE 🟢 ≤10%, kalibratie ≥80%. Staat nu op 100% / 0,0% / 100%.

## Conventies

- Python 3.10+-compatibel, SQLAlchemy 2 (Mapped/mapped_column), async pipeline.
- Domeintaal Nederlands (wp_kandidaat, bellijst, goedgekeurd_door) — consistent houden.
- Gewichten/drempels in `app/config.py`, nooit hardcoden in pipeline-code.
- Mock én live providers achter dezelfde Protocol-interfaces; nieuwe externe afhankelijkheden ook.
- Elke pipeline-stap logt naar `pipeline_runs`, inclusief tokens per stap; de afsluitende regel `stap="totaal"` draagt de kosten van de hele organisatie.
- LLM-prompts bevatten altijd de prompt-injection-clausule (externe tekst = onbetrouwbare input).
- Bij wijzigingen: tests draaien én `scripts.validate` moet op streefwaarden blijven.
- Eén berekening per begrip. Als er al een helper is (`evidence._parse_year`, `usage.get_cost_summary`), hergebruik die; een tweede variant ernaast levert stilzwijgend afwijkende uitkomsten op.

## Belangrijke domeinregels

- Een proportionele schatting (`is_schatting=True`) mag NOOIT label 🟢 krijgen.
- LLM-zekerheid kan een confidence-score alleen begrenzen (cap), nooit verhogen.
- `count_lb == count_nl` (alles in Limburg) telt als locatie-eenduidig.
- Chat-antwoorden gaan altijd via de review-wachtrij, nooit direct het register in.
- FTE ≠ WP: nooit stilzwijgend omrekenen.
- Actualiteit telt mee: een WP-cijfer waarvan het peilmoment meer dan `peilmoment_max_leeftijd_jaren` (1) vóór het peiljaar ligt, krijgt een penalty. Eén jaar verschil is normaal — een jaarverslag over jaar X verschijnt pas in X+1. Een onbekend peilmoment is géén reden voor een penalty.

## Skills

Invoke the task-observer skill at the start of every task-oriented session.

## Openstaand (niet zelf oplossen, vragen aan Arrya)

- KvK API-key (kritieke afhankelijkheid voor locatiecount)
- `register_peildatum` (staat op 2026-04-01) wordt nergens uitgelezen. De confidence gebruikt `batch.jaar` als peiljaar. Besluiten of de peildatum een eigen rol moet krijgen of weg kan.
- Zuyderland ground truth (10.444 is placeholder, verifiëren)
- `pipeline/runner.py` blijft `CallListItem`-regels wegschrijven voor een bellijst die niemand meer bekijkt. Besluiten of dat zo mag blijven (onschadelijk) of dat het weg kan.
- `requirements.txt` pint geen versies (`>=`). FastAPI liep daardoor lokaal naar 0.141 met gewijzigd `include_router`-gedrag. Overwegen om te pinnen.
