# Zoeken & filteren Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reviewers kunnen bedrijven binnen een batch zoeken op vestigingsnummer/CBR/KvK-nummer naast naam, filteren op sector, batches filteren op periode, en zoeken binnen de jaarverslag-monitoringlijst.

**Architecture:** Alle vier de filters zijn client-side (React `useMemo`), consistent met hoe zoeken/filteren nu al overal in deze applicatie werkt (`BatchView.jsx`, `JaarverslagenView.jsx`). De enige backend-wijziging is het toevoegen van vier extra velden aan één bestaande response (`GET /batches/{batch_id}/companies`) — geen nieuwe endpoints, geen nieuwe databasekolommen, geen nieuwe query-parameters.

**Tech Stack:** FastAPI/SQLAlchemy 2 (backend, ongewijzigd patroon), React 19 + Tailwind (frontend, ongewijzigd patroon), pytest.

## Global Constraints

- Domeintaal Nederlands — nieuwe variabelen/state/labels in het Nederlands, consistent met bestaande code (`zoek`, `gefilterd`, `sector`, `periode`).
- Frontend: puur Tailwind utility classes inline, `classNames()`-helper uit `frontend/src/lib/format.js` waar van toepassing, lucide-react-iconen, geen nieuwe styling-library.
- Geen wijziging aan `reconcile.py`, confidence-berekening, of enige pipeline-stap.
- Geen nieuwe databasekolommen of Alembic/lightweight-migraties nodig — alle gebruikte velden bestaan al op `Company`/`Batch`.
- Na de backend-taak: `cd backend && python3 -m pytest tests/ -q` moet slagen zonder nieuwe failures (huidige baseline: 190 passed, 0 failed).
- Na de frontend-taken: `cd frontend && npm run build` moet schoon compileren. Let op: system-Node in deze omgeving is v18.17.0, wat Vite 7 laat falen — gebruik `nvm use v20.19.0` (aanwezig in deze omgeving) vóór elke `npm run dev`/`npm run build`.
- Gebruik `python3`, niet `python`, als interpreter.

---

### Task 1: Backend — extra velden in de bedrijvenlijst-response

**Files:**
- Modify: `backend/app/routers/batches.py` (functie `list_companies`, rond regel 236-271)
- Test: `backend/tests/test_wp_uitsplitsing.py` (uitbreiden, naast de twee bestaande `test_companies_lijst_*`-tests rond regel 371-410)

**Interfaces:**
- Produces: elk item in de lijst-response van `GET /batches/{batch_id}/companies` bevat nu ook `vestigingsnummer`, `cb_er`, `kvk_nummer`, `sbi_omschrijving` (alle `str | None`, direct van het `Company`-model).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_wp_uitsplitsing.py` (gebruik de `client`/`db_session`-fixtures zoals de twee bestaande `test_companies_lijst_*`-tests in dit bestand):

```python
def test_companies_lijst_toont_vestigingsnummer_cber_kvk_en_sector(client, db_session):
    batch = Batch(naam="zoekvelden-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(
        batch_id=batch.id, naam="Testbedrijf", vestigingsnummer="V099",
        cb_er="CB099", kvk_nummer="99887766", sbi_omschrijving="Detailhandel",
    )
    db_session.add(company)
    db_session.commit()

    response = client.get(f"/batches/{batch.id}/companies")

    assert response.status_code == 200
    item = response.json()[0]
    assert item["vestigingsnummer"] == "V099"
    assert item["cb_er"] == "CB099"
    assert item["kvk_nummer"] == "99887766"
    assert item["sbi_omschrijving"] == "Detailhandel"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_wp_uitsplitsing.py::test_companies_lijst_toont_vestigingsnummer_cber_kvk_en_sector -q`
Expected: FAIL with `KeyError: 'vestigingsnummer'`

- [ ] **Step 3: Add the four fields to the response dict**

In `backend/app/routers/batches.py`, in `list_companies`, find:

```python
        out.append({
            "company_id": comp.id, "naam": comp.naam, "gemeente": comp.gemeente,
            "wp_kandidaat": cand.wp_kandidaat if cand else None,
```

Replace with:

```python
        out.append({
            "company_id": comp.id, "naam": comp.naam, "gemeente": comp.gemeente,
            "vestigingsnummer": comp.vestigingsnummer, "cb_er": comp.cb_er,
            "kvk_nummer": comp.kvk_nummer, "sbi_omschrijving": comp.sbi_omschrijving,
            "wp_kandidaat": cand.wp_kandidaat if cand else None,
```

(De rest van de dict-literal, vanaf `"wp_gevonden_ruw"` t/m `"pipeline_error"`, blijft ongewijzigd.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_wp_uitsplitsing.py::test_companies_lijst_toont_vestigingsnummer_cber_kvk_en_sector -q`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python3 -m pytest tests/ -q`
Expected: 191 passed (190 baseline + 1 nieuwe test), 0 failed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/batches.py backend/tests/test_wp_uitsplitsing.py
git commit -m "feat(zoeken): expose vestigingsnummer/cb_er/kvk_nummer/sbi_omschrijving in bedrijvenlijst"
```

---

### Task 2: Frontend — BatchView.jsx zoekbalk uitbreiden + sectorfilter

**Files:**
- Modify: `frontend/src/views/BatchView.jsx`

**Interfaces:**
- Consumes: de vier nieuwe velden uit Task 1's response (`vestigingsnummer`, `cb_er`, `kvk_nummer`, `sbi_omschrijving`), al aanwezig op elk item van `companies` na Task 1.

- [ ] **Step 1: Add a `sector` state variable**

In `frontend/src/views/BatchView.jsx`, find:

```jsx
  const [label, setLabel] = useState("");
  const [search, setSearch] = useState("");
```

Replace with:

```jsx
  const [label, setLabel] = useState("");
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
```

- [ ] **Step 2: Derive the unique sector options and extend the search filter**

Find:

```jsx
  const filtered = useMemo(() => companies.filter((company) => {
    if (label === "fouten") return !!company.pipeline_error;
    const text = `${company.naam || ""} ${company.gemeente || ""}`.toLowerCase();
    return text.includes(search.toLowerCase());
  }), [companies, label, search]);
```

Replace with:

```jsx
  const sectoren = useMemo(() => Array.from(new Set(
    companies.map((company) => company.sbi_omschrijving).filter(Boolean),
  )).sort(), [companies]);

  const filtered = useMemo(() => companies.filter((company) => {
    if (label === "fouten") return !!company.pipeline_error;
    if (sector && company.sbi_omschrijving !== sector) return false;
    const text = `${company.naam || ""} ${company.gemeente || ""} ${company.vestigingsnummer || ""} ${company.cb_er || ""} ${company.kvk_nummer || ""}`.toLowerCase();
    return text.includes(search.toLowerCase());
  }), [companies, label, search, sector]);
```

- [ ] **Step 3: Add the sector dropdown to the filter bar**

Find:

```jsx
      <div className="mb-4 grid gap-3 md:grid-cols-[1fr_200px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3 text-slate-500" size={17} />
          <input className="focus-ring h-11 w-full rounded-md border border-line bg-white pl-9 pr-3" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Zoeken" aria-label="Zoeken op vestiging of gemeente" />
        </div>
        <select className={classNames(
          "focus-ring h-11 rounded-md border bg-white px-3",
          label === "fouten" ? "border-red-400 text-red-700 font-medium" : "border-line",
        )} value={label} onChange={(event) => setLabel(event.target.value)} aria-label="Filter op confidence-label">
          <option value="">Alle labels</option>
          <option value="hoog">Eenduidig</option>
          <option value="middel">Twijfelachtig</option>
          <option value="laag">Onduidelijk</option>
          <option value="fouten">{batch?.fouten > 0 ? `Fouten (${batch.fouten})` : "Fouten"}</option>
        </select>
      </div>
```

Replace with:

```jsx
      <div className="mb-4 grid gap-3 md:grid-cols-[1fr_200px_200px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3 text-slate-500" size={17} />
          <input className="focus-ring h-11 w-full rounded-md border border-line bg-white pl-9 pr-3" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Zoeken op naam, gemeente, vestigingsnummer, CBR of KvK" aria-label="Zoeken op naam, gemeente, vestigingsnummer, CBR of KvK-nummer" />
        </div>
        <select className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={sector} onChange={(event) => setSector(event.target.value)} aria-label="Filter op sector">
          <option value="">Alle sectoren</option>
          {sectoren.map((naam) => <option key={naam} value={naam}>{naam}</option>)}
        </select>
        <select className={classNames(
          "focus-ring h-11 rounded-md border bg-white px-3",
          label === "fouten" ? "border-red-400 text-red-700 font-medium" : "border-line",
        )} value={label} onChange={(event) => setLabel(event.target.value)} aria-label="Filter op confidence-label">
          <option value="">Alle labels</option>
          <option value="hoog">Eenduidig</option>
          <option value="middel">Twijfelachtig</option>
          <option value="laag">Onduidelijk</option>
          <option value="fouten">{batch?.fouten > 0 ? `Fouten (${batch.fouten})` : "Fouten"}</option>
        </select>
      </div>
```

- [ ] **Step 4: Verify the build compiles cleanly**

Run: `cd frontend && nvm use v20.19.0 && npm run build`
Expected: build succeeds, no errors (met name geen `sectoren`/`sector` reference-fouten).

- [ ] **Step 5: Manual verification (best-effort — no browser tool available in this environment)**

Als er wél een browser beschikbaar is: start `cd backend && PROVIDER_MODE=mock uvicorn app.main:app --reload` en `cd frontend && nvm use v20.19.0 && npm run dev`, open een batch, en controleer: (a) typen van een vestigingsnummer (bv. "V001") of CBR-code (bv. "CB001") uit de testset filtert naar het juiste bedrijf, (b) de sectordropdown toont unieke, leesbare sectornamen en filtert correct, (c) beide filters combineren correct met het bestaande label-filter. Als er geen browser beschikbaar is: rapporteer dit expliciet in plaats van "werkt" te claimen (consistent met eerdere frontend-taken in dit project).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/BatchView.jsx
git commit -m "feat(zoeken): zoekbalk uitbreiden naar vestigingsnummer/CBR/KvK + sectorfilter in BatchView"
```

---

### Task 3: Frontend — Dashboard.jsx periodefilter

**Files:**
- Modify: `frontend/src/views/Dashboard.jsx`

**Interfaces:**
- Consumes: `Batch.created_at` (al aanwezig op elk item van `batches`, ISO-datetime string).

- [ ] **Step 1: Add period-filter state and an ISO-week helper**

In `frontend/src/views/Dashboard.jsx`, find:

```jsx
export function Dashboard({api, user, onLogout, openBatch, openChatTemplates, openJaarverslagen, openMonitoring}) {
  const fileRef = useRef(null);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
```

Replace with:

```jsx
function isoWeekGrenzen(weekOffset) {
  const nu = new Date();
  const dagIndex = (nu.getDay() + 6) % 7; // maandag = 0
  const maandag = new Date(nu.getFullYear(), nu.getMonth(), nu.getDate() - dagIndex + weekOffset * 7);
  const volgendeMaandag = new Date(maandag.getFullYear(), maandag.getMonth(), maandag.getDate() + 7);
  return [maandag, volgendeMaandag];
}

export function Dashboard({api, user, onLogout, openBatch, openChatTemplates, openJaarverslagen, openMonitoring}) {
  const fileRef = useRef(null);
  const [batches, setBatches] = useState([]);
  const [periode, setPeriode] = useState("alle");
  const [vanaf, setVanaf] = useState("");
  const [tot, setTot] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
```

- [ ] **Step 2: Add the filtered-batches derivation**

Find (right after the `load` function's closing brace, before the `useEffect`):

```jsx
  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 3000);
    return () => window.clearInterval(timer);
  }, []);
```

Leave the `useEffect` unchanged, but add this new block directly after it:

```jsx

  const gefilterd = useMemo(() => {
    if (periode === "alle") return batches;
    if (periode === "aangepast") {
      return batches.filter((batch) => {
        if (!batch.created_at) return false;
        const datum = batch.created_at.slice(0, 10);
        if (vanaf && datum < vanaf) return false;
        if (tot && datum > tot) return false;
        return true;
      });
    }
    const [van, totGrens] = isoWeekGrenzen(periode === "deze_week" ? 0 : -1);
    return batches.filter((batch) => {
      if (!batch.created_at) return false;
      const datum = new Date(batch.created_at);
      return datum >= van && datum < totGrens;
    });
  }, [batches, periode, vanaf, tot]);
```

Add `useMemo` to the existing React import at the top of the file:

```jsx
import {useEffect, useMemo, useRef, useState} from "react";
```

- [ ] **Step 3: Add the period-filter UI above the batch table**

Find:

```jsx
      {error ? <Alert message={error} /> : null}
      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Batch</th>
```

Replace with:

```jsx
      {error ? <Alert message={error} /> : null}
      <div className="mb-4 flex flex-wrap items-center justify-end gap-2">
        <select className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={periode} onChange={(event) => setPeriode(event.target.value)} aria-label="Filter op periode">
          <option value="alle">Alle periodes</option>
          <option value="deze_week">Deze week</option>
          <option value="vorige_week">Vorige week</option>
          <option value="aangepast">Aangepaste range</option>
        </select>
        {periode === "aangepast" ? (
          <>
            <input type="date" className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={vanaf} onChange={(event) => setVanaf(event.target.value)} aria-label="Vanaf datum" />
            <input type="date" className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={tot} onChange={(event) => setTot(event.target.value)} aria-label="Tot datum" />
          </>
        ) : null}
      </div>
      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Batch</th>
```

- [ ] **Step 4: Render the filtered list instead of the raw list**

Find:

```jsx
          <tbody>
            {batches.map((batch) => (
```

Replace with:

```jsx
          <tbody>
            {gefilterd.map((batch) => (
```

Find the empty-state row:

```jsx
            {!batches.length ? (
              <tr>
                <td className="px-4 py-8 text-center text-slate-500" colSpan="5">Geen batches</td>
              </tr>
            ) : null}
```

Replace with:

```jsx
            {!gefilterd.length ? (
              <tr>
                <td className="px-4 py-8 text-center text-slate-500" colSpan="5">
                  {batches.length ? "Geen batches in deze periode" : "Geen batches"}
                </td>
              </tr>
            ) : null}
```

- [ ] **Step 5: Verify the build compiles cleanly**

Run: `cd frontend && nvm use v20.19.0 && npm run build`
Expected: build succeeds, no errors.

- [ ] **Step 6: Manual verification (best-effort — no browser tool available in this environment)**

Als er een browser beschikbaar is: controleer dat "Deze week"/"Vorige week" de juiste batches tonen (maandag t/m zondag), dat "Aangepaste range" de twee datumvelden toont en filtert, en dat "Alle periodes" alles weer toont. Rapporteer expliciet als dit niet uitgevoerd kon worden.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/Dashboard.jsx
git commit -m "feat(zoeken): periodefilter (deze week/vorige week/aangepast) op het batch-overzicht"
```

---

### Task 4: Frontend — MonitoringView.jsx zoekbalk

**Files:**
- Modify: `frontend/src/views/MonitoringView.jsx`

**Interfaces:**
- Consumes: `company.naam`/`company.gemeente` (al aanwezig op elk item van `status.companies`).

- [ ] **Step 1: Add `useMemo` and a `Search` icon to the imports**

Find:

```jsx
import {useEffect, useState} from "react";
import {AlertTriangle, FileSearch, ListChecks, RefreshCw, Sparkles} from "lucide-react";
```

Replace with:

```jsx
import {useEffect, useMemo, useState} from "react";
import {AlertTriangle, FileSearch, ListChecks, RefreshCw, Search, Sparkles} from "lucide-react";
```

- [ ] **Step 2: Add a `zoek` state variable**

Find:

```jsx
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [gestartOm, setGestartOm] = useState(null);
```

Replace with:

```jsx
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [gestartOm, setGestartOm] = useState(null);
  const [zoek, setZoek] = useState("");
```

- [ ] **Step 3: Derive the filtered companies list**

Find:

```jsx
  const batch = status?.batch;
  const companies = status?.companies || [];
```

Replace with:

```jsx
  const batch = status?.batch;
  const companies = status?.companies || [];
  const gefilterd = useMemo(() => companies.filter((company) => {
    const text = `${company.naam || ""} ${company.gemeente || ""}`.toLowerCase();
    return text.includes(zoek.toLowerCase());
  }), [companies, zoek]);
```

- [ ] **Step 4: Add the search bar above the metrics grid**

Find:

```jsx
          {gestartOm ? (
            <p className="mb-4 text-sm text-slate-600">
              Controle gestart om {formatDatumTijd(gestartOm.toISOString())}. Het overzicht ververst vanzelf.
            </p>
          ) : null}
          <div className="mb-4 grid gap-3 md:grid-cols-5">
```

Replace with:

```jsx
          {gestartOm ? (
            <p className="mb-4 text-sm text-slate-600">
              Controle gestart om {formatDatumTijd(gestartOm.toISOString())}. Het overzicht ververst vanzelf.
            </p>
          ) : null}
          <div className="relative mb-4">
            <Search className="pointer-events-none absolute left-3 top-3 text-slate-500" size={17} />
            <input className="focus-ring h-11 w-full max-w-sm rounded-md border border-line bg-white pl-9 pr-3" value={zoek} onChange={(event) => setZoek(event.target.value)} placeholder="Zoeken" aria-label="Zoeken op naam of gemeente" />
          </div>
          <div className="mb-4 grid gap-3 md:grid-cols-5">
```

- [ ] **Step 5: Render the filtered list instead of the raw list**

Find:

```jsx
              <tbody>
                {companies.map((company) => (
```

Replace with:

```jsx
              <tbody>
                {gefilterd.map((company) => (
```

Find the empty-state row:

```jsx
                {!companies.length ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-500" colSpan="4">
                      Geen organisaties in de watchlist
                    </td>
                  </tr>
                ) : null}
```

Replace with:

```jsx
                {!gefilterd.length ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-500" colSpan="4">
                      {companies.length ? "Geen resultaten voor deze zoekopdracht" : "Geen organisaties in de watchlist"}
                    </td>
                  </tr>
                ) : null}
```

- [ ] **Step 6: Verify the build compiles cleanly**

Run: `cd frontend && nvm use v20.19.0 && npm run build`
Expected: build succeeds, no errors.

- [ ] **Step 7: Manual verification (best-effort — no browser tool available in this environment)**

Als er een browser beschikbaar is: open de jaarverslag-monitoringpagina en controleer dat typen in de zoekbalk de lijst filtert op naam/gemeente. Rapporteer expliciet als dit niet uitgevoerd kon worden.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/MonitoringView.jsx
git commit -m "feat(zoeken): zoekbalk toevoegen aan de jaarverslag-monitoringlijst"
```

---

### Task 5: Eindverificatie

**Files:** geen wijzigingen.

- [ ] **Step 1: Full backend suite + validate**

Run: `cd backend && python3 -m pytest tests/ -q && python3 -m scripts.validate`
Expected: 191 passed, 0 failed (190 baseline + 1 nieuwe test uit Task 1); validate-streefwaarden ongewijzigd (coverage 100%, MAPE 🟢 0%, kalibratie 100%) — dit sub-project raakt de pipeline/reconciliatie niet, dus deze cijfers moeten identiek blijven aan vóór dit project.

- [ ] **Step 2: Frontend build check**

Run: `cd frontend && nvm use v20.19.0 && npm run build`
Expected: build slaagt zonder errors, met name geen import-fouten rond `useMemo` in `Dashboard.jsx`/`MonitoringView.jsx` of de nieuwe `sectoren`/`gefilterd`-variabelen.

- [ ] **Step 3: Walk through the manual-verification checklists from Tasks 2, 3 en 4 one more time, end-to-end, if a browser becomes available.** Zo niet: rapporteer expliciet dat dit een open, aan een mens over te laten stap blijft (consistent met de rest van dit project — zie `docs/superpowers/specs/2026-07-24-zoeken-en-filteren-design.md`, sectie Testing).

- [ ] **Step 4: No commit needed** — dit is een verificatie-only taak. Als een check faalt, ga terug naar de betreffende taak, fix, herrun die taak se eigen tests, en herhaal deze taak.

---

## Self-Review Notes

- **Spec coverage:** bedrijvenzoekbalk uitbreiden naar vestigingsnummer/CBR/KvK (Task 1+2) ✓, sectorfilter binnen batch (Task 1+2) ✓, periodefilter op batch-overzicht met ISO-weekgrenzen + aangepaste range (Task 3) ✓, zoekbalk in jaarverslag-monitoringlijst (Task 4) ✓, geen wijziging aan reconciliatie/scoring/pipeline (expliciet genoemd, niet aangeraakt in enige taak) ✓, geen nieuwe databasekolommen/migraties (bevestigd — alleen bestaande velden gebruikt) ✓.
- **Type consistency:** de vier nieuwe responsevelden (`vestigingsnummer`, `cb_er`, `kvk_nummer`, `sbi_omschrijving`) hebben in Task 1 exact dezelfde namen als waar Task 2's `BatchView.jsx`-filterlogica naar verwijst — geen naamverschil tussen backend-output en frontend-consumptie.
- **Bekende beperking, geen blokkade:** net als bij eerdere frontend-taken in dit project is er geen browser-tool beschikbaar om de UI daadwerkelijk visueel te verifiëren — elke taak downgrade't dit expliciet naar "build compileert schoon" + een niet-geblokkeerde, voor een mens achtergelaten checklist, in plaats van een niet-uitgevoerde check als "geslaagd" te claimen.
