# Bronnenverzameling — proces en datacontract

> Wat er gebeurt tussen "een lijst vestigingen komt binnen" en "een reviewer
> kiest een bron", welke gegevens daarvoor nodig zijn, en waar de grenzen van
> het systeem liggen. Geschreven 24 augustus 2026.

Voor de architectuur en het datamodel: zie [00-overzicht](00-overzicht.md) en
[02-datamodel-en-scoring](02-datamodel-en-scoring.md). Dit document gaat over
het proces en over de afspraken met de aanleverende partij (VVL).

---

## 1. Wat dit systeem doet, en wat niet

KYC4etil zoekt openbare bronnen over het aantal Werkzame Personen bij een
vestiging, ordent ze op sterkte, en legt ze voor aan een mens. Het beheert geen
register en neemt geen registerbeslissingen: elke uitkomst is een bron met een
oordeel van een reviewer erbij.

Twee gevolgen die het hele ontwerp sturen:

- **"Niets gevonden" is geen conclusie.** Een mislukte zoekopdracht, een leeg
  API-tegoed en een organisatie die niets publiceert leveren alle drie geen
  bron op. Het systeem houdt die drie uit elkaar en zegt welke het is.
- **Een getal zonder herkomst bestaat niet.** Elk WP-cijfer draagt zijn bron,
  het citaat waar het staat, en het moment waarop het geldt.

---

## 2. Het proces, stap voor stap

### 2.1 Aanlevering

Een lijst vestigingen komt binnen als CSV of Excel (`POST /batches/upload`).
Alleen `naam` is verplicht; elk ander veld maakt het onderzoek beter. Zie §3
voor wat elk veld doet.

Een lijst is niet af zodra hij geüpload is. Een tweede bestand vult de bestaande
lijst aan in plaats van hem te vervangen, en losse vestigingen kunnen met de
hand worden toegevoegd (`POST /batches/{id}/companies`). Herkenning van
"bestaat deze al" gaat op vestigingsnummer, anders KvK-nummer, anders naam plus
gemeente. Bestaande waarden worden nooit overschreven, alleen aangevuld waar een
veld leeg is.

### 2.2 Website vaststellen

Vóór het onderzoek begint wordt de aangeleverde website gecontroleerd:

| Uitkomst | Wat er gebeurt |
|---|---|
| Antwoordt normaal | Gebruiken |
| Verwijst door naar een ander domein | Nieuw adres gebruiken en vastleggen |
| Foutstatus of onbereikbaar | Loslaten en via Google Places een nieuw adres zoeken |

De aangeleverde URL blijft ongewijzigd op `Company.website_url`; de correctie
komt op `Enrichment`. Zo is achteraf te zien dát de aanlevering achterliep —
bruikbaar voor terugkoppeling aan VVL.

### 2.3 Routes kiezen

Welke routes draaien hangt af van het profiel van de organisatie, afgeleid uit
SBI-code en (als die ontbreekt) uit de naam en SBI-omschrijving:

| Route | Wanneer | Verplicht |
|---|---|---|
| `website` | altijd | ja |
| `document` | altijd | ja — de dragende route |
| `duo` | onderwijs (SBI 85) | ja |
| `digimv` | zorg (SBI 86/87/88) | alleen institutionele zorg |
| `lrk` | kinderopvang (SBI 8891) | nee |
| `team_afspraak` | lokale zorgpraktijk, kapper | nee |
| `media` | altijd | ja |

"Verplicht" betekent: faalt deze route technisch, dan is de run *onvolledig* en
niet *niets gevonden*. Dat onderscheid komt terug in de interface.

De documentroute is verplicht omdat hij het meeste levert: van de kandidaten
met een WP-waarde was een jaarverslag 15× de enige bron binnen 25% van de
waarheid — meer dan alle andere brontypen samen.

### 2.4 Zoeken en lezen

Per route worden zoekopdrachten uitgevoerd (Serper), resultaten opgehaald en
gelezen. Voor jaarverslagen geldt: eerst alle verslagjaren op PDF, pas daarna op
HTML. Een PDF is de sterkere bron — vaste opmaak, en een paginanummer waarmee
het bewijs op de juiste plek opent.

Uit een document wordt het personeelsgetal gelezen door eerst pagina's te
selecteren op vijftien trefwoorden (medewerker, personeel, collega,
arbeidsplaats, workforce, …) en die aan het model voor te leggen.

**Grens:** een gescande PDF zonder tekstlaag levert geen tekst op en dus geen
trefwoordtreffer. Zo'n document komt eruit als "doorzocht, geen WP-getal",
terwijl het cijfer op papier staat. OCR is niet ingebouwd.

### 2.5 Valideren en rangschikken

Elke gevonden bron krijgt:

- een **identiteitsklasse** — gaat dit over dit bedrijf, deze groep, of een
  ander bedrijf?
- een **scope** — geldt het cijfer voor deze vestiging, Limburg, Nederland of
  het hele concern?
- een **ranking** over identiteit, autoriteit, relevantie, actualiteit en bewijs

Gewichten en drempels staan in `app/config.py`, nooit in de pipeline zelf.

Harde afwijzingen: een andere organisatie, een onbruikbare URL, of een
verslagjaar dat afwijkt van het gevraagde jaar. DUO is daarop de uitzondering —
dat meet op 1 oktober en publiceert met vertraging, dus daar is één jaar
achterstand toegestaan.

### 2.6 Beoordelen

De reviewer krijgt per organisatie een samenvattend oordeel en daaronder de
bronkaarten, gesorteerd op sterkte. Elke kaart zegt in vaste regels wat er
bekend is (bedrijf, bereik, bewijs, verslagjaar of peilmoment) en wat de
volgende stap is — afgeleid van de eerste twijfel bij die bron, niet van het
brontype.

Een acceptatie krijgt `juiste_bron_bruikbaar_bewijs`; een afwijzing vereist een
vaste reden.

### 2.7 Uitlevering

`GET /batches/{id}/export.xlsx` levert per organisatie de gekozen bron, met
website, bron-URL, brontype, verslagjaar, peilmoment, waarde, eenheid, scope,
citaat, paginanummer, reviewredencode en beoordelaar.

---

## 3. Datacontract — wat we van VVL nodig hebben

### 3.1 Wat nu wordt ingelezen

| Kolom | Verplicht | Waarvoor | Gevolg als het ontbreekt |
|---|---|---|---|
| `naam` | **ja** | stuurt elke zoekopdracht | rij wordt overgeslagen |
| `vestigingsnummer` | nee | identificatie richting VVL; herkenning bij hernieuwde aanlevering | terugval op KvK of naam+gemeente |
| `gemeente` | nee | zoekopdracht, locatiecontrole, DUO-matching | zoekopdracht wordt vager; gelijknamige vestigingen niet te scheiden |
| `adres` | nee | locatiecontrole, DUO-adresmatching | zwakkere match op onderwijsinstellingen |
| `sbi_code` | nee | kiest de onderzoeksroutes | terugval op naam en SBI-omschrijving |
| `sbi_omschrijving` | nee | idem, als de code ontbreekt | zorg of onderwijs wordt alleen aan de naam herkend |
| `kvk_nummer` | nee | identificatie, locatietelling | geen vestigingstelling |
| `cb_er` | nee | wordt doorgegeven | — |
| `website_url` | nee | startpunt van het onderzoek | Places moet de site zoeken; kost een lookup en lukt niet altijd |
| `telefoonnummer` | nee | wordt doorgegeven | — |

Schrijfwijzen worden herkend: `vestnr` voor `vestigingsnummer`, en
`SBI omschrijving` / `sbi-omschrijving` / `omschrijving` voor
`sbi_omschrijving`.

### 3.2 Wat we graag zouden ontvangen

| Gegeven | Waarvoor | Wat het oplost |
|---|---|---|
| **KvK-status** — actief/opgeheven, uitschrijfdatum | vaststellen of een vestiging nog bestaat | nu niet te beantwoorden zonder KvK-API, waarvoor de sleutel ontbreekt. Alleen het nummer is niet genoeg |
| **Rechtsvorm** | bepaalt of een jaarverslag verplicht is | scheelt zoeken bij organisaties die er per definitie geen publiceren |
| **Peildatum van de aanlevering** | het moment waarop het register de stand wil weten | nu wordt `batch.jaar` als peiljaar gebruikt; `register_peildatum` staat in de config maar wordt nergens uitgelezen |
| **Bekend WP uit een vorige ronde** | vergelijking en signalering | een afwijking van 40% ten opzichte van vorig jaar is nu niet te zien |

### 3.3 Minimale kwaliteit

Met alleen `naam` werkt het systeem, maar slecht: gelijknamige vestigingen zijn
niet te scheiden en de routekeuze valt terug op woorden in de naam.

**Praktisch minimum voor bruikbare kwaliteit:**
`naam` + `vestigingsnummer` + `gemeente` + `sbi_code` (of `sbi_omschrijving`).

**Met `website_url` erbij** wordt het merkbaar beter: dat is het startpunt van
de website- én documentroute, en het bespaart een Places-lookup per organisatie.

Voor een **monitoringlijst** is minder nodig — die doet maar één ding, het
jaarverslag volgen: `naam`, `vestigingsnummer` en `website_url` volstaan.

---

## 4. Externe afhankelijkheden

| Dienst | Waarvoor | Wat er gebeurt als hij uitvalt |
|---|---|---|
| Serper | alle zoekopdrachten | terugval op DuckDuckGo (zwakkere index); melding in de interface |
| OpenAI | tekst lezen, identiteit en scope classificeren | geen extractie mogelijk; melding in de interface |
| Google Places | website zoeken, vestigingen tellen | geen websiteterugval; melding in de interface |
| DUO | onderwijspersoneel | route levert niets |
| DigiMV | zorgjaarverslagen | route levert niets |
| KvK | locatietelling, bestaanscontrole | **sleutel ontbreekt; niet in gebruik** |

Een leeg tegoed, een geweigerde sleutel en een onbereikbare dienst worden uit
elkaar gehouden en per run vastgelegd. De reviewer ziet dat boven de
bronnenlijst staan, want een run zonder Serper levert "niets gevonden" op en dat
is dan een storing, geen uitkomst.

---

## 5. Wat dit systeem niet weet

Eerlijk over de grenzen, zodat niemand er meer uit leest dan erin zit:

- **Een gescande PDF** zonder tekstlaag wordt niet gelezen.
- **FTE is geen WP** en wordt nooit stilzwijgend omgerekend. Staat er alleen een
  FTE-cijfer, dan blijft het WP-getal leeg.
- **Een concerncijfer is geen vestigingscijfer.** Het systeem markeert dat wel,
  maar kan niet uitsplitsen wat de bron niet uitsplitst.
- **Een teampagina is geen personeelsbestand.** Bij grotere organisaties toont
  die de directie of één afdeling.
- **Een peilmoment ontbreekt vaak.** Websites vermelden zelden per wanneer een
  aantal geldt. Waar het jaartal alleen uit de URL komt, staat dat er
  uitdrukkelijk bij.
- **Het systeem beslist niets.** Elke bron gaat langs een mens.
