# "Vestiging afgewerkt"-vinkje — design

> Sub-project 2 van 6 uit Roy van Zandvoort's feedback (na "Zoeken & filteren",
> reeds gemerged naar main). Elk sub-project krijgt een eigen spec → plan →
> implementatie-cyclus.

## Doel

Reviewers willen zelf kunnen bijhouden welke vestigingen ze al hebben afgehandeld,
onafhankelijk van de automatische pipeline-status. Dit is uitdrukkelijk een
handmatig, los vinkje — niet afgeleid van `Candidate.status` (approved/corrected/
to_chat/to_call), omdat een reviewer een vestiging als "afgewerkt" wil kunnen
markeren voor eigen workflow-tracking, ongeacht de uitkomst van de automatische
verwerking (en zelfs als er nog geen `Candidate` bestaat, bijvoorbeeld bij een
pipeline-fout).

## Scope

Eén nieuw boolean-veld, zichtbaar en aanklikbaar als checkbox in de bedrijvenlijst
binnen een batch (`BatchView.jsx`). Geen filter, geen weergave in de detailpagina,
geen wijziging aan reconciliatie/confidence — puur een reviewer-eigen
markeer-mechanisme.

**Waarom op `Company` en niet op `Candidate`:** `Company.candidate` is
`Candidate | None` — een company krijgt niet altijd een candidate (bijvoorbeeld bij
een pipeline-fout vóór reconciliatie). Het vinkje moet ook dán bruikbaar zijn, dus
het hoort op `Company`, die altijd bestaat vanaf de CSV-upload.

## Architectuur

**Backend:**
- Nieuw veld `Company.afgewerkt: Mapped[bool] = mapped_column(Boolean, default=False)`
  in `backend/app/models.py`.
- Kolom toevoegen via het bestaande lichtgewicht-migratiemechanisme
  (`ensure_lightweight_migrations()` in `backend/app/database.py`,
  `_add_column_if_missing`-patroon), default `false`/`0`.
- `CompanyUpdateBody` (`backend/app/routers/batches.py`, rond regel 371-380) krijgt
  een extra optioneel veld `afgewerkt: bool | None = None`; `_COMPANY_FIELDS`
  (regel 383) krijgt `"afgewerkt"` erbij, zodat de bestaande
  `PATCH /batches/{batch_id}/companies/{company_id}`-logica het automatisch
  meeneemt — geen nieuw endpoint nodig.
- `GET /batches/{batch_id}/companies` (`list_companies`) response krijgt
  `"afgewerkt": comp.afgewerkt` toegevoegd aan de bestaande dict (zelfde additieve
  patroon als de vier zoekvelden uit sub-project 1).

**Frontend (`BatchView.jsx` alleen):**
- Nieuwe kolom "Afgewerkt" in de tabel-header, met een `<input type="checkbox">`
  per rij, `checked={company.afgewerkt}`.
- `onClick`/`onChange` stopt event-propagatie (`event.stopPropagation()`) zodat
  klikken op de checkbox niet ook de rij-klik (`openCompany`) triggert.
- Bij toggelen: direct `api.updateCompany(batchId, companyId, {afgewerkt: !huidige})`
  aanroepen, en de lokale `companies`-state optimistisch bijwerken (checkbox
  reageert meteen, geen wachten op de volgende poll-cyclus van 3 seconden).
- Bij een mislukte PATCH-call: checkbox terugzetten naar de vorige waarde en de
  bestaande `error`-Alert tonen (zelfde foutafhandelingspatroon als de rest van dit
  bestand, bijvoorbeeld `approveAll`/`runBatch`).

## Data flow

Company → PATCH-call werkt direct het `afgewerkt`-veld bij in de database → volgende
`list_companies`-call (elke 3 seconden via de bestaande poll, of direct via de
optimistische update) toont de bijgewerkte staat.

## Testing

- Backend: uitgebreide `pytest`-test op `PATCH /batches/{batch_id}/companies/{company_id}`
  die bevestigt dat `afgewerkt` correct wordt opgeslagen en teruggegeven, en dat het
  ontbreken van dit veld in de request (bestaand gedrag voor andere velden) niets
  wijzigt (regressie op `exclude_unset=True`-gedrag).
- Frontend: geen geautomatiseerde testrunner — verificatie via `npm run build`
  (schoon compileren) plus, waar mogelijk, een handmatige browsercontrole
  (klik-toggle, foutafhandeling bij een mislukte call).
