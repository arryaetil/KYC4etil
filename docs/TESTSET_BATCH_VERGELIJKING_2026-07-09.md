# Testset batchvergelijking 2026-07-09

## Context

Na de evidence/source-validation wijzigingen is de backend gedeployed naar Railway en is een nieuwe productie-testset batch gedraaid.

Oude batch:

- naam: `testset`
- id: `fc200a31-5ed6-4c8a-8767-d93fe5422a95`
- periode: 2026-07-09 13:08-13:23 UTC
- labels: 16 hoog, 0 middel, 4 laag

Nieuwe batch:

- naam: `testset-evidence-eval`
- id: `68b2213e-b01b-4523-8f79-8fba603d8876`
- periode: 2026-07-09 14:54-15:06 UTC
- labels: 14 hoog, 0 middel, 6 laag

## Hoofdconclusie

De nieuwe run vermindert catastrofale foutpositieven. Vooral wrong-company en wrong-scope gevallen worden nu lager gezet of krijgen geen kandidaat. Dat is precies het belangrijkste doel van deze fase.

De run laat ook zien dat de volgende kwaliteitslaag nodig is: scope-classificatie en source-type filtering voor media/search-resultaten. Sommige foutieve mediaresultaten krijgen nog steeds te veel vertrouwen.

## Belangrijkste verbeteringen

### Salon Handmade

Oude batch:

- kandidaat: 6.158
- label: hoog
- bron: Heijmans PDF
- fouttype: wrong-company

Nieuwe batch:

- kandidaat: geen
- label: laag
- reden: geen bron gevonden

Beoordeling: sterke verbetering. Liever geen kandidaat dan een hoog-confidence getal van een ander bedrijf.

### Jumbo Supermarkten B.V. - Filiaal

Oude batch:

- kandidaat: 44.485
- label: hoog
- bron: landelijk Jumbo jaarverslag
- fouttype: wrong-scope

Nieuwe batch:

- kandidaat: geen
- label: laag
- reden: niet-Limburg-specifieke bron en geen vestigingscount bekend

Beoordeling: sterke verbetering. De bron is niet wrong-company, maar wel ongeschikt als direct filiaal-WP.

### Stichting Pergamijn

Oude batch:

- kandidaat: 1.000
- label: hoog

Nieuwe batch:

- kandidaat: geen
- label: laag
- extra bron: LinkedIn 582 medewerkers, puur informatief

Beoordeling: verbetering qua kandidaatveiligheid. Extra bron moet reviewer-informatie blijven totdat gekalibreerd.

## Regressies / open problemen

### Zuyderland Medisch en Zorgconcern

Oude batch:

- kandidaat: 10.000
- label: hoog

Nieuwe batch:

- kandidaat: 2.235
- label: hoog
- bron: website homepage
- context lijkt onvoldoende inhoudelijk onderbouwd

Beoordeling: regressie. Dit vraagt om betere context-verificatie: de geciteerde tekst moet het getal letterlijk ondersteunen.

### Huisartsenpraktijk Hoensbroek

Oude batch:

- kandidaat: 22

Nieuwe batch:

- kandidaat: 24

Beoordeling: lichte regressie t.o.v. verwachte testsetwaarde 13. Waarschijnlijk telt de agent alle personen op de medewerkerspagina, niet alleen de gewenste WP-definitie of peilmomentscope.

### BAM

Oude batch:

- kandidaat: 13.200
- label: laag

Nieuwe batch:

- kandidaat: 6.500
- label: hoog
- bron: Wikipedia/media
- context noemt "650 voltijdsbanen", maar kandidaat is 6.500

Beoordeling: numerieke extractie-glitch plus media te hoog vertrouwd. Media/Wikipedia mag niet hoog worden zonder officiële bron of scope-match.

### IKEA Heerlen

Oude batch:

- kandidaat: 4
- label: hoog

Nieuwe batch:

- kandidaat: 4
- label: hoog
- bron: IKEA jobs URL
- fouttype: vacature-aantal in plaats van medewerkers

Beoordeling: open probleem. Zoekresultaten met `/jobs/`, `vacature`, `careers` moeten niet als WP-bron gebruikt worden tenzij de tekst expliciet medewerkers/headcount noemt.

## Samenvattende telling

Vergelijking oude vs nieuwe productie-batch:

- improved: 1
- regressed: 2
- same_correct: 3
- same_error: 11
- new_missing: 3
- new_found: 0

Deze telling is streng op numerieke correctheid. Kwalitatief is de belangrijkste winst dat drie gevaarlijke hoog-confidence foutpositieven zijn gedegradeerd naar laag/geen kandidaat.

## Aanbevolen volgende stap

Implementeer nu geen extra search-agent. De volgende stap is deterministic hardening:

1. Scope-classificatie expliciet maken (`vestiging`, `limburg`, `nederland`, `concern`, `unknown`).
2. Candidate hard gates uitbreiden:
   - media zonder expliciete headcount-context nooit hoog;
   - vacature/job/careers pagina's niet als WP-bron gebruiken;
   - context moet het gekozen getal letterlijk of aantoonbaar ondersteunen;
   - concern/nederland-scope niet direct branch-WP.
3. Reviewer extra bronnen blijven informatief.
4. Daarna pas opnieuw batch vergelijken.
