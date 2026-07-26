# Onderzoekswerkbank — frontend-herontwerp — Design

**Project:** Vestigingsregister AI Platform (Etil / Provincie Limburg)
**Datum:** 2026-07-26
**Status:** Goedgekeurd uitgangspunt voor implementatie
**Scope:** frontend, informatiearchitectuur en UX. Backend blijft ongewijzigd.

---

## 1. Aanleiding en doel

De huidige frontend presenteert twee volledig gescheiden systemen door elkaar
heen: de oude WP-pipeline (`agent_results`, confidence-labels 🟢/🟡/🔴) en de
nieuwe autonome onderzoeksagent (`BronKandidaat`, identiteit/scope-classificatie).
`BatchView` toont letterlijk "Research-WP" naast "Legacy-WP" naast
"Vergelijking", wat de reviewer dwingt twee mentale modellen tegelijk te
hanteren.

Doel van dit herontwerp: **één interface, gebouwd rond bronnenonderzoek en het
presenteren van bewijs.** De onderzoeker moet per organisatie snel kunnen
beoordelen of een gevonden bron klopt, en met één handeling bij de exacte
bewijsplek in die bron uitkomen.

Dit document beschrijft alleen de frontend. Alle benodigde data wordt al door
bestaande endpoints geleverd (`/research/*`, `/monitoring`, `/batches/*`).

---

## 2. Analyse van de huidige frontend

### 2.1 Navigatie

`Shell.jsx` biedt geen persistente navigatie — het is een header plus een
actiebalk die elke view zelf vult. Die actiebalk mengt navigatie (Dashboard,
Monitoring, Jaarverslagen, Chat-templates) met acties (Export, Bellijst,
Verwijderen). Met zeven bereikbare views zonder hiërarchie is oriëntatie
lastig.

### 2.2 Twee pipelines in één tabel

`BatchView` combineert kolommen uit beide systemen. Alle legacy-elementen
(`legacy_wp`, `vergelijking`, "Legacy vergelijken", `runLegacyBatch`) vervallen
in het nieuwe ontwerp.

### 2.3 Bewijspresentatie is de zwakste plek

- PDF-deeplinking bestáát (`lib/pdfViewerLink.js`, pagina + zoekterm-highlight
  via pdf.js) maar wordt alleen in de legacy `DetailView` gebruikt — niet in
  `ResearchPanel`, waar een bron een kale `target="_blank"`-link is.
- Voor HTML-bronnen bestaat geen sprong-naar-bewijs.
- Het bewijscitaat staat als losse tekst onder de link, zonder functionele
  relatie tot die link.

### 2.4 Review zit opgesloten in een tabelrij

`ResearchPanel` wordt inline in een tabelrij uitgeklapt (`colSpan={8}`). Er kan
één organisatie tegelijk open staan, de beschikbare breedte is die van de
tabel, en er is geen deeplink naar een organisatie in review. Met de sinds
kort verhoogde kandidatenlimiet (8 in plaats van 3) wordt dat een lange, smalle
kolom zonder vergelijkingsruimte.

### 2.5 Inconsistent vocabulaire

Drie woordenboeken naast elkaar: `StatusPill` (legacy- én researchstatussen),
`LABELS` (`hoog/middel/laag` → "Eenduidig/Twijfelachtig/Onduidelijk", het
legacy confidence-label) en de researchvelden (`ranking_score`,
`identity_class`, `scope_class`, candidate-`status`). Rauwe enum-waarden
(`exact_entity`, `vestiging`) lekken onvertaald naar het scherm.

### 2.6 Wat behouden blijft

De backend levert alles wat nodig is; er is geen backendwijziging vereist. De
diagnostiek bij een mislukte zoektocht (zoekresultaten, onderzochte pagina's,
afwijsredenen, website-resolutie) is functioneel sterk en verdient een betere
plek dan de huidige `<details>`-wegstopper.

---

## 3. Informatiearchitectuur

### 3.1 Twee modules

```
┌─ Etil ──────────────────────────────────────────────┐
│  Onderzoek   ·   Jaarverslagenmonitoring     [Arrya] │
└─────────────────────────────────────────────────────┘
```

Permanente navigatie met exact twee bestemmingen. Acties staan bij het object
waar ze betrekking op hebben (batch-acties bij de batch, bronacties bij de
bron), niet in een globale balk.

### 3.2 Module Onderzoek — twee toestanden

**Geen batch gekozen** → batchoverzicht: uploaden, voortgang per batch,
exporteren, verwijderen.

**Batch gekozen** → de werkbank (§4). Terug via breadcrumb.

### 3.3 Wat wordt verborgen

De volgende views blijven als code bestaan maar zijn niet meer via navigatie
bereikbaar: `BatchView`, `DetailView`, `BellijstView`, `ChatSessiesView`,
`ChatTemplatesView`, `JaarverslagenView`, `JaarverslagChatView`, `Dashboard`.
De publieke chat-route (`?chat=<token>`) blijft ongewijzigd werken, want die
wordt buiten de applicatie om gedeeld.

Backend-endpoints worden niet aangeraakt. Verwijderen van nu ongebruikte
endpoints is een aparte, latere afweging.

---

## 4. De werkbank (drie panelen)

```
┌──────────┬──────────────────────┬───────────────┐
│ ONDERZOEK│  Okechamp B.V.       │  BEWIJS       │
│          │  Horst aan de Maas   │               │
│ ● Okecha…│                      │ ┌───────────┐ │
│   Mondri…│  ① okechamp.eu       │ │ PDF  p.14 │ │
│   Jumbo  │    Officiële website │ │ ▓▓▓▓▓▓▓▓▓ │ │
│   Zuyder…│    "47 medewerkers   │ │ highlight │ │
│   Pergam…│     in dienst"       │ │           │ │
│          │    Vestiging · 2025  │ └───────────┘ │
│ ─────────│    [Bewijs] [✓] [✕]  │               │
│ 12 open  │  ② jaarverslag.pdf   │               │
└──────────┴──────────────────────┴───────────────┘
```

### 4.1 Linkerpaneel — organisaties

Compacte lijst met per regel: naam, gemeente, en één statusindicatie (§5.1).
Zoekveld en statusfilter bovenaan; onderaan een telling (`12 te beoordelen ·
4 klaar`). De actieve organisatie is gemarkeerd. Klikken wisselt het midden- en
rechterpaneel zonder paginanavigatie.

### 4.2 Middenpaneel — bronkandidaten

Kopregel met organisatienaam, gemeente en identificerende gegevens
(vestigingsnummer, KvK). Daaronder de kandidaten als kaarten, in de volgorde
die de ranking bepaalt, genummerd ①②③ — **zonder het ruwe scorepercentage.**

Per kaart, in volgorde van belang:

1. **Bronsoort en herkomst** — "Officiële website · okechamp.eu"
2. **Het bewijscitaat** — typografisch het zwaarste element van de kaart
3. **Twee signalen**: identiteit en bereik (§5.2)
4. **WP-getal en eenheid**, met FTE expliciet als waarschuwing
5. **Jaar** — als relatie ("verslagjaar 2025", en een waarschuwing wanneer dat
   afwijkt van het gevraagde jaar), niet als drie losse datumvelden
6. **Acties**: `Bewijs bekijken` · `Accepteren` · `Afwijzen`

Onderaan het paneel: een knop om een bron handmatig toe te voegen, en een knop
om het onderzoek (opnieuw) te starten.

Detailinformatie die niet in de kaart hoort — `score_breakdown`,
`validaties`, ruwe classificatiewaarden — komt achter één uitklapbare
"Onderbouwing"-regel per kaart.

### 4.3 Rechterpaneel — bewijs

Toont het bewijs van de geselecteerde kandidaat. Leeg bij eerste opening, met
een korte uitleg. Zie §6.

### 4.4 Responsief gedrag

| Breedte | Gedrag |
|---|---|
| ≥ 1280px | Drie panelen naast elkaar |
| 1024–1280px | Linkerpaneel klapt in tot een smalle strook; uitschuifbaar |
| < 1024px | Eén paneel tegelijk, met terugnavigatie tussen lijst → kandidaten → bewijs |

---

## 5. Nieuw status- en labelvocabulaire

Het huidige stelsel wordt vervangen door twee assen, corresponderend met de
twee vragen die een onderzoeker daadwerkelijk stelt.

### 5.1 Per organisatie — proceststatus

| Nieuw label | Afgeleid uit |
|---|---|
| Nog niet onderzocht | geen `research_status` |
| Onderzoek loopt | `research_status = running` / `pending` |
| **Te beoordelen** | `research_resultaat_status = review_nodig` |
| Bron gekozen | `research_review_status = geaccepteerd` |
| Geen bron gevonden | `research_resultaat_status = niet_gevonden` |
| Mislukt | `research_status = error` |

### 5.2 Per bron — twee losse signalen

Eén samengestelde score wordt vervangen door twee orthogonale uitspraken.

**Identiteit** (uit `identity_class`):

| Nieuw label | Enum |
|---|---|
| Dit bedrijf | `exact_entity` |
| Zelfde groep | `same_brand_or_group` |
| Mogelijk ander bedrijf | `possible_match` / `unknown` |
| Ander bedrijf | `mismatch` |

**Bereik** (uit `scope_class`):

| Nieuw label | Enum |
|---|---|
| Deze vestiging | `vestiging` |
| Limburg | `limburg` |
| Heel Nederland | `nederland` |
| Hele concern | `concern` |
| Onbekend bereik | `unknown` |

**Waarschuwingsvlaggen**, alleen getoond wanneer ze gelden:
`FTE — geen WP` (`eenheid = fte`), `Ander verslagjaar`
(`verslagjaar ≠ gevraagd_jaar`), `Geen getal gevonden` (`wp_gevonden = null`),
plus de bestaande `waarschuwingen`-lijst in leesbare vorm.

### 5.3 Wat verdwijnt

`LABELS` ("Eenduidig/Twijfelachtig/Onduidelijk"), het percentage
"68.75% rankingscore", de legacy-statussen in `StatusPill` (`to_chat`,
`to_call`, `corrected`), en elke onvertaalde enum in de UI.

### 5.4 Kleurdiscipline

Standaard neutraal. Amber uitsluitend voor "controleer dit". Rood uitsluitend
voor identiteitsmismatch of fout. Groen uitsluitend voor een gekozen bron.

Er komen géén groene "in orde"-badges: de **afwezigheid** van een
waarschuwing is het signaal. Dit is wat de interface rustig houdt en zorgt dat
een amber of rood label daadwerkelijk opvalt.

---

## 6. Bewijspresentatie

Eén paneel, twee technische paden.

### 6.1 PDF-bronnen — ingebed

Hergebruikt de bestaande `buildPdfViewerUrl` (pdf.js met `page=` en
`search=`-highlight) in een iframe binnen het rechterpaneel. Dit werkt al en
verandert niet.

### 6.2 HTML-bronnen — nieuwe tab met tekstfragment

De browser kan zelf naar een tekstpassage scrollen en die markeren via een
Text Fragment (`#:~:text=…`). Beperking: browsers passen tekstfragmenten
**niet** toe binnen een iframe, en een cross-origin pagina kan niet door ons
worden gemanipuleerd. Een HTML-bron kan dus niet ingebed worden getoond mét
highlight.

Gekozen oplossing: voor HTML-bronnen toont het rechterpaneel het citaat groot
en leesbaar, met de bronmetadata, en één knop `Open bron op de bewijsplek ↗`
die een nieuw tabblad opent op de tekstfragment-URL. De gebruiker landt daarmee
alsnog rechtstreeks bij het bewijs, gemarkeerd door de browser zelf.

Wanneer het citaat ontbreekt, valt de knop terug op de kale bron-URL.

### 6.3 Koppeling citaat ↔ bewijs

Het citaat in de kaart en het citaat in het bewijspaneel worden visueel als
hetzelfde object gepresenteerd, zodat duidelijk is dat het paneel het bewijs
van díe kaart toont.

---

## 7. Diagnostiek

Alleen tonen wanneer de agent niets bruikbaars vond
(`resultaat_status = niet_gevonden`). Dan verschijnt in het middenpaneel, in
plaats van een lege lijst, een blok dat verklaart waaróm:

- hoeveel zoekresultaten, onderzochte pagina's, gelezen en afgewezen documenten
- de afwijsredenen in leesbare vorm
- of de officiële website is opgelost, en via welke bron
- de afgewezen bronnen met hun reden, uitklapbaar

Bij een geslaagde run is diagnostiek niet zichtbaar.

---

## 8. Module Jaarverslagenmonitoring

Behoudt zijn huidige functie (vaste watchlist, periodieke controle, "Nu
controleren") maar krijgt de nieuwe vormgeving, het nieuwe vocabulaire en
dezelfde werkbank voor het beoordelen van een organisatie — zodat er precies
één manier is om een bron te controleren, in beide modules.

---

## 9. Bestandsstructuur

**Nieuw:**

| Bestand | Verantwoordelijkheid |
|---|---|
| `components/AppShell.jsx` | Header met tweemodule-navigatie |
| `views/OnderzoekView.jsx` | Werkbank: coördineert de drie panelen |
| `views/BatchesView.jsx` | Batchoverzicht (uploaden, voortgang, export) |
| `components/onderzoek/OrganisatieLijst.jsx` | Linkerpaneel |
| `components/onderzoek/KandidatenPaneel.jsx` | Middenpaneel |
| `components/onderzoek/BronKaart.jsx` | Eén bronkandidaat |
| `components/onderzoek/BewijsPaneel.jsx` | Rechterpaneel |
| `components/onderzoek/Diagnostiek.jsx` | Verklaring bij niets gevonden |
| `lib/onderzoekLabels.js` | Het vocabulaire uit §5, één bron van waarheid |
| `lib/evidenceLink.js` | Tekstfragment-URL voor HTML-bronnen |

**Gewijzigd:** `App.jsx` (routing teruggebracht tot twee modules),
`MonitoringView.jsx` (nieuwe vormgeving en vocabulaire).

**Verborgen, niet verwijderd:** `Dashboard.jsx`, `BatchView.jsx`,
`DetailView.jsx`, `BellijstView.jsx`, `ChatSessiesView.jsx`,
`ChatTemplatesView.jsx`, `JaarverslagenView.jsx`, `JaarverslagChatView.jsx`,
`ResearchPanel.jsx`, `lib/zekerheid.js`, `lib/constants.js`.

---

## 10. Bewust buiten scope

- **Backendwijzigingen.** Alle benodigde data komt uit bestaande endpoints.
- **Verwijderen van backend-endpoints** die door het verbergen van views
  ongebruikt raken.
- **Toetsenbordnavigatie** (bijvoorbeeld ↑/↓ door de lijst, sneltoetsen voor
  accepteren/afwijzen). Waardevol voor doorlopend reviewen, maar een aparte
  toevoeging nadat de basisinterface staat.
- **Deeplinks per organisatie.** De huidige applicatie heeft geen router; dat
  introduceren is een eigen wijziging.

---

## 11. Succescriteria

1. Er zijn precies twee bestemmingen in de navigatie.
2. Geen enkel legacy-element (Legacy-WP, Vergelijking, chat-templates,
   losse jaarverslagen-tab) is nog bereikbaar.
3. Geen rauwe enum-waarde of ruw scorepercentage is zichtbaar in de UI.
4. Vanaf een bronkandidaat kom je met één handeling bij het bewijs: PDF
   ingebed op de juiste pagina met highlight, HTML in een nieuw tabblad op het
   tekstfragment.
5. Wisselen tussen organisaties gebeurt zonder de context van het onderzoek
   te verliezen.
6. Diagnostiek is zichtbaar wanneer er niets gevonden is, en anders niet.
