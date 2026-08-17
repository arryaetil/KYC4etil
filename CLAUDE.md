# KYC4etil Bronnenwerkbank — projectcontext

Werkbank die openbare bronnen over Werkzame Personen (WP) vindt, ordent en laat beoordelen voor Etil Research Group. Het product beheert geen register en neemt geen registerbeslissingen.

**Lees eerst `docs/applicatie-spec/00-overzicht.md`** — dit is de bron van waarheid voor architectuur, datamodel, scoring en review-UI. `docs/PLATFORM_DOCUMENTATIE_v2.md` is de oorspronkelijke opzet uit juni 2026 en is sindsdien niet bijgewerkt: raadpleeg het als achtergrond bij de §-verwijzingen in oudere code-commentaren, niet als beschrijving van de huidige staat.

## Actieve architectuur

Het systeem draait live op Railway (aparte frontend- en backend-service, PostgreSQL) met OpenAI, Google Places, Serper/DuckDuckGo, Playwright en Resend als externe afhankelijkheden.

Er is één actieve gegevensstroom:

- `User → Batch → Company → ResearchRun → BronKandidaat → reviewbeslissing`.
- `backend/app/research/` bevat het brononderzoek, validatie en ranking.
- `OnderzoekView` en `MonitoringView` zijn de enige actieve productmodules.
- Monitoring schrijft nieuwe vondsten uitsluitend naar `ResearchRun` en `BronKandidaat`.
- Een acceptatie krijgt `juiste_bron_bruikbaar_bewijs`; een afwijzing vereist een vaste `review_reason_code`, met optionele toelichting.

Provider-pattern: `PROVIDER_MODE=mock|live` (`app/providers/`). Mock is deterministisch voor de 20 testbedrijven in `data/testset.csv`. SQLite lokaal (DATABASE_URL leeg), PostgreSQL op Railway.

### Historische compatibiliteit

De oude database-tabellen (`candidates`, `agent_results`, `wp_records`, chat en
bellijst) worden in deze fase niet verwijderd. Ze kunnen bestaande productiedata
bevatten en worden pas na back-up en een observatieperiode gedropt. Ze zijn geen
onderdeel van de actieve API of schrijfstroom.

De volledige chatimplementatie van vóór deze overgang is lokaal bewaard op Git-tag
`archive/chat-workflow-v1` en branch `archive/chat-workflow`. De oude routers zijn
niet meer geregistreerd en de publieke chatroute is uit de frontend gehaald.

## Testen

- Backend: `python3 -m pytest -q backend/tests`. De testsuite forceert
  `PROVIDER_MODE=mock` in `tests/conftest.py`; `.env` staat op `live` en die
  waarde won voorheen, wat drie tests stil over het netwerk liet gaan.
- Frontend: `cd frontend && npm test -- --run`.
- Validatie: `cd backend && PROVIDER_MODE=mock python -m scripts.validate` —
  streefwaarden coverage ≥70%, MAPE 🟢 ≤10%, kalibratie ≥80%. Staat nu op
  100% / 0,0% / 100%. Zonder die variabele stopt het script met uitleg in
  plaats van een nulmeting te rapporteren.
- **UI-rookproef: `cd backend && python -m scripts.ui_check`.** Verplicht bij
  elke frontendwijziging. Groene tests en een geslaagde build zeggen niets
  over of de interface het dóet — de mappenlaag ging live met 463 groene
  backendtests en 93 groene frontendtests terwijl niemand erop had geklikt.
  Dit script logt in met een echte browser, klikt de kritieke paden door en
  laat screenshots achter in `scripts/ui_check_output/` (gitignored) die je
  zelf moet bekijken; een geslaagde assertie zegt niet dat het er goed uitziet.

  ```
  UI_CHECK_URL=http://localhost:5173 UI_CHECK_PASSWORD=... python -m scripts.ui_check
  ```

  Draait ook tegen productie (`UI_CHECK_URL=https://frontend-production-3080.up.railway.app`);
  het script maakt alleen een eigen wegwerpmap aan en ruimt die op, ook na een
  mislukking. Wachtwoord via
  `railway variables -s backend --kv | grep DEMO_ADMIN_PASSWORD` — nooit in de
  repository.

## Conventies

- Python 3.10+-compatibel, SQLAlchemy 2 (Mapped/mapped_column), async pipeline.
- Domeintaal Nederlands (wp_kandidaat, bellijst, goedgekeurd_door) — consistent houden.
- Gewichten/drempels in `app/config.py`, nooit hardcoden in pipeline-code.
- Mock én live providers achter dezelfde Protocol-interfaces; nieuwe externe afhankelijkheden ook.
- Research-runs bewaren status, tokengebruik en kosten in `research_runs`.
- LLM-prompts bevatten altijd de prompt-injection-clausule (externe tekst = onbetrouwbare input).
- Bij wijzigingen: tests draaien én `scripts.validate` moet op streefwaarden blijven.
- Eén berekening per begrip. Als er al een helper is (`evidence._parse_year`, `usage.get_cost_summary`), hergebruik die; een tweede variant ernaast levert stilzwijgend afwijkende uitkomsten op.

## Belangrijke domeinregels

- Een proportionele schatting (`is_schatting=True`) mag NOOIT label 🟢 krijgen.
- LLM-zekerheid kan een confidence-score alleen begrenzen (cap), nooit verhogen.
- `count_lb == count_nl` (alles in Limburg) telt als locatie-eenduidig.
- KYC4etil schrijft geen bronbeslissingen door naar een register.
- FTE ≠ WP: nooit stilzwijgend omrekenen.
- Actualiteit telt mee: een WP-cijfer waarvan het peilmoment meer dan `peilmoment_max_leeftijd_jaren` (1) vóór het peiljaar ligt, krijgt een penalty. Eén jaar verschil is normaal — een jaarverslag over jaar X verschijnt pas in X+1. Een onbekend peilmoment is géén reden voor een penalty.

## Skills

Invoke the task-observer skill at the start of every task-oriented session.

## Openstaand (niet zelf oplossen, vragen aan Arrya)

- KvK API-key (kritieke afhankelijkheid voor locatiecount)
- `register_peildatum` (staat op 2026-04-01) wordt nergens uitgelezen. De confidence gebruikt `batch.jaar` als peiljaar. Besluiten of de peildatum een eigen rol moet krijgen of weg kan.
- Zuyderland ground truth (10.444 is placeholder, verifiëren)
- `requirements.txt` pint geen versies (`>=`). FastAPI liep daardoor lokaal naar 0.141 met gewijzigd `include_router`-gedrag. Overwegen om te pinnen.
