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

> **Correctie na herlezen van de code:** zoeken/filteren werkt in deze applicatie
> overal client-side — bedrijven/uploads worden één keer per batch/lijst opgehaald,
> en gefilterd in de browser met React's `useMemo` (zie `BatchView.jsx:36-40` en
> `JaarverslagenView.jsx:70-74`). Er bestaat geen `q`-zoekparameter op
> `GET /batches/{batch_id}/companies` — dat endpoint kent alleen een `label`-filter
> (`backend/app/routers/batches.py`, functie `list_companies`). De eerdere versie van
> dit ontwerp ging er ten onrechte van uit dat er al een server-side `q`-parameter
> bestond (die verwarring kwam van het aparte, wél bestaande
> `GET /batches/companies/zoeken`-endpoint, dat een andere, batch-overkoepelende
> dropdown-zoekfunctie bedient). Onderstaande punten zijn hierop aangepast.

1. **Bedrijvenzoekbalk binnen een batch uitbreiden** — `list_companies`
   (`GET /batches/{batch_id}/companies`) geeft nu geen `vestigingsnummer`, `cb_er` of
   `kvk_nummer` mee in de response. Backend: deze drie velden toevoegen aan de
   response-dict (puur additief, geen nieuwe query-parameter). Frontend: de
   `text`-string in `BatchView.jsx`'s bestaande `useMemo`-filter (regel 38) uitbreiden
   van `naam + gemeente` naar ook deze drie velden, zodat de bestaande zoekbalk er
   automatisch op matcht.
2. **Sectorfilter binnen een batch** — `sbi_omschrijving` toevoegen aan diezelfde
   `list_companies`-response (zelfde backend-wijziging als punt 1). Frontend: een
   nieuwe `<select>`-dropdown in `BatchView.jsx` met de unieke
   `sbi_omschrijving`-waarden die voorkomen in de al opgehaalde `companies`-lijst
   (client-side afgeleid, geen extra call), **exacte match** als extra voorwaarde in
   de bestaande `filtered`-`useMemo`. Alleen binnen één batch, geen
   batch-overkoepelende sectorzoekfunctie (expliciet buiten scope).
3. **Periodefilter op het batch-overzicht** — `Dashboard.jsx` haalt nu alle batches
   op (`api.batches()`) en sorteert ze client-side op datum, zonder filter. Nieuw:
   een periodefilter-dropdown (Alle / Deze week / Vorige week / Aangepaste range),
   client-side toegepast op de al opgehaalde `batches`-lijst via `Batch.created_at`,
   met **ISO-weekgrenzen** (maandag t/m zondag) voor "Deze week"/"Vorige week" — sluit
   aan bij hoe batches doorgaans per week worden aangeleverd. Geen backend-wijziging
   nodig. Puur filteren, geen visuele groepering per week (expliciet gekozen boven
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

**Backend (`backend/app/routers/batches.py`, functie `list_companies`):**
- De response-dict per bedrijf (rond regel 257-267) krijgt drie extra sleutels:
  `vestigingsnummer`, `cb_er`, `kvk_nummer`, en `sbi_omschrijving` — puur additief,
  geen nieuwe query-parameters, geen wijziging aan de bestaande `label`-filterlogica.
- `list_batches` en `GET /batches/{batch_id}/companies` blijven verder ongewijzigd op
  backend-niveau — het periodefilter en het label-gedrag zijn en blijven client-side
  respectievelijk via de bestaande `label`-parameter.

**Frontend:**
- `BatchView.jsx`: de bestaande `filtered`-`useMemo` (regel 36-40) wordt uitgebreid:
  de `text`-string bevat straks ook `vestigingsnummer`, `cb_er` en `kvk_nummer`; een
  nieuwe `sector`-state plus `<select>`-dropdown (opties = unieke
  `sbi_omschrijving`-waarden uit `companies`) voegt een exacte-match-voorwaarde toe
  aan diezelfde filter.
- `Dashboard.jsx`: een periodefilter-dropdown boven de batchlijst; de al opgehaalde,
  client-side gesorteerde `batches`-array wordt aanvullend gefilterd op
  `created_at` binnen de gekozen periode (ISO-weekgrenzen) — puur client-side, geen
  aanpassing aan `api.batches()`.
- `MonitoringView.jsx`: een nieuw zoek-tekstveld + een `useMemo`-gefilterde
  weergavelijst, exact het patroon dat al in `JaarverslagenView.jsx` staat.

## Data flow

Geen nieuwe databasekolommen, geen nieuwe API-parameters — alle gebruikte velden
(`vestigingsnummer`, `cb_er`, `kvk_nummer`, `sbi_omschrijving`, `Batch.created_at`)
bestaan al op de bestaande modellen. Dit is uitsluitend een uitbreiding van één
response-dict (backend) en client-side filterlogica (frontend), geen migratie nodig.

## Testing

- Backend: één uitgebreide `pytest`-test voor `GET /batches/{batch_id}/companies` die
  bevestigt dat de vier nieuwe velden in elk response-item aanwezig zijn en de juiste
  waarde hebben; bestaand `label`-filtergedrag moet ongewijzigd blijven (regressietest).
- Frontend: geen geautomatiseerde testrunner aanwezig in dit project (zie eerdere
  sessie-bevindingen) — verificatie via `npm run build` (compileert schoon) plus,
  waar mogelijk, een handmatige browsercontrole. Zoals bij eerdere frontend-taken in dit
  project kan een echte visuele controle in dit werkproces niet gegarandeerd worden
  (geen browser-tool beschikbaar) — dat blijft een open, aan een mens over te laten stap.
