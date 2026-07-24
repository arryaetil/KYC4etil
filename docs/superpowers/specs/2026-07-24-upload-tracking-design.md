# Upload-tracking — design

> Sub-project 3 van 6 uit Roy van Zandvoort's feedback (na "Zoeken & filteren" en
> het "vestiging afgewerkt"-vinkje, beide al gemerged naar main). Elk sub-project
> krijgt een eigen spec → plan → implementatie-cyclus.

## Doel

Zien welke gebruiker een batch heeft geüpload, zichtbaar in het batch-overzicht op
het Dashboard.

## Scope

**Backend:**
- Nieuw veld `Batch.geupload_door: str | None` (FK naar `users.id`) — zelfde patroon
  als het bestaande `Candidate.goedgekeurd_door`/`WPRecord.goedgekeurd_door`.
- `POST /batches/upload` (`backend/app/routers/batches.py`, `upload_batch`) krijgt
  een `current_user=Depends(get_current_user)`-parameter (de router heeft
  `get_current_user` al als afhankelijkheid op routerniveau voor authenticatie, maar
  deze specifieke handler injecteert het object nog niet) en zet
  `geupload_door=current_user.id` op de nieuwe `Batch`.
- `GET /batches` (`list_batches`) response krijgt `geupload_door_naam` erbij: een
  join naar `User.naam` op basis van `geupload_door`, `None` als er geen uploader
  bekend is.
- **Eenmalig backfill-script**, niet onderdeel van `ensure_lightweight_migrations()`:
  `backend/scripts/backfill_geupload_door.py`, zelfde structuur/aanroeppatroon als
  het bestaande `scripts/seed_monitoringlijst.py` (`python -m scripts.backfill_geupload_door`
  vanuit `backend/`). Zet voor elke bestaande `Batch` met `geupload_door IS NULL`
  de waarde naar het admin-account (`admin@etil.nl`). **Waarom een apart script en
  niet in de schema-migratie zelf:** `ensure_lightweight_migrations()` draait bij
  elke app-start, óók bij de allereerste deploy vóórdat `python -m scripts.seed_users`
  ooit is gedraaid — op dat moment bestaat het admin-account nog niet. Een
  schema-migratie mag geen aanname doen over datawaarden die nog niet bestaan; het
  backfill-script wordt bewust apart, handmatig gedraaid ná deploy (net als
  `seed_users`/`seed_monitoringlijst` dat al zijn).

**Frontend (`Dashboard.jsx` alleen):**
- Extra regel/kolom in de batchlijst: "Geüpload door {naam}", of "Onbekend" als
  `geupload_door_naam` leeg is (verwacht na de backfill niet meer voor te komen,
  maar blijft een nette fallback voor toekomstige edge cases, bijvoorbeeld een
  verwijderde gebruiker).

**Expliciet buiten scope:**
- Geen wijziging aan `BatchView.jsx` — uploader-info staat alleen op het Dashboard.
- Geen wijziging aan reconciliatie/confidence/pipeline-logica.
- Geen wijziging aan de bellijst/jaarverslag-monitoring-subsystemen.

## Architectuur

**Backend:**
- `backend/app/models.py`: `Batch`-class krijgt
  `geupload_door: Mapped[str | None] = mapped_column(ForeignKey("users.id"))`.
- `backend/app/database.py`: `ensure_lightweight_migrations()` — nieuwe kolom
  toevoegen aan de `batches`-tabel via het bestaande `_add_column_if_missing`-patroon
  (`VARCHAR(36)`, geen DEFAULT nodig — nullable is hier prima, het backfill-script
  vult de waarde apart).
- `backend/app/routers/batches.py`: `upload_batch` krijgt de
  `current_user`-parameter en zet `geupload_door=current_user.id` bij het aanmaken
  van de `Batch`. `list_batches` doet een left join / aparte lookup naar `User` om
  `geupload_door_naam` te bepalen.
- `backend/scripts/backfill_geupload_door.py`: nieuw, eenmalig, idempotent script
  (draait het twee keer, dan verandert er de tweede keer niets — want het filtert
  al op `geupload_door IS NULL`).

**Frontend:**
- `frontend/src/views/Dashboard.jsx`: in de bestaande batch-rij (waar nu al
  `BatchTimestamp` de aanmaakdatum toont) een extra regel met de uploader-naam.

## Data flow

Nieuwe batch → `upload_batch` zet `geupload_door` bij het aanmaken → `list_batches`
resolvet dit naar een naam bij het ophalen → Dashboard toont het. Voor bestaande
batches: het backfill-script vult `geupload_door` retroactief met het admin-account
→ vanaf dat moment identiek gedrag als nieuwe batches.

## Testing

- Backend: nieuwe `pytest`-test op `POST /batches/upload` die bevestigt dat
  `geupload_door` correct wordt gezet op de ingelogde gebruiker; nieuwe test op
  `GET /batches` die bevestigt dat `geupload_door_naam` correct wordt gerapporteerd
  (en `None` is als er geen uploader bekend is). Los, kort testje voor het
  backfill-script zelf (bevestigt dat het idempotent is en alleen `NULL`-waarden
  aanpast).
- Frontend: geen geautomatiseerde testrunner — verificatie via `npm run build` plus,
  waar mogelijk, een handmatige browsercontrole (dit project heeft inmiddels een
  werkende lokale Playwright-opzet gebruikt in de twee vorige sub-projecten — dezelfde
  aanpak kan hier herhaald worden voor een echte visuele verificatie in plaats van
  alleen een build-check).
