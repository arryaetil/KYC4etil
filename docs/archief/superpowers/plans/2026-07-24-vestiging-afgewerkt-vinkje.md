# "Vestiging afgewerkt"-vinkje Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reviewers kunnen per bedrijf in een batch handmatig een "afgewerkt"-checkbox aan/uit zetten, los van de automatische pipeline-status.

**Architecture:** Eén nieuw boolean-veld `Company.afgewerkt`, gevuld/uitgelezen via de al bestaande `PATCH`/`GET`-endpoints voor de bedrijvenlijst (additieve uitbreiding, geen nieuwe routes). Frontend: een checkbox-kolom in `BatchView.jsx` die direct de PATCH-call doet en optimistisch update.

**Tech Stack:** FastAPI/SQLAlchemy 2 (backend, ongewijzigd patroon), React 19 + Tailwind (frontend, ongewijzigd patroon), pytest.

## Global Constraints

- Domeintaal Nederlands — nieuwe naam is `afgewerkt` (niet "done"/"finished"), consistent met bestaande Nederlandse velden.
- Frontend: puur Tailwind utility classes inline, lucide-react-iconen waar van toepassing, geen nieuwe styling-library.
- Geen wijziging aan `reconcile.py`, confidence-berekening, of enige pipeline-stap.
- Geen filter, geen weergave in de detailpagina — alleen de checkbox-kolom in `BatchView.jsx` (expliciet uit scope, per de goedgekeurde spec).
- Na de backend-taak: `cd backend && python3 -m pytest tests/ -q` moet slagen zonder nieuwe failures (huidige baseline: 191 passed, 0 failed).
- Na de frontend-taak: `cd frontend && npm run build` moet schoon compileren. System-Node in deze omgeving is v18.17.0, wat Vite 7 laat falen — gebruik expliciet het pad `$HOME/.nvm/versions/node/v20.19.0/bin` vooraan in `PATH` (of `nvm use v20.19.0`, als dat in de gebruikte shell werkt) vóór elke `npm run build`.
- Gebruik `python3`, niet `python`, als interpreter.

---

### Task 1: Backend — `afgewerkt`-veld op Company

**Files:**
- Modify: `backend/app/models.py` (`Company`-class, rond regel 46-66)
- Modify: `backend/app/database.py` (`ensure_lightweight_migrations`, rond regel 38-49)
- Modify: `backend/app/routers/batches.py` (`CompanyUpdateBody`/`_COMPANY_FIELDS`, rond regel 371-383; `list_companies`, rond regel 262-267)
- Test: `backend/tests/test_wp_uitsplitsing.py` (uitbreiden, naast de bestaande `test_companies_lijst_*`-tests)

**Interfaces:**
- Produces: `Company.afgewerkt: bool` (default `False`); `PATCH /batches/{batch_id}/companies/{company_id}` accepteert `{"afgewerkt": true|false}`; elk item in `GET /batches/{batch_id}/companies` bevat `"afgewerkt": bool`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_wp_uitsplitsing.py`:

```python
def test_company_afgewerkt_toggle_via_patch(client, db_session):
    batch = Batch(naam="afgewerkt-test", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf")
    db_session.add(company)
    db_session.commit()

    response = client.get(f"/batches/{batch.id}/companies")
    assert response.json()[0]["afgewerkt"] is False

    patch_response = client.patch(
        f"/batches/{batch.id}/companies/{company.id}",
        json={"afgewerkt": True},
    )
    assert patch_response.status_code == 200

    response = client.get(f"/batches/{batch.id}/companies")
    assert response.json()[0]["afgewerkt"] is True


def test_company_afgewerkt_blijft_ongewijzigd_zonder_dat_veld(client, db_session):
    batch = Batch(naam="afgewerkt-test-2", jaar=2026, totaal=1)
    db_session.add(batch)
    db_session.flush()
    company = Company(batch_id=batch.id, naam="Testbedrijf", afgewerkt=True)
    db_session.add(company)
    db_session.commit()

    patch_response = client.patch(
        f"/batches/{batch.id}/companies/{company.id}",
        json={"naam": "Testbedrijf BV"},
    )
    assert patch_response.status_code == 200

    response = client.get(f"/batches/{batch.id}/companies")
    assert response.json()[0]["afgewerkt"] is True
    assert response.json()[0]["naam"] == "Testbedrijf BV"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_wp_uitsplitsing.py::test_company_afgewerkt_toggle_via_patch tests/test_wp_uitsplitsing.py::test_company_afgewerkt_blijft_ongewijzigd_zonder_dat_veld -q`
Expected: FAIL — eerste test met `KeyError: 'afgewerkt'` (ontbreekt in de GET-response), tweede test met `TypeError: 'afgewerkt' is an invalid keyword argument for Company`.

- [ ] **Step 3: Add the field to the Company model**

In `backend/app/models.py`, in de `Company`-class, direct na `kvk_nummer` en vóór `website_url`:

```python
    kvk_nummer: Mapped[str | None] = mapped_column(String(20))
    afgewerkt: Mapped[bool] = mapped_column(Boolean, default=False)
    website_url: Mapped[str | None] = mapped_column(Text)
```

(`Boolean` is al geïmporteerd bovenaan het bestand — zie regel 10-11, gebruikt door o.a. `Batch.is_monitoringlijst`.)

- [ ] **Step 4: Extend the lightweight migration**

In `backend/app/database.py`, in `ensure_lightweight_migrations()`, in het `companies`-blok:

```python
    existing_companies = {col["name"] for col in inspector.get_columns("companies")}
    with engine.begin() as conn:
        for name, ddl_type in [
            ("website_url", "TEXT"), ("telefoonnummer", "VARCHAR(50)"),
            ("afgewerkt", "BOOLEAN"),
        ]:
            _add_column_if_missing(conn, "companies", existing_companies, name, ddl_type)
```

- [ ] **Step 5: Add the field to CompanyUpdateBody and _COMPANY_FIELDS**

In `backend/app/routers/batches.py`:

```python
class CompanyUpdateBody(BaseModel):
    naam: str | None = None
    gemeente: str | None = None
    adres: str | None = None
    sbi_code: str | None = None
    cb_er: str | None = None
    kvk_nummer: str | None = None
    afgewerkt: bool | None = None
    website_url: str | None = None
    telefoonnummer: str | None = None
    email: str | None = None


_COMPANY_FIELDS = {"naam", "gemeente", "adres", "sbi_code", "cb_er", "kvk_nummer", "afgewerkt"}
_ENRICHMENT_FIELDS = {"website_url", "telefoonnummer", "email"}
```

- [ ] **Step 6: Add the field to the list_companies response**

In `backend/app/routers/batches.py`, in `list_companies`, binnen de `out.append({...})`-dict:

```python
        out.append({
            "company_id": comp.id, "naam": comp.naam, "gemeente": comp.gemeente,
            "vestigingsnummer": comp.vestigingsnummer, "cb_er": comp.cb_er,
            "kvk_nummer": comp.kvk_nummer, "sbi_omschrijving": comp.sbi_omschrijving,
            "afgewerkt": comp.afgewerkt,
            "wp_kandidaat": cand.wp_kandidaat if cand else None,
```

(De rest van de dict-literal blijft ongewijzigd.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_wp_uitsplitsing.py::test_company_afgewerkt_toggle_via_patch tests/test_wp_uitsplitsing.py::test_company_afgewerkt_blijft_ongewijzigd_zonder_dat_veld -q`
Expected: PASS (2 passed)

- [ ] **Step 8: Run the full backend suite**

Run: `cd backend && python3 -m pytest tests/ -q`
Expected: 193 passed (191 baseline + 2 nieuwe tests), 0 failed.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models.py backend/app/database.py backend/app/routers/batches.py backend/tests/test_wp_uitsplitsing.py
git commit -m "feat(afgewerkt): voeg handmatig afgewerkt-veld toe aan Company"
```

---

### Task 2: Frontend — checkbox-kolom in BatchView.jsx

**Files:**
- Modify: `frontend/src/views/BatchView.jsx`

**Interfaces:**
- Consumes: `company.afgewerkt` (bool, uit Task 1's response), `api.updateCompany(batchId, companyId, body)` (bestaande functie in `frontend/src/api.js`, accepteert nu ook `{afgewerkt: bool}`).

- [ ] **Step 1: Add a local toggle handler**

In `frontend/src/views/BatchView.jsx`, na de bestaande `deleteBatch`-functie (vlak vóór `const isRunning = batch?.status === "running";`), voeg toe:

```jsx
  async function toggleAfgewerkt(company) {
    const nieuweWaarde = !company.afgewerkt;
    setCompanies((huidige) => huidige.map((c) =>
      c.company_id === company.company_id ? {...c, afgewerkt: nieuweWaarde} : c
    ));
    try {
      await api.updateCompany(batchId, company.company_id, {afgewerkt: nieuweWaarde});
    } catch (err) {
      setCompanies((huidige) => huidige.map((c) =>
        c.company_id === company.company_id ? {...c, afgewerkt: company.afgewerkt} : c
      ));
      setError(err.message);
    }
  }
```

- [ ] **Step 2: Add the table header column**

Find:

```jsx
            <tr>
              <th className="px-4 py-3">Vestiging</th>
              <th className="px-4 py-3">WP</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Status</th>
            </tr>
```

Replace with:

```jsx
            <tr>
              <th className="px-4 py-3">Vestiging</th>
              <th className="px-4 py-3">WP</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Afgewerkt</th>
            </tr>
```

- [ ] **Step 3: Add the checkbox cell**

Find:

```jsx
                <td className="px-4 py-3"><StatusPill status={company.status} /></td>
              </tr>
            ))}
          </tbody>
```

Replace with:

```jsx
                <td className="px-4 py-3"><StatusPill status={company.status} /></td>
                <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
                  <input
                    type="checkbox"
                    className="focus-ring h-4 w-4 rounded border-line"
                    checked={!!company.afgewerkt}
                    onChange={() => toggleAfgewerkt(company)}
                    aria-label={`Markeer ${company.naam} als afgewerkt`}
                  />
                </td>
              </tr>
            ))}
          </tbody>
```

- [ ] **Step 4: Verify the build compiles cleanly**

Run: `export PATH="$HOME/.nvm/versions/node/v20.19.0/bin:$PATH" && cd frontend && npm run build`
Expected: build succeeds, no errors (met name geen `toggleAfgewerkt`/`setCompanies`-referentiefouten).

- [ ] **Step 5: Manual verification (best-effort — no browser tool available in this environment)**

Als er wél een browser beschikbaar is (of via een lokale Playwright-controle zoals eerder in dit project): open een batch, klik een checkbox aan — deze moet direct visueel omslaan zonder de rij te openen, en na een pagina-refresh behouden blijven. Klik nogmaals uit om te bevestigen dat het weer teruggezet wordt. Test ook: een tijdelijk verbroken netwerkverbinding (of een 500-response) moet de checkbox terugzetten naar de vorige staat en de foutmelding tonen. Als er geen browser/Playwright-controle uitgevoerd kan worden: rapporteer dit expliciet in plaats van "werkt" te claimen.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/BatchView.jsx
git commit -m "feat(afgewerkt): checkbox-kolom in BatchView om vestigingen handmatig te markeren"
```

---

### Task 3: Eindverificatie

**Files:** geen wijzigingen.

- [ ] **Step 1: Full backend suite + validate**

Run: `cd backend && python3 -m pytest tests/ -q && python3 -m scripts.validate`
Expected: 193 passed, 0 failed; validate-streefwaarden ongewijzigd (coverage 100%, MAPE 🟢 0%, kalibratie 100%) — dit sub-project raakt de pipeline/reconciliatie niet.

- [ ] **Step 2: Frontend build check**

Run: `export PATH="$HOME/.nvm/versions/node/v20.19.0/bin:$PATH" && cd frontend && npm run build`
Expected: build slaagt zonder errors.

- [ ] **Step 3: Manual browser walkthrough if possible** — herhaal de checklist uit Task 2 Step 5 end-to-end. Als dit niet mogelijk is (geen browser-tool beschikbaar), rapporteer dit expliciet als open punt, consistent met eerdere sub-projecten in dit traject.

- [ ] **Step 4: No commit needed** — dit is een verificatie-only taak. Als een check faalt, ga terug naar de betreffende taak, fix, herrun die taak z'n eigen tests, en herhaal deze taak.

---

## Self-Review Notes

- **Spec coverage:** nieuw boolean-veld op `Company` (Task 1) ✓, toggle via bestaand PATCH-endpoint (Task 1) ✓, zichtbaar in `list_companies`-response (Task 1) ✓, checkbox-kolom alleen in `BatchView.jsx` (Task 2) ✓, geen filter/detailpagina-weergave (expliciet niet geïmplementeerd, buiten scope conform spec) ✓, geen wijziging aan reconciliatie/confidence (geen enkele taak raakt die bestanden aan) ✓.
- **Type consistency:** `afgewerkt` is overal `bool`/`bool | None` — model, request body, response — geen naams- of typeverschil tussen backend (Task 1) en frontend-consumptie (Task 2).
- **Bekende beperking, geen blokkade:** net als bij sub-project 1 is er mogelijk geen browser-tool beschikbaar voor de implementer — elke taak downgrade't dit expliciet naar "build compileert schoon" in plaats van een niet-uitgevoerde check als geslaagd te claimen.
