# Upload-tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Op het Dashboard zien welke gebruiker een batch heeft geüpload.

**Architecture:** Nieuw `Batch.geupload_door`-veld (FK naar `users.id`, zelfde patroon als het bestaande `goedgekeurd_door`), gevuld bij upload via de al ingelogde gebruiker, gerapporteerd als een naam via `GET /batches`. Bestaande batches krijgen de uploader-waarde via een apart, eenmalig, handmatig te draaien backfill-script (niet via de schema-migratie, want die draait vóórdat het admin-account bestaat).

**Tech Stack:** FastAPI/SQLAlchemy 2 (backend, ongewijzigd patroon), React 19 + Tailwind (frontend, ongewijzigd patroon), pytest.

## Global Constraints

- Domeintaal Nederlands — nieuw veld heet `geupload_door`, response-sleutel `geupload_door_naam`, nieuwe test-/scriptnamen in het Nederlands.
- Geen wijziging aan `reconcile.py`, confidence-berekening, of enige pipeline-stap.
- Geen wijziging aan `BatchView.jsx` — uploader-info alleen op het Dashboard.
- Frontend: puur Tailwind utility classes inline, geen nieuwe styling-library.
- Na elke backend-taak: `cd backend && python3 -m pytest tests/ -q` moet slagen zonder nieuwe failures (huidige baseline: 194 passed, 0 failed).
- Na de frontend-taak: `cd frontend && npm run build` moet schoon compileren. System-Node in deze omgeving is v18.17.0, wat Vite 7 laat falen — prepend `$HOME/.nvm/versions/node/v20.19.0/bin` aan `PATH` vóór elke `npm run build`.
- Gebruik `python3`, niet `python`, als interpreter.
- **Belangrijke test-subtiliteit:** de `client`/`db_session`-fixtures in `backend/tests/conftest.py` draaien op een in-memory SQLite-database met `PRAGMA foreign_keys=ON`, en de gemockte ingelogde gebruiker (`_TEST_USER`, `id="test-user-id"`) wordt NIET automatisch in die testdatabase gepersisteerd. Omdat `geupload_door` een echte foreign key naar `users.id` is, moet elke nieuwe test die de upload-endpoint aanroept via de `client`-fixture eerst zelf een `User`-rij met `id="test-user-id"` in `db_session` aanmaken, anders faalt de insert op een foreign-key-constraint-fout. Zie Task 1, Step 1 voor het exacte patroon.

---

### Task 1: Backend — geupload_door-veld, migratie, upload/list-wiring

**Files:**
- Modify: `backend/app/models.py` (`Batch`-class, rond regel 31-42)
- Modify: `backend/app/database.py` (`ensure_lightweight_migrations`, `batches`-blok, rond regel 60-72)
- Modify: `backend/app/routers/batches.py` (imports rond regel 12; `upload_batch` rond regel 54-81; `list_batches` rond regel 175-182)
- Test: `backend/tests/test_wp_uitsplitsing.py` (uitbreiden)

**Interfaces:**
- Produces: `Batch.geupload_door: str | None` (FK `users.id`); `POST /batches/upload` zet dit veld op de ingelogde gebruiker; elk item in `GET /batches` bevat `"geupload_door_naam": str | None`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_wp_uitsplitsing.py`:

```python
from app.models import User


def test_upload_batch_slaat_ingelogde_gebruiker_op(client, db_session):
    db_session.add(User(id="test-user-id", naam="Test User", email="test@etil.nl",
                        rol="admin", password_hash=""))
    db_session.commit()

    csv_data = "naam\nTestbedrijf\n"
    response = client.post(
        "/batches/upload?naam=upload-tracking-test&jaar=2026",
        files={"file": ("bedrijven.csv", csv_data.encode(), "text/csv")},
    )
    assert response.status_code == 200
    batch_id = response.json()["batch_id"]

    batch = db_session.get(Batch, batch_id)
    assert batch.geupload_door == "test-user-id"


def test_list_batches_toont_geupload_door_naam(client, db_session):
    db_session.add(User(id="test-user-id", naam="Test User", email="test@etil.nl",
                        rol="admin", password_hash=""))
    db_session.commit()

    csv_data = "naam\nTestbedrijf\n"
    upload_response = client.post(
        "/batches/upload?naam=upload-tracking-test-2&jaar=2026",
        files={"file": ("bedrijven.csv", csv_data.encode(), "text/csv")},
    )
    assert upload_response.status_code == 200

    response = client.get("/batches")
    assert response.status_code == 200
    item = next(b for b in response.json() if b["naam"] == "upload-tracking-test-2")
    assert item["geupload_door_naam"] == "Test User"


def test_list_batches_toont_none_zonder_bekende_uploader(client, db_session):
    batch = Batch(naam="batch-zonder-uploader", jaar=2026, totaal=0)
    db_session.add(batch)
    db_session.commit()

    response = client.get("/batches")
    assert response.status_code == 200
    item = next(b for b in response.json() if b["naam"] == "batch-zonder-uploader")
    assert item["geupload_door_naam"] is None
```

Voeg `Batch` toe aan de bestaande import bovenaan het bestand als dat nog niet gebeurd is (controleer de huidige import-regel van `app.models` in dit testbestand).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_wp_uitsplitsing.py::test_upload_batch_slaat_ingelogde_gebruiker_op tests/test_wp_uitsplitsing.py::test_list_batches_toont_geupload_door_naam tests/test_wp_uitsplitsing.py::test_list_batches_toont_none_zonder_bekende_uploader -q`
Expected: FAIL — eerste twee met `AttributeError`/`KeyError` rond `geupload_door`, derde met `KeyError: 'geupload_door_naam'`.

- [ ] **Step 3: Add the field to the Batch model**

In `backend/app/models.py`, in de `Batch`-class, direct na `is_monitoringlijst`:

```python
    is_monitoringlijst: Mapped[bool] = mapped_column(Boolean, default=False)
    geupload_door: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
```

(`ForeignKey` is al geïmporteerd bovenaan het bestand — zie regel 10.)

- [ ] **Step 4: Extend the lightweight migration**

In `backend/app/database.py`, in het `batches`-blok van `ensure_lightweight_migrations()`, direct na het `is_monitoringlijst`-blok:

```python
            if "is_monitoringlijst" not in existing_batches:
                conn.execute(text(
                    "ALTER TABLE batches ADD COLUMN is_monitoringlijst BOOLEAN DEFAULT FALSE"
                ))
            if "geupload_door" not in existing_batches:
                conn.execute(text("ALTER TABLE batches ADD COLUMN geupload_door VARCHAR(36)"))
```

(Dit blok gebruikt losse `ALTER TABLE`-statements i.p.v. het `_add_column_if_missing`-helperpatroon — volg exact deze bestaande stijl, niet de helper uit andere tabelblokken.)

- [ ] **Step 5: Wire upload_batch to set the field**

In `backend/app/routers/batches.py`, voeg `User` toe aan de bestaande import:

```python
from ..models import (AgentResult, Batch, CallListItem, Candidate, ChatSession,
                      Company, Enrichment, JaarverslagMonitoring, PipelineRun,
                      User, VastgoedRecord, WPRecord)
```

Vind de functiesignatuur van `upload_batch`:

```python
async def upload_batch(file: UploadFile, naam: str | None = None,
                       jaar: int | None = None, monitoringlijst: bool = False,
                       db: Session = Depends(get_db)):
```

Vervang door:

```python
async def upload_batch(file: UploadFile, naam: str | None = None,
                       jaar: int | None = None, monitoringlijst: bool = False,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
```

Vind:

```python
    batch = Batch(naam=naam or file.filename, jaar=jaar or datetime.now(timezone.utc).replace(tzinfo=None).year,
                  totaal=len(rows), is_monitoringlijst=monitoringlijst)
```

Vervang door:

```python
    batch = Batch(naam=naam or file.filename, jaar=jaar or datetime.now(timezone.utc).replace(tzinfo=None).year,
                  totaal=len(rows), is_monitoringlijst=monitoringlijst,
                  geupload_door=current_user.id)
```

- [ ] **Step 6: Resolve the uploader name in list_batches**

In `backend/app/routers/batches.py`, vind:

```python
def list_batches(db: Session = Depends(get_db)):
    return [{"id": b.id, "naam": b.naam, "jaar": b.jaar, "status": b.status,
             "totaal": b.totaal, "verwerkt": b.verwerkt,
             "created_at": b.created_at.isoformat() + "Z" if b.created_at else None,
             "completed_at": b.completed_at.isoformat() + "Z" if b.completed_at else None}
            for b in db.query(Batch).filter(Batch.is_monitoringlijst.isnot(True))
                .order_by(Batch.created_at.desc()).all()
            if not _lijkt_monitoringlijst_batch(b)]
```

Vervang door:

```python
def list_batches(db: Session = Depends(get_db)):
    batches = [b for b in db.query(Batch).filter(Batch.is_monitoringlijst.isnot(True))
               .order_by(Batch.created_at.desc()).all()
               if not _lijkt_monitoringlijst_batch(b)]
    uploader_ids = {b.geupload_door for b in batches if b.geupload_door}
    naam_per_id: dict[str, str] = {}
    if uploader_ids:
        for user in db.query(User).filter(User.id.in_(uploader_ids)):
            naam_per_id[user.id] = user.naam
    return [{"id": b.id, "naam": b.naam, "jaar": b.jaar, "status": b.status,
             "totaal": b.totaal, "verwerkt": b.verwerkt,
             "created_at": b.created_at.isoformat() + "Z" if b.created_at else None,
             "completed_at": b.completed_at.isoformat() + "Z" if b.completed_at else None,
             "geupload_door_naam": naam_per_id.get(b.geupload_door)}
            for b in batches]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_wp_uitsplitsing.py::test_upload_batch_slaat_ingelogde_gebruiker_op tests/test_wp_uitsplitsing.py::test_list_batches_toont_geupload_door_naam tests/test_wp_uitsplitsing.py::test_list_batches_toont_none_zonder_bekende_uploader -q`
Expected: PASS (3 passed)

- [ ] **Step 8: Run the full backend suite**

Run: `cd backend && python3 -m pytest tests/ -q`
Expected: 197 passed (194 baseline + 3 nieuwe tests), 0 failed.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models.py backend/app/database.py backend/app/routers/batches.py backend/tests/test_wp_uitsplitsing.py
git commit -m "feat(upload-tracking): sla geupload_door op bij batch-upload"
```

---

### Task 2: Backend — eenmalig backfill-script voor bestaande batches

**Files:**
- Create: `backend/scripts/backfill_geupload_door.py`
- Test: `backend/tests/test_wp_uitsplitsing.py` (uitbreiden)

**Interfaces:**
- Consumes: `Batch.geupload_door` (Task 1), `User`-model.
- Produces: functie `backfill_geupload_door(db: Session, admin_email: str = "admin@etil.nl") -> int` (retourneert het aantal bijgewerkte batches), aanroepbaar als `python -m scripts.backfill_geupload_door` vanuit `backend/`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_wp_uitsplitsing.py`:

```python
def test_backfill_geupload_door_kent_admin_toe_aan_oude_batches(db_session):
    from scripts.backfill_geupload_door import backfill_geupload_door

    db_session.add(User(id="admin-id", naam="Admin", email="admin@etil.nl",
                        rol="admin", password_hash=""))
    oude_batch = Batch(naam="oude-batch", jaar=2026, totaal=0)
    db_session.add(oude_batch)
    db_session.commit()

    aantal = backfill_geupload_door(db_session, admin_email="admin@etil.nl")

    db_session.refresh(oude_batch)
    assert aantal == 1
    assert oude_batch.geupload_door == "admin-id"

    # Idempotent: een tweede aanroep vindt niets meer om bij te werken.
    aantal_tweede_keer = backfill_geupload_door(db_session, admin_email="admin@etil.nl")
    assert aantal_tweede_keer == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_wp_uitsplitsing.py::test_backfill_geupload_door_kent_admin_toe_aan_oude_batches -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.backfill_geupload_door'`

- [ ] **Step 3: Implement the script**

```python
# backend/scripts/backfill_geupload_door.py
"""Eenmalig backfill-script: kent het admin-account toe als geupload_door voor
alle bestaande batches die dat veld nog niet hebben (aangemaakt vóór dit
sub-project). Los van ensure_lightweight_migrations(), want die draait al bij
de allereerste deploy, vóórdat het admin-account via seed_users bestaat.

Gebruik vanuit backend/: python -m scripts.backfill_geupload_door
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Batch, User  # noqa: E402


def backfill_geupload_door(db: Session, admin_email: str = "admin@etil.nl") -> int:
    admin = db.query(User).filter_by(email=admin_email).one_or_none()
    if admin is None:
        print(f"Geen gebruiker gevonden met e-mailadres {admin_email} — niets gedaan.")
        return 0
    batches = db.query(Batch).filter(Batch.geupload_door.is_(None)).all()
    for batch in batches:
        batch.geupload_door = admin.id
    db.commit()
    return len(batches)


def main() -> int:
    db = SessionLocal()
    try:
        aantal = backfill_geupload_door(db)
    finally:
        db.close()
    print(f"Backfill geupload_door: {aantal} batch(es) toegewezen aan admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python3 -m pytest tests/test_wp_uitsplitsing.py::test_backfill_geupload_door_kent_admin_toe_aan_oude_batches -q`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python3 -m pytest tests/ -q`
Expected: 198 passed (197 baseline + 1 nieuwe test), 0 failed.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/backfill_geupload_door.py backend/tests/test_wp_uitsplitsing.py
git commit -m "feat(upload-tracking): eenmalig backfill-script voor bestaande batches"
```

---

### Task 3: Frontend — uploader tonen op het Dashboard

**Files:**
- Modify: `frontend/src/views/Dashboard.jsx`

**Interfaces:**
- Consumes: `batch.geupload_door_naam` (uit Task 1's `GET /batches`-response, al aanwezig op elk item van `batches` na Task 1).

- [ ] **Step 1: Show the uploader name below the timestamp**

Find:

```jsx
                <td className="px-4 py-3 text-sm text-slate-600">
                  <BatchTimestamp created_at={batch.created_at} completed_at={batch.completed_at} />
                </td>
```

Replace with:

```jsx
                <td className="px-4 py-3 text-sm text-slate-600">
                  <BatchTimestamp created_at={batch.created_at} completed_at={batch.completed_at} />
                  <div className="mt-1 text-xs text-slate-500">
                    Geüpload door {batch.geupload_door_naam || "Onbekend"}
                  </div>
                </td>
```

- [ ] **Step 2: Verify the build compiles cleanly**

Run: `export PATH="$HOME/.nvm/versions/node/v20.19.0/bin:$PATH" && cd frontend && npm run build`
Expected: build succeeds, no errors.

- [ ] **Step 3: Manual verification (best-effort — no browser tool available in this environment by default)**

Als er een browser beschikbaar is (of via een lokale Playwright-controle zoals eerder in dit project, met de backend/frontend gestart vanuit de juiste worktree-paden): upload een testbatch, controleer dat "Geüpload door {ingelogde gebruikersnaam}" verschijnt onder de datum, en dat een batch zonder bekende uploader (bijvoorbeeld handmatig in de database aangemaakt zonder `geupload_door`) "Geüpload door Onbekend" toont. Als dit niet uitgevoerd kan worden: rapporteer dit expliciet in plaats van "werkt" te claimen.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Dashboard.jsx
git commit -m "feat(upload-tracking): toon uploader-naam in het batch-overzicht"
```

---

### Task 4: Eindverificatie

**Files:** geen wijzigingen.

- [ ] **Step 1: Full backend suite + validate**

Run: `cd backend && python3 -m pytest tests/ -q && python3 -m scripts.validate`
Expected: 198 passed, 0 failed; validate-streefwaarden ongewijzigd (coverage 100%, MAPE 🟢 0%, kalibratie 100%) — dit sub-project raakt de pipeline/reconciliatie niet.

- [ ] **Step 2: Frontend build check**

Run: `export PATH="$HOME/.nvm/versions/node/v20.19.0/bin:$PATH" && cd frontend && npm run build`
Expected: build slaagt zonder errors.

- [ ] **Step 3: Manual browser walkthrough if possible** — herhaal de checklist uit Task 3 Step 3 end-to-end (bijvoorbeeld via een lokale Playwright-controle met backend/frontend gestart vanuit de juiste worktree-paden, zoals in de twee vorige sub-projecten van dit traject). Als dit niet mogelijk is, rapporteer dit expliciet als open punt.

- [ ] **Step 4: Backfill reminder** — dit sub-project introduceert een handmatige, eenmalige stap die NA de deploy naar productie gedraaid moet worden: `python -m scripts.backfill_geupload_door` (op de productie-database, zelfde manier als eerdere `seed_users`/`seed_monitoringlijst`-aanroepen in dit project — via de publieke Railway Postgres-URL, niet via `railway run` omdat die de interne hostnaam gebruikt die niet vanaf een lokale machine bereikbaar is). Dit is geen onderdeel van de geautomatiseerde taken hierboven — noteer dit expliciet als vervolgstap voor de controller na het mergen/deployen.

- [ ] **Step 5: No commit needed** — dit is een verificatie-only taak. Als een check faalt, ga terug naar de betreffende taak, fix, herrun die taak z'n eigen tests, en herhaal deze taak.

---

## Self-Review Notes

- **Spec coverage:** nieuw `geupload_door`-veld + migratie (Task 1) ✓, `upload_batch` zet het veld (Task 1) ✓, `list_batches` rapporteert `geupload_door_naam` (Task 1) ✓, eenmalig backfill-script voor bestaande batches naar admin (Task 2) ✓, Dashboard toont "Geüpload door {naam}"/"Onbekend" (Task 3) ✓, geen wijziging aan `BatchView.jsx`/reconciliatie/pipeline (geen enkele taak raakt die bestanden aan) ✓.
- **Type consistency:** `geupload_door` is overal `str | None` (model, migratie, response-brondata); `geupload_door_naam` (de resolved naam) wordt consistent zo genoemd in zowel backend-response (Task 1) als frontend-consumptie (Task 3) — geen naamsverschil.
- **Test-FK-subtiliteit expliciet gedocumenteerd:** Task 1's nieuwe tests maken zelf een `User`-rij met `id="test-user-id"` aan vóór het aanroepen van de upload-endpoint, om de foreign-key-constraint in de in-memory testdatabase te respecteren — dit is geen omissie maar een bewust, uitgelegd patroon (zie Global Constraints).
- **Bekende, expliciet benoemde vervolgstap:** de backfill moet ná deploy handmatig gedraaid worden — dit is geen taak binnen deze SDD-uitvoering zelf (Task 4, Step 4 herinnert de controller hieraan), consistent met hoe `seed_users`/`seed_monitoringlijst` ook al buiten de geautomatiseerde pipeline om gedraaid worden in dit project.
