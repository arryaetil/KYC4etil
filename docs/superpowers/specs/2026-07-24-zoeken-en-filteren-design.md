# Zoeken & filteren — design

> Sub-project 1 van 6 uit Roy van Zandvoort's feedback (batches beter organiseren,
> vinkje "vestiging afgewerkt", zoeken op CBR/vestigingsnummer, jaarverslag-monitoring
> uitbreiden, zoekbalk/filter bij batch/jaarverslagen, kostenindicatie vooraf,
> media-bronnen bij grote organisaties, koppeling VR uitgesloten). Elk sub-project krijgt
> een eigen spec → plan → implementatie-cyclus.

## Doel

Reviewers (Armina, Anita, Roy, Roger, Stefan) kunnen nu alleen op bedrijfsnaam zoeken
binnen een batch, hebben geen sectorfilter, geen periodefilter op het batch-overzicht, en
geen zoekbalk in de jaarverslag-monitoringlijst. Dit sub-project voegt die vier
zoek-/filtermogelijkheden toe, zonder de reconciliatie-, scoring- of pipelinelogica aan te
raken.

## Scope — vier los toe te voegen filters

1. **Bedrijvenzoekbalk binnen een batch uitbreiden** — nu alleen `Company.naam`
   (`backend/app/routers/batches.py`, de `q`-parameter op
   `GET /batches/{batch_id}/companies`). Wordt een OR-match over `naam`,
   `vestigingsnummer`, `cb_er` en `kvk_nummer`. Eén zoekbalk, geen aparte
   naam/nummer-toggle — de reviewer typt gewoon wat hij weet, en het systeem zoekt
   over alle vier de velden tegelijk. Geen "cijfer vs. tekst"-detectie nodig:
   `vestigingsnummer` (bv. "V001") en `cb_er` (bv. "CB001") zijn alfanumeriek, dus een
   simpele OR-`ilike` over alle vier kolommen dekt alle gevallen.
2. **Sectorfilter binnen een batch** — nieuwe optionele `sector`-parameter op
   dezelfde `GET /batches/{batch_id}/companies`-call, **exacte match** op
   `Company.sbi_omschrijving` (de dropdown-opties zijn toch al precies de bestaande
   waarden uit die batch, dus een vrije-tekst/`ilike`-match voegt niets toe). Alleen
   binnen één batch, geen batch-overkoepelende sectorzoekfunctie (expliciet buiten
   scope, per eerdere keuze in het brainstormgesprek).
3. **Periodefilter op het batch-overzicht** — `Dashboard.jsx` toont nu alle batches in
   één platte, op datum gesorteerde lijst zonder filter. Nieuw: een periodefilter
   (dropdown: Alle / Deze week / Vorige week / Aangepaste range) die filtert op
   `Batch.created_at`, met **ISO-weekgrenzen** (maandag t/m zondag) voor "Deze week"/
   "Vorige week" — sluit aan bij hoe batches doorgaans per week worden aangeleverd.
   Puur filteren, geen visuele groepering per week (expliciet gekozen boven
   groeperen).
4. **Zoekbalk in de jaarverslag-monitoringlijst** — `MonitoringView.jsx` heeft
   momenteel geen enkel zoek-/filterveld. Nieuw: een client-side zoekbalk (zelfde
   patroon als de bestaande `zoek`-state in `JaarverslagenView.jsx`), filtert op
   `naam`/`gemeente` binnen de al opgehaalde watchlist-companies. Geen
   backend-wijziging nodig — de watchlist is typisch klein genoeg voor client-side
   filteren.

**Expliciet buiten scope voor dit sub-project:**
- `JaarverslagenView.jsx` — heeft al een werkende zoekbalk (`zoek`-state,
  `bestandsnaam + company_naam`-match), wordt niet aangeraakt.
- Het "uploads per jaar kunnen zien"-aspect van jaarverslagen (jaar-filter/groepering
  in `JaarverslagenView`) — dat overlapt met sub-project 4 (jaarverslag-monitoring
  uitbreiden) en wordt daar opnieuw beoordeeld, niet hier vooruit geïmplementeerd.
- Elke wijziging aan `reconcile.py`, `confidence`-berekening, of de pipeline zelf.

## Architectuur

**Backend (`backend/app/routers/batches.py`):**
- De query op `GET /batches/{batch_id}/companies` (rond de bestaande `q`-parameter,
  regel ~166) wordt uitgebreid met een `or_(...)`-clausule over de vier velden i.p.v.
  alleen `Company.naam.ilike(...)`.
- Nieuwe optionele query-parameter `sector: str | None = None` op hetzelfde endpoint,
  toegevoegd als extra `.filter(...)` als de parameter is meegegeven.
- `list_batches` (`GET /batches`) krijgt twee nieuwe optionele parameters
  `van: date | None = None`, `tot: date | None = None`, gefilterd op
  `Batch.created_at` als ze zijn meegegeven.

**Frontend:**
- `BatchView.jsx`: de bestaande zoekbalk (die nu al de `q`-parameter naar de backend
  stuurt) hoeft zelf niet te wijzigen — de backend-uitbreiding werkt automatisch mee.
  Nieuw: een `<select>`-dropdown naast de zoekbalk met de unieke
  `sbi_omschrijving`-waarden die voorkomen in de al opgehaalde bedrijvenlijst van deze
  batch (client-side afgeleid, geen extra API-call), die de `sector`-parameter aan de
  bestaande fetch toevoegt.
- `Dashboard.jsx`: een periodefilter-dropdown boven de batchlijst; bij een keuze
  worden `van`/`tot` berekend (client-side, op basis van "vandaag") en meegegeven aan
  `api.batches(...)`.
- `MonitoringView.jsx`: een nieuw zoek-tekstveld + een `useMemo`-gefilterde
  weergavelijst, exact het patroon dat al in `JaarverslagenView.jsx` staat.

## Data flow

Geen nieuwe databasekolommen — alle gebruikte velden (`vestigingsnummer`, `cb_er`,
`kvk_nummer`, `sbi_omschrijving`, `Batch.created_at`) bestaan al. Dit is puur een
uitbreiding van bestaande query's en client-side filterlogica, geen migratie nodig.

## Testing

- Backend: nieuwe/uitgebreide `pytest`-tests voor `GET /batches/{batch_id}/companies`
  (zoeken op elk van de vier velden afzonderlijk, plus de sector-parameter) en voor
  `GET /batches` (periodefilter met `van`/`tot`, en zonder parameters — moet exact het
  huidige gedrag behouden).
- Frontend: geen geautomatiseerde testrunner aanwezig in dit project (zie eerdere
  sessie-bevindingen) — verificatie via `npm run build` (compileert schoon) plus,
  waar mogelijk, een handmatige browsercontrole. Zoals bij eerdere frontend-taken in dit
  project kan een echte visuele controle in dit werkproces niet gegarandeerd worden
  (geen browser-tool beschikbaar) — dat blijft een open, aan een mens over te laten stap.

## Open vragen (voor de plan-fase, geen blokkade voor dit ontwerp)

- Sector-filter: exacte match op `sbi_omschrijving`, of gedeeltelijke `ilike`-match?
  Aanbeveling voor de plan-fase: exacte match uit de dropdown-opties (die toch al
  precies de bestaande waarden zijn), geen vrije tekstinvoer nodig.
- Periodefilter "Deze week"/"Vorige week": ISO-weekgrenzen (maandag t/m zondag) of
  gewoon "laatste 7 dagen" / "7-14 dagen geleden"? Aanbeveling: ISO-weekgrenzen, sluit
  aan bij hoe reviewers waarschijnlijk al in weeknummers denken (batches worden
  doorgaans per week aangeleverd).
