# Jaarverslag-monitoring als hoofddashboard-module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vervang de per-batch jaarverslag-monitoring door één vaste, dashboard-niveau watchlist (206 organisaties, gededupliceerd op cbnr uit `Testbatch Jaarverslagen.xls`), met begrensde gelijktijdigheid en een wekelijkse automatische controle via een ingebouwde scheduler.

**Architecture:** `Batch.is_monitoringlijst` markeert dé actieve watchlist. Nieuwe dashboard-niveau endpoints (`GET /monitoring`, `POST /monitoring/run`) zoeken die batch zelf op — geen `batch_id` meer in de URL. `app/pipeline/monitoring.py` krijgt een concurrency-bounded orchestrator (`asyncio.Semaphore`) die de bestaande, ongewijzigde `check_company_jaarverslag()` per organisatie met een eigen databasesessie aanroept. Een `AsyncIOScheduler` (in-process, geen aparte Railway-service) triggert dezelfde functie wekelijks. Een eenmalig data-prep-script zet de vestiging-niveau brondata om in een organisatie-niveau CSV.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, APScheduler (nieuw), xlrd (nieuw, alleen voor het eenmalige script), pytest + pytest-asyncio, React 19 (frontend, bestaande stack).

## Global Constraints

- Python 3.10+-compatibel, SQLAlchemy 2 Mapped/mapped_column-stijl.
- Externe tekst is onbetrouwbare input — niet van toepassing op dit plan (raakt geen nieuwe LLM-prompts; `check_company_jaarverslag()` zelf blijft ongewijzigd).
- Precies één actieve watchlist tegelijk: het instellen van een nieuwe ontmarkeert automatisch de vorige.
- Tests draaien via `cd backend && python -m pytest tests/ -q`. Er zijn 15 pre-existing, geverifieerd omgevingsgebonden testfouten (bcrypt/passlib-versieconflict in `test_auth.py`, `test_background_run.py`, `test_csv_fallback.py`, `test_review_detail.py`) — niet gerelateerd aan dit werk, niet te fixen als onderdeel van dit plan. Elke taak se testcommando meldt expliciet dat dit de verwachte baseline is.
- Tests die OpenAI aanroepen mogen nooit de echte API raken — dit plan raakt die code niet (alleen `check_company_jaarverslag()`'s AANROEPER verandert, niet de functie zelf), dus dit is hier niet van toepassing behalve in Task 2's hergebruik van de al-bestaande mock-provider-testconventie uit `tests/test_monitoring.py`.
- Geen wijzigingen aan `check_company_jaarverslag()` zelf — alleen hoe/wanneer die aangeroepen wordt.
- Frontend volgt het bestaande "Auditor's Desk"-designsysteem (`DESIGN.md`): geen nieuwe kleuren/componenten, hergebruik van `Shell`/`Metric`/`LabelBadge`/`IconButton`/`Alert`.

---

### Task 1: `Batch.is_monitoringlijst`-vlag + upload-ondersteuning

**Files:**
- Modify: `backend/app/models.py` (Batch-klasse, na regel 40)
- Modify: `backend/app/database.py` (`ensure_lightweight_migrations`, in het `if "batches" in tables:`-blok, na regel 54)
- Modify: `backend/app/routers/batches.py` (`upload_batch`, regels 72-95)
- Test: `backend/tests/test_monitoringlijst_upload.py` (nieuw bestand)

**Interfaces:**
- Produces: `Batch.is_monitoringlijst: bool` (default `False`). `POST /batches/upload` accepteert een nieuwe optionele query-parameter `monitoringlijst: bool = False`; als `True`, wordt de nieuwe batch gemarkeerd en wordt elke eerder gemarkeerde batch automatisch ontmarkeerd.

- [ ] **Step 1: Schrijf de falende test**

Maak `backend/tests/test_monitoringlijst_upload.py` aan:

```python
"""Tests voor de is_monitoringlijst-vlag op Batch en de upload-ondersteuning ervoor."""
from io import BytesIO

from app.models import Batch


def _upload(client, naam: str, monitoringlijst: bool = False):
    params = f"naam={naam}&jaar=2026"
    if monitoringlijst:
        params += "&monitoringlijst=true"
    return client.post(
        f"/batches/upload?{params}",
        files={"file": ("bedrijven.csv", BytesIO(b"naam\nTestbedrijf B.V.\n"), "text/csv")},
    )


def test_upload_met_monitoringlijst_true_zet_de_vlag(client, db_session):
    response = _upload(client, "watchlist-test", monitoringlijst=True)

    assert response.status_code == 200
    batch_id = response.json()["batch_id"]
    batch = db_session.get(Batch, batch_id)
    assert batch.is_monitoringlijst is True


def test_upload_zonder_monitoringlijst_laat_vlag_op_false(client, db_session):
    response = _upload(client, "gewone-batch")

    assert response.status_code == 200
    batch = db_session.get(Batch, response.json()["batch_id"])
    assert batch.is_monitoringlijst is False


def test_nieuwe_monitoringlijst_ontmarkeert_de_vorige(client, db_session):
    eerste = _upload(client, "watchlist-v1", monitoringlijst=True)
    tweede = _upload(client, "watchlist-v2", monitoringlijst=True)

    eerste_batch = db_session.get(Batch, eerste.json()["batch_id"])
    tweede_batch = db_session.get(Batch, tweede.json()["batch_id"])

    assert eerste_batch.is_monitoringlijst is False
    assert tweede_batch.is_monitoringlijst is True
```

- [ ] **Step 2: Run test om te bevestigen dat hij faalt**

Run: `cd backend && python -m pytest tests/test_monitoringlijst_upload.py -v`
Expected: FAIL — `monitoringlijst`-query-parameter bestaat nog niet (FastAPI negeert onbekende query-params stilzwijgend, dus de upload zelf slaagt met status 200, maar `batch.is_monitoringlijst` bestaat nog niet als attribuut op `Batch` → `AttributeError`.

- [ ] **Step 3: Voeg het model-veld toe**

In `backend/app/models.py`, in de `Batch`-klasse, na regel 40 (`completed_at: Mapped[datetime | None] = mapped_column(DateTime)`):

```python
    is_monitoringlijst: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: Voeg de lightweight migration toe**

In `backend/app/database.py`, in het `if "batches" in tables:`-blok (na regel 54, ná de `completed_at`-check, binnen dezelfde `with engine.begin() as conn:`):

```python
            if "is_monitoringlijst" not in existing_batches:
                conn.execute(text(
                    "ALTER TABLE batches ADD COLUMN is_monitoringlijst BOOLEAN DEFAULT FALSE"
                ))
```

- [ ] **Step 5: Werk `upload_batch` bij**

In `backend/app/routers/batches.py`, vervang de `upload_batch`-functie (regels 72-95) door:

```python
@router.post("/upload")
async def upload_batch(file: UploadFile, naam: str | None = None,
                       jaar: int | None = None, monitoringlijst: bool = False,
                       db: Session = Depends(get_db)):
    """CSV-upload -> batch + companies. Verwachte kolommen (flexibel):
    vestigingsnummer, naam, gemeente, adres, sbi_code, cb_er, kvk_nummer.
    monitoringlijst=true markeert deze batch als de actieve jaarverslag-watchlist
    en ontmarkeert automatisch een eventuele vorige watchlist."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows or not CSV_VELDEN.issubset({k.strip().lower() for k in rows[0]}):
        raise HTTPException(422, "CSV mist verplichte kolom 'naam'")

    if monitoringlijst:
        db.query(Batch).filter_by(is_monitoringlijst=True).update(
            {"is_monitoringlijst": False})

    batch = Batch(naam=naam or file.filename, jaar=jaar or datetime.now(timezone.utc).replace(tzinfo=None).year,
                  totaal=len(rows), is_monitoringlijst=monitoringlijst)
    db.add(batch)
    db.flush()
    for r in rows:
        r = {k.strip().lower(): (v.strip() if v else None) for k, v in r.items()}
        db.add(Company(batch_id=batch.id, vestigingsnummer=r.get("vestigingsnummer"),
                       naam=r["naam"], gemeente=r.get("gemeente"), adres=r.get("adres"),
                       sbi_code=r.get("sbi_code"), cb_er=r.get("cb_er"),
                       kvk_nummer=r.get("kvk_nummer"), website_url=r.get("website_url"),
                       telefoonnummer=r.get("telefoonnummer")))
    db.commit()
    return {"batch_id": batch.id, "aantal_companies": len(rows)}
```

- [ ] **Step 6: Run test om te bevestigen dat hij slaagt**

Run: `cd backend && python -m pytest tests/test_monitoringlijst_upload.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Draai de volledige testsuite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 15 pre-existing bcrypt-gerelateerde fouten (ongewijzigd), verder alle tests slagen.

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/models.py app/database.py app/routers/batches.py tests/test_monitoringlijst_upload.py
git commit -m "feat(monitoring): voeg Batch.is_monitoringlijst-vlag en upload-ondersteuning toe"
```

---

### Task 2: Concurrency-bounded batch-processor

**Files:**
- Modify: `backend/app/pipeline/monitoring.py`
- Test: `backend/tests/test_monitoring.py` (bestaand bestand, uitbreiden)

**Interfaces:**
- Consumes: `check_company_jaarverslag(db: Session, company: Company, jaar: int) -> bool` (ongewijzigd, bestaand in dit bestand).
- Produces:
  - `async def check_batch_jaarverslagen(batch_id: str, jaar: int, company_ids: list[str], max_concurrent: int = 8) -> None` — verwerkt de opgegeven organisaties met ten hoogste `max_concurrent` gelijktijdige controles.
  - `def run_monitoring_watchlist_background() -> None` — zoekt zelf de batch met `Batch.is_monitoringlijst=True` op en roept `check_batch_jaarverslagen` daarvoor aan. Stille no-op als er geen watchlist is of die geen organisaties bevat. Dit is de functie die zowel de handmatige trigger (Task 3) als de scheduler (Task 4) aanroepen.

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `backend/tests/test_monitoring.py` (na de bestaande imports, regel 1-7, imports uitbreiden):

```python
import asyncio as _asyncio_voor_lock  # alias voorkomt naamsbotsing met bovenstaande `import asyncio`
```

Voeg toe: (dit gaat na de bestaande `test_check_company_jaarverslag_geen_wijziging_tweede_keer`-functie, aan het eind van het bestand)

```python
def test_check_batch_jaarverslagen_beperkt_gelijktijdigheid(monkeypatch):
    """Verifieert dat check_batch_jaarverslagen ten hoogste max_concurrent
    organisaties tegelijk verwerkt bij een lijst die groter is dan die limiet."""
    from app.pipeline.monitoring import check_batch_jaarverslagen

    db = SessionLocal()
    try:
        batch = Batch(naam="concurrency-test", jaar=2026, totaal=20)
        db.add(batch)
        db.flush()
        company_ids = []
        for i in range(20):
            company = Company(batch_id=batch.id, naam=f"Bedrijf {i}")
            db.add(company)
            db.flush()
            company_ids.append(company.id)
        db.commit()
        batch_id = batch.id

        actief = 0
        max_actief = 0
        lock = _asyncio_voor_lock.Lock()

        async def fake_check_company_jaarverslag(db_arg, company_arg, jaar_arg):
            nonlocal actief, max_actief
            async with lock:
                actief += 1
                max_actief = max(max_actief, actief)
            await _asyncio_voor_lock.sleep(0.02)
            async with lock:
                actief -= 1
            return False

        monkeypatch.setattr(
            "app.pipeline.monitoring.check_company_jaarverslag",
            fake_check_company_jaarverslag,
        )

        asyncio.run(check_batch_jaarverslagen(batch_id, 2026, company_ids, max_concurrent=8))

        assert max_actief == 8
    finally:
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_batch_jaarverslagen_logt_fout_per_organisatie(monkeypatch):
    """Eén falende organisatie mag de rest van de batch niet blokkeren, en moet
    een eigen PipelineRun-foutregel krijgen."""
    from app.models import PipelineRun
    from app.pipeline.monitoring import check_batch_jaarverslagen

    db = SessionLocal()
    try:
        batch = Batch(naam="foutafhandeling-test", jaar=2026, totaal=2)
        db.add(batch)
        db.flush()
        faalt = Company(batch_id=batch.id, naam="Faalt B.V.")
        slaagt = Company(batch_id=batch.id, naam="Slaagt B.V.")
        db.add(faalt)
        db.add(slaagt)
        db.commit()
        batch_id = batch.id

        async def fake_check_company_jaarverslag(db_arg, company_arg, jaar_arg):
            if company_arg.naam == "Faalt B.V.":
                raise RuntimeError("gesimuleerde netwerkfout")
            return False

        monkeypatch.setattr(
            "app.pipeline.monitoring.check_company_jaarverslag",
            fake_check_company_jaarverslag,
        )

        asyncio.run(check_batch_jaarverslagen(batch_id, 2026, [faalt.id, slaagt.id]))

        fout = db.query(PipelineRun).filter_by(company_id=faalt.id, status="error").one()
        assert "gesimuleerde netwerkfout" in fout.error
        assert db.query(PipelineRun).filter_by(company_id=slaagt.id, status="error").count() == 0
    finally:
        db.query(PipelineRun).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_run_monitoring_watchlist_background_zonder_watchlist_is_stille_noop():
    """Geen batch met is_monitoringlijst=True -> geen fout, gewoon niets doen."""
    from app.pipeline.monitoring import run_monitoring_watchlist_background

    db = SessionLocal()
    try:
        db.query(Batch).filter_by(is_monitoringlijst=True).update({"is_monitoringlijst": False})
        db.commit()

        run_monitoring_watchlist_background()  # mag geen exception opgooien
    finally:
        db.close()
```

- [ ] **Step 2: Run tests om te bevestigen dat ze falen**

Run: `cd backend && python -m pytest tests/test_monitoring.py -v -k "check_batch_jaarverslagen or run_monitoring_watchlist_background"`
Expected: FAIL met `ImportError: cannot import name 'check_batch_jaarverslagen' from 'app.pipeline.monitoring'`

- [ ] **Step 3: Schrijf de implementatie**

In `backend/app/pipeline/monitoring.py`, werk de imports bovenaan bij (vervang regels 1-11):

```python
"""Periodieke jaarverslag-monitoring: hergebruikt de bestaande jaarverslag-agent
en reconciliatie-/confidence-logica, maar draait buiten een handmatige batch-run om."""
import asyncio
import time

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import AgentResult, Batch, Candidate, Company, JaarverslagMonitoring, PipelineRun
from ..providers import get_providers
from .confidence import bereken_confidence
from .reconcile import reconcilieer
from .runner import _log, _now
```

Voeg toe aan het eind van `backend/app/pipeline/monitoring.py` (na de bestaande `check_company_jaarverslag`-functie):

```python


async def _check_company_met_eigen_sessie(batch_id: str, company_id: str, jaar: int,
                                          semaphore: asyncio.Semaphore) -> None:
    """Verwerkt één organisatie met een eigen databasesessie, zodat meerdere
    organisaties veilig gelijktijdig verwerkt kunnen worden (een SQLAlchemy
    Session mag niet door meerdere gelijktijdige taken gedeeld worden)."""
    async with semaphore:
        t0 = time.monotonic()
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if company is None:
                return
            await check_company_jaarverslag(db, company, jaar)
        except Exception as exc:
            db.rollback()
            db.add(PipelineRun(batch_id=batch_id, company_id=company_id,
                               stap="jaarverslag_monitoring", status="error",
                               duur_ms=int((time.monotonic() - t0) * 1000),
                               error=str(exc)[:1000]))
            db.commit()
        finally:
            db.close()


async def check_batch_jaarverslagen(batch_id: str, jaar: int, company_ids: list[str],
                                    max_concurrent: int = 8) -> None:
    """Controleert alle opgegeven organisaties op nieuwe jaarverslagen, met ten
    hoogste max_concurrent gelijktijdige controles."""
    semaphore = asyncio.Semaphore(max_concurrent)
    await asyncio.gather(*(
        _check_company_met_eigen_sessie(batch_id, company_id, jaar, semaphore)
        for company_id in company_ids
    ))


def run_monitoring_watchlist_background() -> None:
    """Zoekt de gemarkeerde watchlist-batch op (Batch.is_monitoringlijst=True) en
    controleert alle organisaties daarin gelijktijdig op nieuwe jaarverslagen.
    Geen watchlist ingesteld of leeg -> stille no-op."""
    db = SessionLocal()
    try:
        batch = db.query(Batch).filter_by(is_monitoringlijst=True).order_by(
            Batch.created_at.desc()).first()
        if batch is None:
            return
        batch_id, jaar = batch.id, batch.jaar
        company_ids = [c.id for c in batch.companies]
    finally:
        db.close()

    if not company_ids:
        return
    asyncio.run(check_batch_jaarverslagen(batch_id, jaar, company_ids))
```

- [ ] **Step 4: Run tests om te bevestigen dat ze slagen**

Run: `cd backend && python -m pytest tests/test_monitoring.py -v`
Expected: PASS (7 tests: de 4 bestaande + de 3 nieuwe)

- [ ] **Step 5: Draai de volledige testsuite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 15 pre-existing bcrypt-gerelateerde fouten (ongewijzigd), verder alle tests slagen.

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/pipeline/monitoring.py tests/test_monitoring.py
git commit -m "feat(monitoring): concurrency-bounded batch-processor + watchlist-resolver"
```

---

### Task 3: Dashboard-niveau `/monitoring`-router, oude per-batch endpoints verwijderen

**Files:**
- Create: `backend/app/routers/monitoring.py`
- Modify: `backend/app/routers/batches.py` (verwijderen van oude functie/endpoints)
- Modify: `backend/app/main.py` (nieuwe router registreren)
- Modify: `backend/tests/test_monitoring_endpoint.py` (verouderde tests verwijderen, delete-regressietest behouden)
- Create: `backend/tests/test_monitoring_dashboard.py`

**Interfaces:**
- Consumes: `run_monitoring_watchlist_background()` uit `app/pipeline/monitoring.py` (Task 2).
- Produces: `GET /monitoring` → `{"batch": {"id", "naam", "jaar"} | null, "totaal", "gecontroleerd", "nieuwe_bevindingen", "fouten", "companies": [...]}`. `POST /monitoring/run` → `{"batch_id", "aantal_companies"}` (200) of 404 zonder watchlist.

- [ ] **Step 1: Schrijf de falende tests**

Maak `backend/tests/test_monitoring_dashboard.py` aan:

```python
"""Tests voor de dashboard-niveau /monitoring-endpoints (geen batch_id in de URL)."""
from datetime import datetime, timezone
from io import BytesIO

from app.models import Candidate, Company, JaarverslagMonitoring, PipelineRun
from app.routers import monitoring as monitoring_router


def test_monitoring_status_zonder_watchlist_geeft_lege_staat(client):
    response = client.get("/monitoring")

    assert response.status_code == 200
    assert response.json() == {
        "batch": None, "totaal": 0, "gecontroleerd": 0,
        "nieuwe_bevindingen": 0, "fouten": 0, "companies": [],
    }


def test_monitoring_status_met_actieve_watchlist(client, db_session):
    upload = client.post(
        "/batches/upload?naam=watchlist&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(
            b"naam\nGecontroleerde Organisatie\nNog Niet Gecontroleerd\n"
        ), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    companies = {c.naam: c for c in db_session.query(Company).filter_by(batch_id=batch_id)}
    gecontroleerd = companies["Gecontroleerde Organisatie"]

    nu = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(JaarverslagMonitoring(
        company_id=gecontroleerd.id, laatste_bron_url="https://voorbeeld.test/jaarverslag.pdf",
        laatst_gecontroleerd_op=nu,
    ))
    db_session.add(PipelineRun(batch_id=batch_id, company_id=gecontroleerd.id,
                               stap="jaarverslag_monitoring", status="ok", duur_ms=100))
    db_session.add(Candidate(company_id=gecontroleerd.id, batch_id=batch_id,
                             wp_kandidaat=50, is_schatting=False,
                             confidence_score=0.9, confidence_label="hoog", strategie="auto"))
    db_session.commit()

    response = client.get("/monitoring")

    assert response.status_code == 200
    data = response.json()
    assert data["batch"] == {"id": batch_id, "naam": "watchlist", "jaar": 2026}
    assert data["totaal"] == 2
    assert data["gecontroleerd"] == 1
    assert data["nieuwe_bevindingen"] == 1
    assert data["fouten"] == 0

    per_naam = {c["naam"]: c for c in data["companies"]}
    assert per_naam["Gecontroleerde Organisatie"]["nieuwe_bevinding"] is True
    assert per_naam["Gecontroleerde Organisatie"]["wp_kandidaat"] == 50
    assert per_naam["Nog Niet Gecontroleerd"]["laatst_gecontroleerd_op"] is None


def test_monitoring_run_zonder_watchlist_geeft_404(client):
    response = client.post("/monitoring/run")
    assert response.status_code == 404


def test_monitoring_run_start_achtergrondtaak(client, monkeypatch):
    upload = client.post(
        "/batches/upload?naam=watchlist-run&jaar=2026&monitoringlijst=true",
        files={"file": ("orgs.csv", BytesIO(b"naam\nOrganisatie X\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    gestart = []

    def fake_run_monitoring_watchlist_background() -> None:
        gestart.append(True)

    monkeypatch.setattr(monitoring_router, "run_monitoring_watchlist_background",
                        fake_run_monitoring_watchlist_background)

    response = client.post("/monitoring/run")

    assert response.status_code == 200
    assert response.json() == {"batch_id": batch_id, "aantal_companies": 1}
    assert gestart == [True]
```

Verwijder uit `backend/tests/test_monitoring_endpoint.py` de functies
`test_monitor_batch_start_achtergrondtaak`,
`test_monitoring_status_toont_gecontroleerde_en_ongecontroleerde_vestigingen`, en
`test_monitoring_status_onbekende_batch_geeft_404` (regels 1-92 t/m vóór
`test_batch_met_monitoring_status_kan_verwijderd_worden`) — die testen
endpoints die dit bestand gaat verwijderen. Het bestand wordt na deze
verwijdering:

```python
from datetime import datetime, timezone
from io import BytesIO

from app.models import Company, JaarverslagMonitoring


def test_batch_met_monitoring_status_kan_verwijderd_worden(client, db_session):
    """Regressie: JaarverslagMonitoring-rijen blokkeerden het verwijderen van een
    batch (foreign-key-fout) omdat delete_batch ze niet opruimde vóór de
    company-rijen te verwijderen."""
    upload = client.post(
        "/batches/upload?naam=delete-monitoring-test&jaar=2026",
        files={"file": ("bedrijven.csv", BytesIO(b"naam\nGemonitord B.V.\n"), "text/csv")},
    )
    assert upload.status_code == 200
    batch_id = upload.json()["batch_id"]

    company = db_session.query(Company).filter_by(batch_id=batch_id).one()
    db_session.add(JaarverslagMonitoring(
        company_id=company.id, laatste_bron_url="https://voorbeeld.test/jaarverslag.pdf",
        laatst_gecontroleerd_op=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db_session.commit()

    response = client.delete(f"/batches/{batch_id}")

    assert response.status_code == 200
    assert response.json() == {"deleted": batch_id}
    assert db_session.query(JaarverslagMonitoring).filter_by(company_id=company.id).count() == 0
```

- [ ] **Step 2: Run tests om te bevestigen dat ze falen**

Run: `cd backend && python -m pytest tests/test_monitoring_dashboard.py -v`
Expected: FAIL — `/monitoring` bestaat nog niet (404 op elke aanroep, of `ModuleNotFoundError` bij het importeren van `app.routers.monitoring`).

- [ ] **Step 3: Maak de nieuwe router aan**

Maak `backend/app/routers/monitoring.py` aan:

```python
"""Dashboard-niveau jaarverslag-monitoring: werkt altijd op de ene actieve
watchlist (Batch.is_monitoringlijst=True), zonder batch_id in de URL."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Batch, Company, JaarverslagMonitoring, PipelineRun
from ..pipeline.monitoring import run_monitoring_watchlist_background

router = APIRouter(prefix="/monitoring", tags=["monitoring"], dependencies=[Depends(get_current_user)])


def _actieve_watchlist(db: Session) -> Batch | None:
    return (db.query(Batch).filter_by(is_monitoringlijst=True)
            .order_by(Batch.created_at.desc()).first())


@router.get("")
def monitoring_status(db: Session = Depends(get_db)):
    """Status van de actieve jaarverslag-watchlist. batch=null als er nog geen is ingesteld."""
    batch = _actieve_watchlist(db)
    if batch is None:
        return {"batch": None, "totaal": 0, "gecontroleerd": 0,
                "nieuwe_bevindingen": 0, "fouten": 0, "companies": []}

    companies = db.query(Company).filter_by(batch_id=batch.id).all()
    company_ids = [c.id for c in companies]

    status_map: dict[str, JaarverslagMonitoring] = {}
    if company_ids:
        for status in (db.query(JaarverslagMonitoring)
                       .filter(JaarverslagMonitoring.company_id.in_(company_ids))):
            status_map[status.company_id] = status

    bevindingen: set[str] = set()
    fouten_map: dict[str, str] = {}
    if company_ids:
        for pr in (db.query(PipelineRun)
                   .filter(PipelineRun.company_id.in_(company_ids),
                           PipelineRun.stap == "jaarverslag_monitoring")
                   .order_by(PipelineRun.created_at)):
            if pr.status == "ok":
                bevindingen.add(pr.company_id)
            elif pr.status == "error":
                fouten_map[pr.company_id] = pr.error or "onbekende fout"

    out = []
    for comp in companies:
        status = status_map.get(comp.id)
        cand = comp.candidate
        out.append({
            "company_id": comp.id, "naam": comp.naam, "gemeente": comp.gemeente,
            "laatst_gecontroleerd_op": (status.laatst_gecontroleerd_op.isoformat() + "Z"
                                        if status and status.laatst_gecontroleerd_op else None),
            "laatste_bron_url": status.laatste_bron_url if status else None,
            "nieuwe_bevinding": comp.id in bevindingen,
            "fout": fouten_map.get(comp.id),
            "wp_kandidaat": cand.wp_kandidaat if cand else None,
            "confidence_label": cand.confidence_label if cand else None,
        })

    gecontroleerd = sum(1 for c in out if c["laatst_gecontroleerd_op"])
    return {
        "batch": {"id": batch.id, "naam": batch.naam, "jaar": batch.jaar},
        "totaal": len(companies),
        "gecontroleerd": gecontroleerd,
        "nieuwe_bevindingen": len(bevindingen),
        "fouten": len(fouten_map),
        "companies": out,
    }


@router.post("/run")
def start_monitoring_run(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start handmatig een controle van de actieve watchlist."""
    batch = _actieve_watchlist(db)
    if batch is None:
        raise HTTPException(404, "geen watchlist ingesteld")
    background_tasks.add_task(run_monitoring_watchlist_background)
    return {"batch_id": batch.id, "aantal_companies": len(batch.companies)}
```

- [ ] **Step 4: Registreer de router in `app/main.py`**

In `backend/app/main.py`, wijzig regel 7:

```python
from .routers import auth, batches, chat, chat_admin, review, jaarverslagen, monitoring
```

En voeg na regel 25 (`app.include_router(jaarverslagen.router)`) toe:

```python
app.include_router(monitoring.router)
```

- [ ] **Step 5: Verwijder de oude per-batch code uit `batches.py`**

In `backend/app/routers/batches.py`:
1. Verwijder regel 3 (`import time`) — wordt na deze wijziging nergens meer gebruikt.
2. Verwijder regel 16 (`from ..pipeline.monitoring import check_company_jaarverslag`).
3. Verwijder de functie `run_monitoring_background` (regels 49-69, van `def run_monitoring_background` t/m de bijbehorende `finally: db.close()`).
4. Verwijder het endpoint `POST /{batch_id}/monitor` (regels 118-126).
5. Verwijder het endpoint `GET /{batch_id}/monitoring` (regels 129-182).

De `JaarverslagMonitoring`-import (regel 14) blijft staan — die is nog nodig voor `delete_batch`'s cleanup-query.

- [ ] **Step 6: Run tests om te bevestigen dat ze slagen**

Run: `cd backend && python -m pytest tests/test_monitoring_dashboard.py tests/test_monitoring_endpoint.py -v`
Expected: PASS (4 nieuwe + 1 overgebleven delete-regressietest)

- [ ] **Step 7: Draai de volledige testsuite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 15 pre-existing bcrypt-gerelateerde fouten (ongewijzigd), verder alle tests slagen.

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/routers/monitoring.py app/routers/batches.py app/main.py tests/test_monitoring_dashboard.py tests/test_monitoring_endpoint.py
git commit -m "feat(monitoring): dashboard-niveau /monitoring-router, verwijder oude per-batch endpoints"
```

---

### Task 4: Wekelijkse in-process scheduler

**Files:**
- Create: `backend/app/scheduler.py`
- Modify: `backend/app/main.py` (scheduler starten bij opstarten)
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_scheduler.py` (nieuw bestand)

**Interfaces:**
- Consumes: `run_monitoring_watchlist_background()` uit `app/pipeline/monitoring.py` (Task 2).
- Produces: `start_scheduler() -> None` — registreert en start een wekelijkse cron-taak (maandag 06:00, Europe/Amsterdam). Veilig om meerdere keren aan te roepen (idempotent, vangt fouten af zodat een misluk­king de rest van de app-opstart niet breekt).

- [ ] **Step 1: Voeg de dependency toe**

In `backend/requirements.txt`, voeg toe na de regel `openpyxl>=3.1`:

```
apscheduler>=3.10
```

Installeer 'm lokaal: `cd backend && pip install apscheduler>=3.10`

- [ ] **Step 2: Schrijf de falende test**

Maak `backend/tests/test_scheduler.py` aan:

```python
"""Tests voor de wekelijkse jaarverslag-monitoring-scheduler."""
from app.scheduler import _scheduler, start_scheduler


def test_start_scheduler_registreert_wekelijkse_taak():
    start_scheduler()

    job = _scheduler.get_job("wekelijkse_jaarverslag_monitoring")
    assert job is not None


def test_start_scheduler_is_veilig_dubbel_aan_te_roepen():
    start_scheduler()
    start_scheduler()  # mag geen SchedulerAlreadyRunningError geven

    assert _scheduler.running is True
```

- [ ] **Step 3: Run test om te bevestigen dat hij faalt**

Run: `cd backend && python -m pytest tests/test_scheduler.py -v`
Expected: FAIL met `ModuleNotFoundError: No module named 'app.scheduler'`

- [ ] **Step 4: Maak `app/scheduler.py` aan**

```python
"""Wekelijkse achtergrondplanning voor jaarverslag-monitoring. In-process
(binnen de al-draaiende backend), geen aparte Railway-cron-service nodig."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .pipeline.monitoring import run_monitoring_watchlist_background

_log = logging.getLogger("scheduler")
_scheduler = AsyncIOScheduler(timezone="Europe/Amsterdam")


def start_scheduler() -> None:
    """Registreert en start de wekelijkse jaarverslag-monitoring-taak (maandag
    06:00, Europe/Amsterdam). Veilig om meerdere keren aan te roepen: start
    alleen als de scheduler nog niet draait, en laat een eventuele fout de
    rest van de applicatie-opstart niet breken."""
    if _scheduler.running:
        return
    try:
        _scheduler.add_job(
            run_monitoring_watchlist_background,
            trigger="cron", day_of_week="mon", hour=6, minute=0,
            id="wekelijkse_jaarverslag_monitoring", replace_existing=True,
        )
        _scheduler.start()
    except Exception:
        _log.exception("Kon de jaarverslag-monitoring-scheduler niet starten")
```

- [ ] **Step 5: Run test om te bevestigen dat hij slaagt**

Run: `cd backend && python -m pytest tests/test_scheduler.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Wire de scheduler in `app/main.py`**

In `backend/app/main.py`, voeg toe na regel 7 (de router-imports):

```python
from .scheduler import start_scheduler
```

Voeg toe na de bestaande `@app.on_event("startup")`-functie `reset_stuck_batches` (na regel 89, ná de afsluitende `finally: db.close()`-regel van die functie):

```python


@app.on_event("startup")
def start_jaarverslag_scheduler() -> None:
    start_scheduler()
```

- [ ] **Step 7: Draai de volledige testsuite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 15 pre-existing bcrypt-gerelateerde fouten (ongewijzigd), verder alle tests slagen — inclusief alle tests die de `client`-fixture gebruiken (die triggeren nu ook `start_jaarverslag_scheduler()` bij elke `TestClient`-opstart; de idempotentie-guard in `start_scheduler()` voorkomt dat dit een probleem wordt).

- [ ] **Step 8: Commit**

```bash
cd backend && git add app/scheduler.py app/main.py requirements.txt tests/test_scheduler.py
git commit -m "feat(monitoring): wekelijkse in-process scheduler (maandag 06:00)"
```

---

### Task 5: Data-prep-script voor de watchlist

**Files:**
- Create: `backend/scripts/prepareer_monitoringlijst.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_prepareer_monitoringlijst.py`

**Interfaces:**
- Produces:
  - `organisaties_uit_vestiging_tabblad(rijen: list[dict]) -> list[dict]` — elk dict in `rijen` heeft sleutels `cbnr`, `naam`, `cb-er`; retourneert `[{"naam": str, "cb_er": str | None}, ...]`.
  - `organisaties_uit_organisatie_tabblad(rijen: list[dict]) -> list[dict]` — elk dict heeft sleutels `naam cb-er`, `cbnr`; zelfde retourvorm.
  - `dedupliceer_organisaties(*groepen: list[dict]) -> list[dict]` — combineert en dedupliceert op `cb_er` (indien gezet) of `naam`.
  - `main() -> int` — leest `Testbatch Jaarverslagen.xls`, schrijft `backend/data/jaarverslag_monitoringlijst.csv`.

- [ ] **Step 1: Voeg de dependency toe**

In `backend/requirements.txt`, voeg toe na de regel `apscheduler>=3.10` (uit Task 4):

```
xlrd>=2.0
```

Installeer 'm lokaal: `cd backend && pip install xlrd>=2.0`

- [ ] **Step 2: Schrijf de falende tests**

Maak `backend/tests/test_prepareer_monitoringlijst.py` aan:

```python
"""Tests voor de organisatie-deduplicatie-logica van het watchlist-prep-script.
Gebruikt kleine, ingebakken testfixtures — niet het echte Excel-bestand."""
from scripts.prepareer_monitoringlijst import (
    dedupliceer_organisaties,
    organisaties_uit_organisatie_tabblad,
    organisaties_uit_vestiging_tabblad,
)


def test_groepeert_vestigingen_op_cbnr_en_kiest_cber_naam():
    rijen = [
        {"vestnr": "1", "naam": "Stichting Dichterbij", "cbnr": "001245", "cb-er": "Stichting Dichterbij"},
        {"vestnr": "2", "naam": "Stichting Dichterbij - Locatie A", "cbnr": "001245", "cb-er": ""},
        {"vestnr": "3", "naam": "Stichting Dichterbij - Locatie B", "cbnr": "001245", "cb-er": ""},
    ]

    organisaties = organisaties_uit_vestiging_tabblad(rijen)

    assert organisaties == [{"naam": "Stichting Dichterbij", "cb_er": "001245"}]


def test_losse_vestiging_wordt_eigen_organisatie():
    rijen = [
        {"vestnr": "1", "naam": "Deloitte Tax & Legal B.V.", "cbnr": "000000", "cb-er": ""},
    ]

    organisaties = organisaties_uit_vestiging_tabblad(rijen)

    assert organisaties == [{"naam": "Deloitte Tax & Legal B.V.", "cb_er": None}]


def test_fallback_naar_kortste_naam_zonder_ingevulde_cber():
    rijen = [
        {"vestnr": "1", "naam": "Voorbeeld Groep - Vestiging Noord", "cbnr": "002000", "cb-er": ""},
        {"vestnr": "2", "naam": "Voorbeeld Groep", "cbnr": "002000", "cb-er": ""},
    ]

    organisaties = organisaties_uit_vestiging_tabblad(rijen)

    assert organisaties == [{"naam": "Voorbeeld Groep", "cb_er": "002000"}]


def test_organisatie_tabblad_is_al_organisatie_niveau():
    rijen = [
        {"naam cb-er": "CEVA Logistics", "cbnr": "002441", "vestnr": ""},
        {"naam cb-er": "Losse Stichting X", "cbnr": "000000", "vestnr": ""},
    ]

    organisaties = organisaties_uit_organisatie_tabblad(rijen)

    assert organisaties == [
        {"naam": "CEVA Logistics", "cb_er": "002441"},
        {"naam": "Losse Stichting X", "cb_er": None},
    ]


def test_dedupliceert_over_meerdere_tabbladen_op_cb_er():
    tabblad_1 = [{"naam": "Stichting Dichterbij", "cb_er": "001245"}]
    tabblad_2 = [{"naam": "Stichting Dichterbij", "cb_er": "001245"},
                 {"naam": "CEVA Logistics", "cb_er": "002441"}]

    organisaties = dedupliceer_organisaties(tabblad_1, tabblad_2)

    assert organisaties == [
        {"naam": "Stichting Dichterbij", "cb_er": "001245"},
        {"naam": "CEVA Logistics", "cb_er": "002441"},
    ]


def test_dedupliceert_losse_vestigingen_op_naam():
    tabblad_1 = [{"naam": "Deloitte Tax & Legal B.V.", "cb_er": None}]
    tabblad_2 = [{"naam": "Deloitte Tax & Legal B.V.", "cb_er": None}]

    organisaties = dedupliceer_organisaties(tabblad_1, tabblad_2)

    assert organisaties == [{"naam": "Deloitte Tax & Legal B.V.", "cb_er": None}]
```

- [ ] **Step 3: Run tests om te bevestigen dat ze falen**

Run: `cd backend && python -m pytest tests/test_prepareer_monitoringlijst.py -v`
Expected: FAIL met `ModuleNotFoundError: No module named 'scripts.prepareer_monitoringlijst'`

- [ ] **Step 4: Maak het script aan**

Maak `backend/scripts/prepareer_monitoringlijst.py` aan:

```python
"""Zet de vestiging-niveau brondata (Testbatch Jaarverslagen.xls) om in een
organisatie-niveau CSV voor de jaarverslag-monitoring-watchlist. Een
jaarverslag wordt op organisatieniveau gepubliceerd, niet per vestiging —
vestigingen met dezelfde cbnr horen bij dezelfde organisatie.

Gebruik vanuit backend/: python -m scripts.prepareer_monitoringlijst
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LEEG_CBNR = {"", "0", "000000"}


def organisaties_uit_vestiging_tabblad(rijen: list[dict]) -> list[dict]:
    """rijen: elk dict heeft sleutels 'cbnr', 'naam', 'cb-er' (vestiging-niveau,
    bv. het tabblad 'Alles vorig jaar 16'). Groepeert op cbnr; kiest per groep
    de organisatienaam uit de ingevulde 'cb-er'-kolom, met als terugval de
    kortste vestigingsnaam in de groep. Losse vestigingen (cbnr leeg/000000)
    worden zelf als organisatie behandeld."""
    groepen: dict[str, list[dict]] = {}
    organisaties: list[dict] = []

    for rij in rijen:
        cbnr = str(rij.get("cbnr", "")).strip()
        if cbnr in LEEG_CBNR:
            organisaties.append({"naam": str(rij["naam"]).strip(), "cb_er": None})
        else:
            groepen.setdefault(cbnr, []).append(rij)

    for cbnr, groep_rijen in groepen.items():
        cber_namen = [str(r["cb-er"]).strip() for r in groep_rijen if str(r.get("cb-er", "")).strip()]
        if cber_namen:
            naam = cber_namen[0]
        else:
            naam = min((str(r["naam"]).strip() for r in groep_rijen), key=len)
        organisaties.append({"naam": naam, "cb_er": cbnr})

    return organisaties


def organisaties_uit_organisatie_tabblad(rijen: list[dict]) -> list[dict]:
    """rijen: elk dict heeft sleutels 'naam cb-er', 'cbnr' (al organisatie-niveau,
    bv. het tabblad 'Alles map Jaarverslagen')."""
    organisaties = []
    for rij in rijen:
        cbnr = str(rij.get("cbnr", "")).strip()
        organisaties.append({
            "naam": str(rij["naam cb-er"]).strip(),
            "cb_er": None if cbnr in LEEG_CBNR else cbnr,
        })
    return organisaties


def dedupliceer_organisaties(*groepen: list[dict]) -> list[dict]:
    """Combineert meerdere organisatie-lijsten en dedupliceert: op cb_er als die
    gezet is, anders op naam."""
    gezien: set[tuple[str, str]] = set()
    resultaat = []
    for organisaties in groepen:
        for org in organisaties:
            sleutel = ("cb_er", org["cb_er"]) if org["cb_er"] else ("naam", org["naam"])
            if sleutel in gezien:
                continue
            gezien.add(sleutel)
            resultaat.append(org)
    return resultaat


def _lees_rijen(werkboek, sheetnaam: str) -> list[dict]:
    sh = werkboek.sheet_by_name(sheetnaam)
    header = [str(h).strip().lower() for h in sh.row_values(0)]
    rijen = []
    for r in range(1, sh.nrows):
        waarden = sh.row_values(r)
        if not any(str(v).strip() for v in waarden):
            continue
        rijen.append(dict(zip(header, waarden)))
    return rijen


def main() -> int:
    import xlrd

    bron_pad = Path(__file__).resolve().parents[2] / "Testbatch Jaarverslagen.xls"
    if not bron_pad.exists():
        print(f"Bronbestand niet gevonden: {bron_pad}")
        return 1

    wb = xlrd.open_workbook(str(bron_pad), encoding_override="latin-1")
    vestiging_orgs = organisaties_uit_vestiging_tabblad(_lees_rijen(wb, "Alles vorig jaar 16"))
    tabblad_orgs = organisaties_uit_organisatie_tabblad(_lees_rijen(wb, "Alles map Jaarverslagen"))
    organisaties = dedupliceer_organisaties(vestiging_orgs, tabblad_orgs)

    output_pad = Path(__file__).resolve().parents[1] / "data" / "jaarverslag_monitoringlijst.csv"
    output_pad.parent.mkdir(parents=True, exist_ok=True)
    with open(output_pad, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["naam", "cb_er"])
        writer.writeheader()
        writer.writerows(organisaties)

    print(f"{len(organisaties)} organisaties geschreven naar {output_pad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests om te bevestigen dat ze slagen**

Run: `cd backend && python -m pytest tests/test_prepareer_monitoringlijst.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Draai het script tegen het echte bestand**

Run: `cd backend && python -m scripts.prepareer_monitoringlijst`
Expected: `206 organisaties geschreven naar .../backend/data/jaarverslag_monitoringlijst.csv` (of een vergelijkbaar aantal — het exacte cijfer kan licht afwijken als de brondata na het schrijven van dit plan is bijgewerkt; controleer dat het aantal in de buurt van 206 ligt en niet in de duizenden, wat op een groeperingsfout zou wijzen).

- [ ] **Step 7: Draai de volledige testsuite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 15 pre-existing bcrypt-gerelateerde fouten (ongewijzigd), verder alle tests slagen.

- [ ] **Step 8: Commit**

```bash
cd backend && git add scripts/prepareer_monitoringlijst.py requirements.txt tests/test_prepareer_monitoringlijst.py data/jaarverslag_monitoringlijst.csv
git commit -m "feat(monitoring): data-prep-script voor de organisatie-niveau watchlist-CSV"
```

---

### Task 6: Frontend — dashboard-niveau module

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/views/MonitoringView.jsx` (volledig herschrijven)
- Modify: `frontend/src/views/BatchView.jsx` (Monitoring-knop verwijderen)
- Modify: `frontend/src/views/Dashboard.jsx` (Monitoring-knop toevoegen)
- Modify: `frontend/src/App.jsx` (routing bijwerken)

**Interfaces:**
- Consumes: `GET /monitoring`, `POST /monitoring/run`, `POST /batches/upload?monitoringlijst=true` (Tasks 1 en 3).
- Produces: `api.monitoringStatus()`, `api.monitorRun()`, `api.uploadMonitoringlijst(file)` (geen `batchId`-argumenten meer). `MonitoringView`-props: `{api, user, onLogout, openDashboard, openCompany}` (was `{..., batchId, openBatch, openCompany}`).

Dit is een frontend-only taak zonder geautomatiseerde tests (dit project heeft
geen frontend-testrunner opgezet — verificatie gebeurt via `npm run build` en
handmatige controle, consistent met hoe eerdere frontend-taken in dit project
zijn afgerond).

- [ ] **Step 1: Werk `api.js` bij**

In `frontend/src/api.js`, vervang regels 56-57:

```javascript
    monitorBatch: (id) => request(`/batches/${id}/monitor`, {method: "POST"}),
    monitoringStatus: (id) => request(`/batches/${id}/monitoring`),
```

door:

```javascript
    monitoringStatus: () => request("/monitoring"),
    monitorRun: () => request("/monitoring/run", {method: "POST"}),
    uploadMonitoringlijst: (file) => {
      const body = new FormData();
      body.append("file", file);
      return request("/batches/upload?monitoringlijst=true", {method: "POST", body});
    },
```

- [ ] **Step 2: Herschrijf `MonitoringView.jsx`**

Vervang de volledige inhoud van `frontend/src/views/MonitoringView.jsx` door:

```jsx
import {useEffect, useRef, useState} from "react";
import {AlertTriangle, FileUp, ListChecks, RefreshCw, Sparkles} from "lucide-react";
import {classNames} from "../lib/format.js";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {Metric} from "../components/Metric.jsx";
import {LabelBadge} from "../components/LabelBadge.jsx";

function formatDatumTijd(iso) {
  if (!iso) return null;
  return new Date(iso).toLocaleString("nl-NL", {
    day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function MonitoringView({api, user, onLogout, openDashboard, openCompany}) {
  const fileRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [gestartOm, setGestartOm] = useState(null);

  async function load() {
    const data = await api.monitoringStatus();
    setStatus(data);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 3000);
    return () => window.clearInterval(timer);
  }, []);

  async function nuControleren() {
    setBusy(true);
    setError("");
    try {
      await api.monitorRun();
      setGestartOm(new Date());
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function watchlistUploaden(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await api.uploadMonitoringlijst(file);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  const batch = status?.batch;
  const companies = status?.companies || [];

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title="Jaarverslag-monitoring"
      actions={
        <>
          <IconButton icon={ListChecks} onClick={openDashboard}>Dashboard</IconButton>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={watchlistUploaden} />
          <IconButton icon={FileUp} variant="quiet" onClick={() => fileRef.current?.click()} disabled={busy}>
            {batch ? "Watchlist vervangen" : "Watchlist uploaden"}
          </IconButton>
          {batch ? (
            <IconButton icon={RefreshCw} variant="primary" onClick={nuControleren} disabled={busy}>
              {busy ? "Bezig…" : "Nu controleren"}
            </IconButton>
          ) : null}
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      {!batch ? (
        <div className="rounded-lg border border-dashed border-line bg-white p-8 text-center text-sm text-slate-500">
          Nog geen watchlist ingesteld. Upload een CSV met organisaties om wekelijkse
          jaarverslag-monitoring te starten (elke maandag om 06:00 automatisch, of
          handmatig via "Nu controleren").
        </div>
      ) : (
        <>
          {gestartOm ? (
            <p className="mb-4 text-sm text-slate-500">
              Controle gestart om {formatDatumTijd(gestartOm.toISOString())} — dit kan enkele
              minuten duren; het overzicht ververst vanzelf.
            </p>
          ) : null}
          <div className="mb-4 grid gap-3 md:grid-cols-4">
            <Metric title="Totaal" value={status.totaal} />
            <Metric title="Gecontroleerd" value={`${status.gecontroleerd}/${status.totaal}`} />
            <Metric title="Nieuwe bevindingen" value={
              <span className={classNames(status.nieuwe_bevindingen > 0 && "text-emerald-700")}>
                {status.nieuwe_bevindingen}
              </span>
            } />
            <Metric title="Fouten" value={
              <span className={classNames(status.fouten > 0 && "text-red-600")}>{status.fouten}</span>
            } />
          </div>
          <div className="overflow-hidden rounded-lg border border-line bg-white">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-panel text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">Organisatie</th>
                  <th className="px-4 py-3">Laatst gecontroleerd</th>
                  <th className="px-4 py-3">Laatste bron</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {companies.map((company) => {
                  const klikbaar = company.nieuwe_bevinding;
                  return (
                    <tr
                      key={company.company_id}
                      className={classNames("border-t border-line", klikbaar && "cursor-pointer hover:bg-panel")}
                      onClick={klikbaar ? () => openCompany(batch.id, company.company_id) : undefined}
                    >
                      <td className="px-4 py-3">
                        <div className="font-semibold">{company.naam}</div>
                        <div className="text-xs text-slate-500">{company.gemeente}</div>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {formatDatumTijd(company.laatst_gecontroleerd_op) || (
                          <span className="text-slate-500">Nog niet gecontroleerd</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {company.laatste_bron_url ? (
                          <a
                            href={company.laatste_bron_url}
                            target="_blank" rel="noreferrer"
                            onClick={(event) => event.stopPropagation()}
                            className="text-etil underline"
                          >
                            Bron openen
                          </a>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {company.fout ? (
                          <span className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700" title={company.fout}>
                            <AlertTriangle size={11} />Fout
                          </span>
                        ) : company.nieuwe_bevinding ? (
                          <div className="flex items-center gap-2">
                            <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800">
                              <Sparkles size={11} />Nieuwe bevinding
                            </span>
                            {company.wp_kandidaat != null && <LabelBadge label={company.confidence_label} />}
                          </div>
                        ) : (
                          <span className="text-slate-500">Geen wijziging</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {!companies.length ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-500" colSpan="4">Geen organisaties in de watchlist</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Shell>
  );
}
```

- [ ] **Step 3: Verwijder de Monitoring-knop uit `BatchView.jsx`**

In `frontend/src/views/BatchView.jsx`:
1. Regel 2: verwijder `SearchCheck` uit de lucide-react-import (wordt `import {AlertTriangle, Check, FileDown, ListChecks, MessageSquare, Phone, Play, RefreshCw, Search, Square, Trash2} from "lucide-react";`).
2. Regel 12: verwijder `openMonitoring` uit de props-destructuring (wordt `export function BatchView({api, user, onLogout, batchId, openDashboard, openCompany, openBellijst, openChatSessies}) {`).
3. Regel 124: verwijder de regel `<IconButton icon={SearchCheck} onClick={() => openMonitoring(batchId)} title="Jaarverslag-monitoring">Monitoring</IconButton>` volledig.

- [ ] **Step 4: Voeg de Monitoring-knop toe aan `Dashboard.jsx`**

In `frontend/src/views/Dashboard.jsx`, wijzig regel 2:

```javascript
import {AlertTriangle, BookOpen, FileUp, Play, RefreshCw, SearchCheck, Settings, Square, Trash2} from "lucide-react";
```

Wijzig regel 11 (props-destructuring):

```javascript
export function Dashboard({api, user, onLogout, openBatch, openChatTemplates, openJaarverslagen, openMonitoring}) {
```

Voeg in de `actions`-JSX (na regel 98, ná de `Jaarverslagen`-knop) toe:

```jsx
          <IconButton icon={SearchCheck} variant="quiet" onClick={openMonitoring}>Jaarverslag-monitoring</IconButton>
```

- [ ] **Step 5: Werk de routing in `App.jsx` bij**

In `frontend/src/App.jsx`:
1. Verwijder regel 57 uit de `BatchView`-props (`openMonitoring={(batchId) => setRoute({name: "monitoring", batchId})}`).
2. Vervang het `monitoring`-route-blok (regels 74-85):

```jsx
  if (route.name === "monitoring") {
    return (
      <MonitoringView
        api={api}
        user={user}
        onLogout={logout}
        openDashboard={() => setRoute({name: "dashboard"})}
        openCompany={(batchId, companyId) => setRoute({name: "detail", batchId, companyId})}
      />
    );
  }
```

3. Voeg `openMonitoring` toe aan de `Dashboard`-props onderaan (na regel 154, `openJaarverslagen={() => setRoute({name: "jaarverslagen"})}`):

```jsx
      openMonitoring={() => setRoute({name: "monitoring"})}
```

- [ ] **Step 6: Bouw en verifieer**

Run: `cd frontend && npm run build`
Expected: build slaagt zonder fouten (gebruik Node 20 via `nvm use v20.19.0` als het systeem-Node te oud is — bekend uit eerdere sessies).

- [ ] **Step 7: Commit**

```bash
cd frontend && git add src/api.js src/views/MonitoringView.jsx src/views/BatchView.jsx src/views/Dashboard.jsx src/App.jsx
git commit -m "feat(monitoring): verplaats monitoring-module naar hoofddashboard-niveau"
```

---

## Vervolgstappen (buiten dit plan)

- **Echte watchlist-upload naar productie:** na deployment het data-prep-script draaien (Task 5, Step 6) en de resulterende CSV daadwerkelijk uploaden via het nieuwe scherm ("Watchlist uploaden") of rechtstreeks via `POST /batches/upload?monitoringlijst=true` — dit is een operationele actie, geen code.
- **Handmatige validatie na deploy:** eenmalig "Nu controleren" klikken en de resultaten in het nieuwe dashboardscherm bekijken.
- Scenario 2 (Totaal-WP per CO'er) uit de bredere onderzoeksagent-spec blijft een los vervolgplan.
