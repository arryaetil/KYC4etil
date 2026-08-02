# Jaarverslag-monitoring als hoofddashboard-module — Design

**Project:** Vestigingsregister AI Platform (Etil / Provincie Limburg)
**Datum:** 2026-07-07
**Auteur:** Arrya Willems

---

## 1. Context

Een eerdere sessie bouwde periodieke jaarverslag-monitoring (spec:
`2026-07-07-jaarverslag-onderzoeksagent-design.md`, plan:
`2026-07-07-jaarverslag-monitoring.md`) als een generieke, per-batch feature:
elke willekeurige CSV-batch kon via een "Monitoring"-knop in `BatchView`
handmatig gecontroleerd worden op nieuwe jaarverslagen. Na oplevering bleek dit
niet te matchen met het echte mentale model: er is **één specifieke, doorlopende
watchlist** van organisaties die **wekelijks automatisch** gecontroleerd moet
worden — geen ad-hoc actie op een willekeurige batch, en zichtbaar op het
hoofddashboard, niet genest onder een specifieke batch.

Tijdens het herontwerp kwam een belangrijke correctie van de gebruiker naar
voren: de beschikbare brondata (`Testbatch Jaarverslagen.xls`, aangeleverd door
Armina) is vestiging-niveau (1786 + 95 rijen over de tabbladen "Alles vorig
jaar 16" en "Alles map Jaarverslagen"), maar een jaarverslag wordt gepubliceerd
op **organisatieniveau**. Rijen met dezelfde `cbnr` horen bij dezelfde
organisatie (CB-er) — bijvoorbeeld "Stichting Dichterbij" met 278 vestigingen
in de brondata. Monitoring per vestiging zou dus tot 278× dezelfde zoekopdracht
herhalen. Na deduplicatie op organisatieniveau (cbnr-groepering, of de losse
vestiging zelf als cbnr = "000000") komt de watchlist uit op **206 unieke
organisaties** — kosten en looptijd zijn hierdoor verwaarloosbaar (~$0,60/week,
enkele minuten per run), waar de vestiging-niveau-aanname aanvankelijk een
kosten-/tijdsprobleem leek (uren per run bij >1800 "bedrijven").

**Besluit:** volledige lijst (206 organisaties), niet alleen de zorg-subset
(49) — kosten/tijd zijn in beide gevallen verwaarloosbaar, dus geen reden om
klein te beginnen.

---

## 2. Doel & Scope

**Doel:** Armina/Anita hoeven niet meer handmatig te controleren of er een
nieuw jaarverslag verschenen is voor de ~206 organisaties op de watchlist —
dat gebeurt wekelijks automatisch, met een duidelijk overzicht op het
hoofddashboard en de mogelijkheid het handmatig te forceren.

**In scope:**
1. Eenmalig data-prep-script: `Testbatch Jaarverslagen.xls` → gededupliceerde
   organisatie-CSV (206 rijen), geüpload als de watchlist-batch.
2. `Batch.is_monitoringlijst`-vlag: markeert dé actieve watchlist.
3. Dashboard-niveau endpoints (`GET /monitoring`, `POST /monitoring/run`) die
   zelf de gemarkeerde batch opzoeken — geen `batch_id` in de URL.
4. Begrensde gelijktijdigheid in `run_monitoring_background` (bv. 8-10
   tegelijk via een semafoor), voor toekomstbestendigheid bij een groeiende
   lijst.
5. Wekelijkse automatische trigger via een in-process scheduler (APScheduler)
   binnen de al-draaiende backend — geen aparte Railway-service.
6. Nieuwe hoofddashboard-knop "Jaarverslag-monitoring", met een scherm dat
   altijd op de actieve watchlist werkt (geen batch-selectie meer nodig).
7. Verwijderen van de eerder gebouwde per-batch `MonitoringView` en de
   "Monitoring"-knop in `BatchView` — één duidelijk pad, geen twee
   concurrerende manieren om hetzelfde te doen.

**Buiten scope (bewust):**
- Meerdere genoemde watchlists per sector (zorg/onderwijs/etc.) — de gebruiker
  koos expliciet voor één vaste lijst nu; latere uitbreiding kan
  `is_monitoringlijst: bool` vervangen door een naam/sector-veld zonder de
  rest van het ontwerp te breken.
- Scenario 2 (Totaal-WP per CO'er) en de adaptieve website-agent uit de
  bredere onderzoeksagent-spec — losse, al eerder opgeleverde/geplande stukken.
- Wijzigingen aan `check_company_jaarverslag()` zelf (de kernextractielogica
  blijft ongewijzigd) — dit ontwerp raakt alleen hoe/wanneer die aangeroepen
  wordt en hoe de resultaten getoond worden.

---

## 3. Architectuur

### 3.1 Data-prep (eenmalig, geen productiecode)

Een script (`backend/scripts/prepareer_monitoringlijst.py`) dat:
1. `Testbatch Jaarverslagen.xls` inleest (tabbladen "Alles vorig jaar 16" +
   "Alles map Jaarverslagen") met `xlrd` (bestaand `.xls`-formaat, geen
   `openpyxl`).
2. Per rij in "Alles vorig jaar 16": groepeert op `cbnr`. Voor elke groep met
   `cbnr != "000000"`: de organisatienaam is de niet-lege waarde uit de
   `CB-er`-kolom binnen die groep (elke groep heeft precies één rij met een
   ingevulde `CB-er`-naam; fallback naar de kortste `naam`-waarde in de groep
   als geen enkele rij een `CB-er`-waarde heeft). Voor `cbnr == "000000"`:
   de vestiging is zelf de organisatie, `naam` = de eigen naam.
3. Per rij in "Alles map Jaarverslagen": deze tab is al organisatie-niveau
   (kolom `naam CB-er`); direct bruikbaar.
4. Dedupliceert de gecombineerde set op `cbnr` (voor gegroepeerde
   organisaties) of op naam (voor losse vestigingen).
5. Schrijft een CSV met kolommen `naam,cb_er` (206 rijen) naar
   `backend/data/jaarverslag_monitoringlijst.csv`.

Dit script draait één keer, lokaal, om de CSV te produceren. De upload naar
productie gebeurt via het bestaande `/batches/upload`-endpoint (zie 3.2) —
niet via het script zelf, zodat de normale upload-/validatiepad gebruikt wordt.

### 3.2 Backend

**Datamodel:**
```python
# Batch (uitbreiding)
is_monitoringlijst: Mapped[bool] = mapped_column(Boolean, default=False)
```

**Endpoints (nieuw, dashboard-niveau, geen batch_id in de URL):**
- `POST /batches/upload?monitoringlijst=true` — bestaand upload-endpoint,
  uitgebreid: als `monitoringlijst=true`, wordt de nieuwe batch
  `is_monitoringlijst=True` gezet én wordt elke eerder gemarkeerde batch
  automatisch ontmarkeerd (hoogstens één actieve watchlist tegelijk).
- `GET /monitoring` — zoekt de batch met `is_monitoringlijst=True` op; retourneert
  dezelfde statusvorm als de eerder gebouwde `GET /batches/{id}/monitoring`
  (totaal, gecontroleerd, nieuwe bevindingen, fouten, per-organisatie-detail),
  met `batch: null` als er nog geen watchlist is ingesteld.
- `POST /monitoring/run` — zoekt dezelfde gemarkeerde batch op en start
  `run_monitoring_background` daarvoor; 404 als er geen watchlist is.

**Concurrency:** `run_monitoring_background` verwerkt organisaties met een
`asyncio.Semaphore` van 8 gelijktijdige taken i.p.v. strikt sequentieel —
elke organisatie behoudt zijn eigen try/except/log-patroon, alleen de
iteratie wordt `asyncio.gather` over ten hoogste 8 gelijktijdige taken in
plaats van een `for`-lus.

**Scheduler:** `APScheduler`'s `AsyncIOScheduler`, gestart in `app/main.py`'s
lifespan/startup-hook, met een wekelijkse cron-trigger (maandag 06:00,
Europe/Amsterdam-tijdzone) die dezelfde interne functie aanroept als
`POST /monitoring/run` (geen HTTP-round-trip nodig — direct de Python-functie
aanroepen binnen het proces). Nieuwe dependency: `apscheduler` in
`requirements.txt`.

**Cleanup:** de bestaande per-batch `GET /batches/{batch_id}/monitoring` en
`POST /batches/{batch_id}/monitor`-endpoints worden verwijderd (vervangen
door de dashboard-niveau versies) — niet ernaast gehouden, om twee
concurrerende paden naar hetzelfde te voorkomen.

### 3.3 Frontend

- Nieuwe `JaarverslagMonitoringView` (geen `batchId`-prop) — hergebruikt de
  bestaande metrics-/tabel-opzet uit de eerder gebouwde `MonitoringView`, maar:
  - Als `GET /monitoring` `batch: null` teruggeeft: lege staat met duidelijke
    tekst ("Nog geen watchlist ingesteld") — geen crash, geen foutmelding.
  - Anders: dezelfde metrics (Totaal/Gecontroleerd/Nieuwe bevindingen/Fouten)
    + tabel (Organisatie/Laatst gecontroleerd/Laatste bron/Status) + "Nu
    controleren"-knop.
- Nieuwe hoofdknop op `Dashboard.jsx`, naast "Jaarverslagen"/"Chat-templates".
- Verwijderen: `MonitoringView.jsx` (oude, per-batch versie), de
  "Monitoring"-knop + `openMonitoring`-prop in `BatchView.jsx`, de
  `monitoring`-route in `App.jsx` die een `batchId` verwachtte — vervangen
  door een route zonder parameter.
- `api.js`: `monitoringStatus()`/`monitorRun()` zonder `batchId`-argument
  (was `monitoringStatus(id)`/`monitorBatch(id)`).

---

## 4. Dataflow

1. **Eenmalige setup:** data-prep-script draait → CSV met 206 organisaties →
   geüpload via `POST /batches/upload?monitoringlijst=true` → nieuwe `Batch`
   met `is_monitoringlijst=True`, 206 `Company`-rijen (één per organisatie,
   `cb_er` = cbnr waar van toepassing).
2. **Wekelijks (automatisch):** scheduler triggert maandagochtend →
   `run_monitoring_background` zoekt de gemarkeerde batch op → verwerkt de
   206 organisaties met begrensde gelijktijdigheid → per organisatie:
   `check_company_jaarverslag()` (ongewijzigd) → resultaten landen zoals
   altijd in de review-wachtrij via de bestaande confidence-/reconciliatielogica.
3. **Handmatig (op aanvraag):** reviewer klikt "Nu controleren" op het
   Dashboard → `POST /monitoring/run` → zelfde onderliggende functie, direct
   getriggerd i.p.v. te wachten op de wekelijkse cron.
4. **Bekijken:** reviewer opent "Jaarverslag-monitoring" vanuit het Dashboard
   → `GET /monitoring` → ziet direct de status van de ene, vaste watchlist.

---

## 5. Error handling & edge cases

- Nog geen watchlist ingesteld (`is_monitoringlijst`-batch bestaat niet):
  `GET /monitoring` geeft `{"batch": null, ...}` i.p.v. een fout; frontend
  toont een duidelijke lege staat, geen crash.
- Een nieuwe watchlist uploaden terwijl er al één actief is: de oude wordt
  automatisch ontmarkeerd (niet verwijderd — blijft gewoon een normale batch,
  alleen niet meer "de" watchlist).
- Eén organisatie faalt tijdens de wekelijkse/handmatige run: bestaand
  gedrag blijft — loggen naar `pipeline_runs`, doorgaan met de rest (nu ook
  onder de semafoor-gebaseerde concurrency, dezelfde garantie).
- Scheduler-run en handmatige "Nu controleren"-klik overlappen toevallig:
  buiten scope voor nu — bij 206 organisaties en een looptijd van enkele
  minuten is de kans klein en de impact beperkt (hooguit dubbel werk voor
  dezelfde organisaties in die run, geen datacorruptie, want
  `check_company_jaarverslag` is idempotent per organisatie).

---

## 6. Testing & validatie

- Data-prep-script: unit test op een kleine, ingebakken testset (niet het
  echte bestand) die het cbnr-groeperen en de CB-er-naam-selectie verifieert,
  inclusief de fallback (geen enkele rij met ingevulde CB-er-naam in een
  groep) en de dedupe tussen de twee tabbladen.
- Backend: tests voor `POST /batches/upload?monitoringlijst=true` (vlag
  correct gezet, vorige watchlist ontmarkeerd), `GET /monitoring` (met en
  zonder actieve watchlist), `POST /monitoring/run` (404 zonder watchlist,
  start de achtergrondtaak met de juiste batch anders).
- Scheduler: geen tijdklok-afhankelijke test nodig — een test die verifieert
  dat de scheduler bij opstarten geregistreerd wordt met de juiste
  trigger-functie is voldoende; het daadwerkelijke wekelijkse vuren wordt niet
  in CI getest.
- Handmatige validatie na deploy: eenmalig `POST /monitoring/run` triggeren
  en de resultaten in het nieuwe dashboardscherm bekijken, vergelijkbaar met
  de validatie die al gedaan is voor de eerdere per-batch versie.
