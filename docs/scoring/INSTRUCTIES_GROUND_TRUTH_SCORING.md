# Instructies: ground truth-scoring voor het Vestigingsregister

## Waar dit voor is

We willen weten hoe goed de AI-pipeline het aantal werkzame personen (WP) per
vestiging vindt. Daarvoor hebben we een lijst met **onafhankelijk, handmatig
geverifieerde** gegevens nodig — dit is geen training van een model, maar een
**meetlat** waarmee we objectief kunnen zien of de pipeline verbetert of
verslechtert bij toekomstige aanpassingen.

Gebruik `ground_truth_template.csv` als startpunt (bevat de 20 bekende
testbedrijven; `wp_werkelijk` is bewust leeg gelaten — zoek dit zelf opnieuw
uit, vertrouw niet op oude aannames).

Voor de bredere v1-meting staan 50 cases in
`backend/data/research_testset_v1.csv` en de afzonderlijke bronlabels in
`backend/data/research_testset_sources_v1.csv`. Het bijbehorende werkboek
`VR_research_testset_v1.xlsx` is de praktische invulversie. Alle regels starten
als `pending_review`; alleen `verified` cases en bronnen tellen mee in de
automatische evaluator `backend/scripts/evaluate_research_testset.py`.

## Wat je per bedrijf invult

| Kolom | Wat je invult |
|---|---|
| `wp_werkelijk` | Het aantal werkzame personen dat je zelf hebt kunnen vaststellen voor déze specifieke vestiging (niet het landelijke/concern-totaal, tenzij het bedrijf maar één vestiging heeft) |
| `wp_bron_url` | De URL van de bron waarmee je dit hebt vastgesteld (team-pagina, jaarverslag, KvK, etc.) |
| `betrouwbaarheid_oordeel` | Zie hieronder — één van drie labels |
| `oordeel_toelichting` | Eén zin: waarom dit oordeel? |
| `gescoord_door` | Jouw naam |
| `scoor_datum` | Datum van onderzoek (bv. 2026-07-10) |

## De 3 betrouwbaarheidslabels

Vraag die je jezelf steeds stelt: **"Als een collega dit getal zonder verder
onderzoek zou overnemen, is dat dan verantwoord?"**

### `eenduidig`
Er is één duidelijke, officiële bron die het getal expliciet noemt vóór déze
vestiging (niet landelijk/concern-breed). Een collega kan dit zonder twijfel
overnemen.

*Voorbeeld: een team-pagina die alle medewerkers van déze locatie met naam en
functie toont (zoals Hallux Podotherapie's vestigingspagina's).*

### `twijfelachtig`
Bronnen spreken elkaar tegen, het getal is afgeleid/geschat (niet letterlijk
vermeld), of het is onduidelijk of het getal voor déze vestiging geldt of voor
het hele concern/land. Dit vraagt een korte navraag bij het bedrijf voordat je
het zou overnemen.

*Voorbeeld: een jaarverslag noemt een totaal medewerkersaantal, maar het
bedrijf heeft meerdere vestigingen en het is niet duidelijk hoeveel daarvan op
déze locatie werken.*

### `onduidelijk`
Geen betrouwbare publieke bron gevonden, of je kon niet met zekerheid
vaststellen welk bedrijf/welke vestiging bedoeld wordt (bijvoorbeeld: meerdere
gelijknamige bedrijven op dezelfde plek). Dit vraagt een telefoontje of
uitgebreider onderzoek.

*Voorbeeld: twee vergelijkbaar genoemde praktijken op hetzelfde
adres/plein, zonder duidelijke bron welke de juiste is (dit gebeurde
daadwerkelijk bij Huisartsenpraktijk Hoensbroek — controleer dit geval dus
extra goed).*

## Belangrijke aandachtspunten

- **Zoek zelf opnieuw uit** — vertrouw niet op eerdere aannames in dit
  project. We hebben vandaag ontdekt dat minstens één bestaand cijfer
  (Huisartsenpraktijk Hoensbroek) zelf twijfelachtig was.
- **WP ≠ FTE.** Als een bron alleen FTE noemt, vermeld dat expliciet in de
  toelichting — reken dit niet zelf om.
- **Let op gelijknamige bedrijven** — vooral bij generieke sectornamen
  (huisartsenpraktijk, kapsalon, fysiotherapie + plaatsnaam) kunnen er
  meerdere, niet-gerelateerde bedrijven op dezelfde straat/plein zitten.
  Controleer adres én telefoonnummer, niet alleen de naam.
- **Voeg gerust meer bedrijven toe** dan de 20 in de template — hoe groter en
  diverser de lijst (grote instellingen, kleine eenpitters, multi-locatie-
  ketens), hoe beter we de pipeline kunnen ijken.

## Wat we hiermee gaan doen

Zodra de lijst is ingevuld, vergelijken we voor elk bedrijf:

- **Pipeline-label** (wat de AI automatisch als 🟢/🟡/🔴 zou geven)
- **Scorer-oordeel** (`eenduidig`/`twijfelachtig`/`onduidelijk`)

Komt "eenduidig" overeen met 🟢, "twijfelachtig" met 🟡 en "onduidelijk" met
🔴? Zo niet, dan weten we precies waar de confidence-berekening nog niet
klopt — en kunnen we dat gericht bijstellen in plaats van op losse
voorbeelden te varen.
