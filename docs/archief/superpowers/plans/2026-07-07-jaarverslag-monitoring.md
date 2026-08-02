# Periodieke Jaarverslag-Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vestigingen die eerder via jaarverslag zijn ingevuld periodiek (buiten een handmatige batch-run om) opnieuw laten checken op een nieuw jaarverslag, met hergebruik van de bestaande `jaarverslag_agent` en confidence-/reconciliatielogica — resultaten landen zoals altijd in de review-wachtrij.

**Architecture:** Eén nieuwe tabel (`JaarverslagMonitoring`) om per company de laatst bekende jaarverslag-bron en check-datum bij te houden, één nieuwe pipeline-functie (`check_company_jaarverslag`) die de bestaande `jaarverslag_agent`, `reconcilieer()` en `bereken_confidence()` hergebruikt, en één nieuw endpoint (`POST /batches/{batch_id}/monitor`) dat — net als het bestaande `/run`-endpoint — een achtergrondtaak start die sequentieel (niet parallel; zelfde patroon als `run_batch`) door de companies van een batch loopt.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (Mapped/mapped_column), pytest, bestaand provider-patroon (`PROVIDER_MODE=mock|live`).

## Global Constraints

- Python 3.10+-compatibel, SQLAlchemy 2 Mapped/mapped_column-stijl (zie `backend/app/models.py`).
- Geen hardcoded gewichten/drempels in pipeline-code — die staan in `app/config.py` (hier niet van toepassing, geen nieuwe drempels nodig).
- Elke pipeline-stap logt naar `pipeline_runs` via de bestaande `_log()`-helper in `app/pipeline/runner.py`.
- Provider-pattern: nieuwe logica moet zowel met `PROVIDER_MODE=mock` als `live` werken zonder wijziging — hergebruikt de bestaande `get_providers()`-factory, geen nieuwe provider nodig.
- Een proportionele schatting (`is_schatting=True`) mag nooit label 🟢 krijgen — al afgedwongen in `bereken_confidence()`, wordt hier niet opnieuw geïmplementeerd, alleen hergebruikt.
- Tests draaien via `cd backend && python -m pytest tests/ -q`; alle bestaande tests moeten blijven slagen.

---

### Task 1: `JaarverslagMonitoring`-datamodel

**Files:**
- Modify: `backend/app/models.py` (voeg toe na de `JaarverslagChatMessage`-klasse, regel 253)
- Test: `backend/tests/test_monitoring.py` (nieuw bestand)

**Interfaces:**
- Produces: `JaarverslagMonitoring` SQLAlchemy-model met kolommen `id: str`, `company_id: str` (FK naar `companies.id`, uniek), `laatste_bron_url: str | None`, `laatst_gecontroleerd_op: datetime | None`, `created_at: datetime`.

- [ ] **Step 1: Schrijf de falende test**

Maak `backend/tests/test_monitoring.py` aan met:

```python
"""Tests voor periodieke jaarverslag-monitoring."""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import Batch, Company, JaarverslagMonitoring


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _maak_company(db, naam: str = "Okechamp B.V.") -> Company:
    batch = Batch(naam="monitoring-test", jaar=2026, totaal=1)
    db.add(batch)
    db.flush()
    company = Company(batch_id=batch.id, naam=naam, vestigingsnummer="111067624")
    db.add(company)
    db.commit()
    return company


def test_jaarverslag_monitoring_rij_aanmaken_en_opvragen():
    db = SessionLocal()
    try:
        company = _maak_company(db)
        status = JaarverslagMonitoring(
            company_id=company.id,
            laatste_bron_url="https://www.okechamp.nl/jaarverslag-2025.pdf",
            laatst_gecontroleerd_op=_now(),
        )
        db.add(status)
        db.commit()

        opgehaald = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one()
        assert opgehaald.laatste_bron_url == "https://www.okechamp.nl/jaarverslag-2025.pdf"
        assert opgehaald.laatst_gecontroleerd_op is not None
    finally:
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()
```

- [ ] **Step 2: Run test om te bevestigen dat hij faalt**

Run: `cd backend && python -m pytest tests/test_monitoring.py -v`
Expected: FAIL met `ImportError: cannot import name 'JaarverslagMonitoring' from 'app.models'`

- [ ] **Step 3: Voeg het model toe**

In `backend/app/models.py`, direct na de `JaarverslagChatMessage`-klasse (na regel 253):

```python


class JaarverslagMonitoring(Base):
    __tablename__ = "jaarverslag_monitoring"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True, index=True)
    laatste_bron_url: Mapped[str | None] = mapped_column(Text)
    laatst_gecontroleerd_op: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
```

Geen wijziging nodig in `app/main.py` — `Base.metadata.create_all(bind=engine)` (regel 11) maakt de nieuwe tabel automatisch aan; het is een nieuwe tabel, geen kolom op een bestaande tabel, dus `ensure_lightweight_migrations()` hoeft niet aangepast.

- [ ] **Step 4: Run test om te bevestigen dat hij slaagt**

Run: `cd backend && python -m pytest tests/test_monitoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/models.py tests/test_monitoring.py
git commit -m "feat(monitoring): voeg JaarverslagMonitoring-model toe"
```

---

### Task 2: `check_company_jaarverslag()` — nieuw jaarverslag gevonden

**Files:**
- Create: `backend/app/pipeline/monitoring.py`
- Modify: `backend/tests/test_monitoring.py`

**Interfaces:**
- Consumes: `get_providers()` uit `app/providers/__init__.py` (retourneert `tuple[LookupProvider, WebsiteAgent, JaarverslagAgent]`); `reconcilieer(website, jaarverslag, count_nl, count_lb) -> ReconciliatieResultaat` uit `app/pipeline/reconcile.py`; `bereken_confidence(finding, count_nl, count_lb, adres_validated, n_bronnen, bronnen_consistent, peiljaar, is_schatting=False, schatting_penalty=0.0, locatie_bron="mock") -> ScoreResult` uit `app/pipeline/confidence.py`; `_log(db, batch_id, company_id, stap, status, t0, error=None)` uit `app/pipeline/runner.py`; modellen `AgentResult`, `Candidate`, `Company`, `JaarverslagMonitoring` uit `app/models.py`.
- Produces: `async def check_company_jaarverslag(db: Session, company: Company, jaar: int) -> bool` — retourneert `True` als er een nieuw/gewijzigd jaarverslag verwerkt is (nieuwe `AgentResult` aangemaakt, `Candidate` aangemaakt of bijgewerkt als er al één bestond voor deze company+batch), `False` als er niets nieuws was.

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `backend/tests/test_monitoring.py`:

```python
import asyncio

from app.models import AgentResult, Candidate
from app.pipeline.monitoring import check_company_jaarverslag


def test_check_company_jaarverslag_nieuw_gevonden():
    db = SessionLocal()
    try:
        company = _maak_company(db)

        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is True
        ar = db.query(AgentResult).filter_by(company_id=company.id).one()
        assert ar.wp_gevonden == 138
        assert ar.bron_type == "jaarverslag"

        candidate = db.query(Candidate).filter_by(company_id=company.id).one()
        assert candidate.wp_kandidaat == 138

        status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one()
        assert status.laatste_bron_url == "https://www.okechamp.nl/jaarverslag-2025.pdf"
        assert status.laatst_gecontroleerd_op is not None
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()


def test_check_company_jaarverslag_werkt_bestaande_candidate_bij():
    """Een company kan al een candidate hebben (bijv. van een eerdere, volledige
    pipeline-run) — een nieuw gevonden jaarverslag moet die bijwerken, niet dupliceren
    (Candidate heeft een UniqueConstraint op company_id+batch_id)."""
    db = SessionLocal()
    try:
        company = _maak_company(db)
        oude_candidate = Candidate(
            company_id=company.id, batch_id=company.batch_id,
            wp_kandidaat=99, is_schatting=False, confidence_score=0.5,
            confidence_label="middel", status="pending",
        )
        db.add(oude_candidate)
        db.commit()
        oude_candidate_id = oude_candidate.id

        resultaat = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert resultaat is True
        candidaten = db.query(Candidate).filter_by(company_id=company.id).all()
        assert len(candidaten) == 1  # bijgewerkt, niet gedupliceerd
        assert candidaten[0].id == oude_candidate_id  # zelfde rij
        assert candidaten[0].wp_kandidaat == 138  # nieuwe waarde uit het jaarverslag
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()
```

- [ ] **Step 2: Run test om te bevestigen dat hij faalt**

Run: `cd backend && python -m pytest tests/test_monitoring.py::test_check_company_jaarverslag_nieuw_gevonden tests/test_monitoring.py::test_check_company_jaarverslag_werkt_bestaande_candidate_bij -v`
Expected: FAIL met `ModuleNotFoundError: No module named 'app.pipeline.monitoring'`

- [ ] **Step 3: Schrijf de implementatie**

Maak `backend/app/pipeline/monitoring.py` aan:

```python
"""Periodieke jaarverslag-monitoring: hergebruikt de bestaande jaarverslag-agent
en reconciliatie-/confidence-logica, maar draait buiten een handmatige batch-run om."""
import time

from sqlalchemy.orm import Session

from ..models import AgentResult, Candidate, Company, JaarverslagMonitoring
from ..providers import get_providers
from .confidence import bereken_confidence
from .reconcile import reconcilieer
from .runner import _log, _now


async def check_company_jaarverslag(db: Session, company: Company, jaar: int) -> bool:
    """Controleert of er een nieuw jaarverslag is t.o.v. de laatst bekende bron.
    Retourneert True als er een nieuwe/bijgewerkte candidate is aangemaakt."""
    _, _, jaarverslag_agent = get_providers()
    t0 = time.monotonic()

    status = db.query(JaarverslagMonitoring).filter_by(company_id=company.id).one_or_none()
    if status is None:
        status = JaarverslagMonitoring(company_id=company.id)
        db.add(status)

    finding = await jaarverslag_agent.run(company.naam, jaar)
    status.laatst_gecontroleerd_op = _now()

    if finding is None or not finding.wp_gevonden:
        _log(db, company.batch_id, company.id, "jaarverslag_monitoring", "skipped", t0)
        db.commit()
        return False

    if finding.bron_url == status.laatste_bron_url:
        _log(db, company.batch_id, company.id, "jaarverslag_monitoring", "skipped", t0)
        db.commit()
        return False

    status.laatste_bron_url = finding.bron_url

    ar = AgentResult(
        company_id=company.id, batch_id=company.batch_id, agent_type="jaarverslag",
        wp_gevonden=finding.wp_gevonden, wp_context=finding.context,
        is_limburg_specifiek=finding.is_limburg_specifiek, is_fte=finding.is_fte,
        peilmoment=finding.peilmoment, bron_url=finding.bron_url,
        bron_type=finding.bron_type, llm_zekerheid=finding.zekerheid,
        raw_output=finding.raw or None,
    )
    db.add(ar)
    db.flush()

    rec = reconcilieer(None, finding, None, None)
    score = bereken_confidence(
        rec.finding, None, None, adres_validated=False,
        n_bronnen=rec.n_bronnen, bronnen_consistent=rec.bronnen_consistent,
        peiljaar=jaar, is_schatting=rec.is_schatting,
        schatting_penalty=rec.schatting_penalty, locatie_bron="mock",
    )

    bestaande_candidate = db.query(Candidate).filter_by(
        company_id=company.id, batch_id=company.batch_id).one_or_none()
    if bestaande_candidate is not None:
        bestaande_candidate.wp_kandidaat = rec.wp_kandidaat
        bestaande_candidate.is_schatting = rec.is_schatting
        bestaande_candidate.gekozen_agent_result = ar.id
        bestaande_candidate.reconciliatie_reden = rec.reden
        bestaande_candidate.confidence_score = score.score
        bestaande_candidate.confidence_label = score.label
        bestaande_candidate.score_breakdown = score.breakdown
        bestaande_candidate.status = "pending"
    else:
        db.add(Candidate(
            company_id=company.id, batch_id=company.batch_id,
            wp_kandidaat=rec.wp_kandidaat, is_schatting=rec.is_schatting,
            gekozen_agent_result=ar.id, reconciliatie_reden=rec.reden,
            confidence_score=score.score, confidence_label=score.label,
            score_breakdown=score.breakdown, strategie="auto",
        ))

    _log(db, company.batch_id, company.id, "jaarverslag_monitoring", "ok", t0)
    db.commit()
    return True
```

`_now` bestaat nog niet als herbruikbare functie in `app/pipeline/runner.py` — die berekent `datetime.now(timezone.utc).replace(tzinfo=None)` nu inline in `run_batch` (regel 166). Voeg 'm eerst toe als module-level functie, zodat `monitoring.py` 'm kan importeren:

In `backend/app/pipeline/runner.py`, voeg toe na de imports (na regel 12), vóór `_log`:

```python
def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

En vervang in `run_batch` (regel 166) `datetime.now(timezone.utc).replace(tzinfo=None)` door `_now()`.

- [ ] **Step 4: Run test om te bevestigen dat hij slaagt**

Run: `cd backend && python -m pytest tests/test_monitoring.py -v`
Expected: PASS (3 tests: `test_jaarverslag_monitoring_rij_aanmaken_en_opvragen`,
`test_check_company_jaarverslag_nieuw_gevonden`,
`test_check_company_jaarverslag_werkt_bestaande_candidate_bij`)

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/pipeline/monitoring.py app/pipeline/runner.py tests/test_monitoring.py
git commit -m "feat(monitoring): check_company_jaarverslag herkent en verwerkt een nieuw jaarverslag"
```

---

### Task 3: `check_company_jaarverslag()` — geen wijziging bij dezelfde bron

**Files:**
- Modify: `backend/tests/test_monitoring.py`

**Interfaces:**
- Consumes: `check_company_jaarverslag` uit Task 2 (ongewijzigd signatuur).

- [ ] **Step 1: Schrijf de falende test**

Voeg toe aan `backend/tests/test_monitoring.py`:

```python
def test_check_company_jaarverslag_geen_wijziging_tweede_keer():
    db = SessionLocal()
    try:
        company = _maak_company(db)

        eerste = asyncio.run(check_company_jaarverslag(db, company, 2026))
        tweede = asyncio.run(check_company_jaarverslag(db, company, 2026))

        assert eerste is True
        assert tweede is False
        # Geen dubbele AgentResult/Candidate aangemaakt op de tweede, ongewijzigde check
        assert db.query(AgentResult).filter_by(company_id=company.id).count() == 1
        assert db.query(Candidate).filter_by(company_id=company.id).count() == 1
    finally:
        db.query(Candidate).delete()
        db.query(AgentResult).delete()
        db.query(JaarverslagMonitoring).delete()
        db.query(Company).delete()
        db.query(Batch).delete()
        db.commit()
        db.close()
```

- [ ] **Step 2: Run test om te bevestigen dat hij slaagt of faalt**

Run: `cd backend && python -m pytest tests/test_monitoring.py::test_check_company_jaarverslag_geen_wijziging_tweede_keer -v`
Expected: PASS — de implementatie uit Task 2 dekt dit gedrag al (vergelijking `finding.bron_url == status.laatste_bron_url`). Als deze test faalt, controleer of Task 2 stap 3 exact is overgenomen.

- [ ] **Step 3: Commit**

```bash
cd backend && git add tests/test_monitoring.py
git commit -m "test(monitoring): dek idempotent gedrag bij ongewijzigd jaarverslag"
```

---

### Task 4: Endpoint om een monitoring-run te starten voor een batch

**Files:**
- Modify: `backend/app/routers/batches.py`
- Create: `backend/tests/test_monitoring_endpoint.py`

**Interfaces:**
- Consumes: `check_company_jaarverslag` uit `app/pipeline/monitoring.py`; bestaand patroon `run_batch_background`/`SessionLocal` uit `app/routers/batches.py`.
- Produces: `def run_monitoring_background(batch_id: str) -> None` (module-level in `batches.py`, zelfde patroon als `run_batch_background`); endpoint `POST /batches/{batch_id}/monitor` die 200 retourneert met `{"batch_id": ..., "aantal_companies": ...}` en de achtergrondtaak plant.

- [ ] **Step 1: Schrijf de falende test**

Maak `backend/tests/test_monitoring_endpoint.py` aan:

```python
from datetime import datetime

from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import SessionLocal
from app.main import app
from app.models import Batch, Company, User
from app.routers import batches as batches_router


client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    email = f"monitor-{datetime.utcnow().timestamp()}@example.test"
    password = "TestWachtwoord2026!"
    db = SessionLocal()
    try:
        db.add(User(naam="Monitor Tester", email=email, rol="reviewer",
                    password_hash=hash_password(password)))
        db.commit()
    finally:
        db.close()

    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_monitor_batch_start_achtergrondtaak(monkeypatch):
    db = SessionLocal()
    try:
        batch = Batch(naam="monitor-endpoint-test", jaar=2026, totaal=1)
        db.add(batch)
        db.flush()
        db.add(Company(batch_id=batch.id, naam="Okechamp B.V."))
        db.commit()
        batch_id = batch.id
    finally:
        db.close()

    scheduled = []

    def fake_run_monitoring_background(batch_id_arg: str) -> None:
        scheduled.append(batch_id_arg)

    monkeypatch.setattr(batches_router, "run_monitoring_background", fake_run_monitoring_background)

    response = client.post(f"/batches/{batch_id}/monitor", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json() == {"batch_id": batch_id, "aantal_companies": 1}
    assert scheduled == [batch_id]
```

- [ ] **Step 2: Run test om te bevestigen dat hij faalt**

Run: `cd backend && python -m pytest tests/test_monitoring_endpoint.py -v`
Expected: FAIL met 404 (endpoint bestaat nog niet) of `AttributeError: module 'app.routers.batches' has no attribute 'run_monitoring_background'`

- [ ] **Step 3: Implementeer de achtergrondtaak en het endpoint**

In `backend/app/routers/batches.py`, voeg de import toe (na regel 14, `from ..pipeline.runner import run_batch, verwerk_company`):

```python
from ..pipeline.monitoring import check_company_jaarverslag
```

Voeg na de bestaande `run_single_background`-functie (na regel 39) toe:

```python
def run_monitoring_background(batch_id: str) -> None:
    db = SessionLocal()
    try:
        batch = db.get(Batch, batch_id)
        if batch is None:
            return
        for company in batch.companies:
            t0 = time.monotonic()
            try:
                asyncio.run(check_company_jaarverslag(db, company, batch.jaar))
                db.commit()
            except Exception as exc:
                db.rollback()
                db.add(PipelineRun(batch_id=batch.id, company_id=company.id,
                                   stap="jaarverslag_monitoring", status="error",
                                   duur_ms=int((time.monotonic() - t0) * 1000),
                                   error=str(exc)[:1000]))
                db.commit()
    finally:
        db.close()
```

`time` is al geïmporteerd in `runner.py` maar niet in `batches.py` — voeg toe aan de imports bovenaan `batches.py` (na regel 3, `import asyncio`):

```python
import time
```

Voeg het endpoint toe, direct na `start_batch` (na regel 88):

```python
@router.post("/{batch_id}/monitor")
async def monitor_batch(batch_id: str, background_tasks: BackgroundTasks,
                        db: Session = Depends(get_db)):
    """Start een periodieke jaarverslag-controle voor alle companies in deze batch,
    los van de reguliere pipeline-status (batch.status/verwerkt blijven ongewijzigd)."""
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(404, f"batch {batch_id} bestaat niet")
    background_tasks.add_task(run_monitoring_background, batch.id)
    return {"batch_id": batch.id, "aantal_companies": len(batch.companies)}
```

- [ ] **Step 4: Run test om te bevestigen dat hij slaagt**

Run: `cd backend && python -m pytest tests/test_monitoring_endpoint.py -v`
Expected: PASS

- [ ] **Step 5: Draai de volledige testsuite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: alle tests slagen (bestaande + de 4 nieuwe uit dit plan)

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/routers/batches.py tests/test_monitoring_endpoint.py
git commit -m "feat(monitoring): endpoint POST /batches/{batch_id}/monitor start jaarverslag-controle"
```

---

## Vervolgstappen (buiten dit plan)

- **Scheduling in productie:** dit plan levert het endpoint; het *periodiek* aanroepen ervan (bijv.
  wekelijks) is een Railway-cron-configuratie (of vergelijkbaar), geen applicatiecode — apart te regelen
  bij deployment, niet onderdeel van dit plan.
- **Import van de monitoringlijst:** hergebruikt het bestaande `POST /batches/upload`-endpoint
  (CSV met minimaal een `naam`-kolom) om een dedicated "monitoring"-batch aan te maken uit
  `Testbatch Jaarverslagen.xls` (eenmalig xls→csv-conversie, geen productiecode).
- Scenario 2 (totaal-WP per CO'er) en scenario 3 (adaptieve website-agent) uit de spec zijn losse
  vervolgplannen, niet in dit plan meegenomen.
