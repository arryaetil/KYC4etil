---
name: Vestigingsregister Review-interface
description: Interne review-tool voor WP-data van het Vestigingsregister — Etil Research Group / Provincie Limburg
colors:
  etil-blue: "#1e3a5f"
  etil-red: "#C8102E"
  signal-ochre: "#b45309"
  ink: "#1f2933"
  line: "#d7dde5"
  panel: "#f7f8fa"
  page-bg: "#eef2f5"
  slate-500: "#64748b"
  slate-700: "#334155"
  emerald-500: "#10b981"
  emerald-50: "#ecfdf5"
  emerald-800: "#065f46"
  amber-500: "#f59e0b"
  amber-50: "#fffbeb"
  amber-800: "#92400e"
  red-500: "#ef4444"
  red-50: "#fef2f2"
  red-800: "#991b1b"
typography:
  headline:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.2
  title:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter, Segoe UI, Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.3
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  full: "9999px"
spacing:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
components:
  button-primary:
    backgroundColor: "{colors.etil-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    height: "40px"
    padding: "0 12px"
  button-primary-hover:
    backgroundColor: "{colors.etil-blue}"
  button-danger:
    backgroundColor: "#dc2626"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    height: "40px"
  button-default:
    backgroundColor: "#ffffff"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "40px"
  label-badge-groen:
    backgroundColor: "{colors.emerald-50}"
    textColor: "{colors.emerald-800}"
    rounded: "{rounded.md}"
  label-badge-geel:
    backgroundColor: "{colors.amber-50}"
    textColor: "{colors.amber-800}"
    rounded: "{rounded.md}"
  label-badge-rood:
    backgroundColor: "{colors.red-50}"
    textColor: "{colors.red-800}"
    rounded: "{rounded.md}"
  input-field:
    backgroundColor: "#ffffff"
    rounded: "{rounded.md}"
    height: "44px"
    padding: "0 12px"
---

# Design System: Vestigingsregister Review-interface

## 1. Overview

**Creative North Star: "The Auditor's Desk"**

Dit systeem is de digitale werkplek van een precieze, betrouwbare controleur — niet een marketingvitrine. Reviewers (Armina, Anita) verwerken hier tientallen tot honderden bedrijfsrecords per dag: uploaden, wachten, oordelen, corrigeren, goedkeuren. Elke visuele keuze dient dat tempo en die zorgvuldigheid. Het Etil-rood (`#C8102E`) in de header en het Etil-blauw (`#1e3a5f`) als actie-kleur zijn de enige plekken waar merkidentiteit zich mag laten zien; de rest van het scherm is neutraal grijs-wit zodat status- en confidence-signalen (groen/geel/rood) altijd de opvallendste kleur op het scherm zijn — nooit concurrerend met decoratie.

Dit systeem wijst expliciet af: gradient-tekst, glassmorphism, identieke kaartgrids, kleine uppercase "eyebrows" boven elke sectie, hero-metric-templates. Dit is geen marketingpagina — geen decoratieve elementen die niet aan het reviewwerk bijdragen.

**Key Characteristics:**
- Vlak, neutraal canvas (`page-bg` #eef2f5, `panel` #f7f8fa) met precies twee merk-accenten: rood (header) en `etil`-blauw (primaire actie).
- Statuskleuren (emerald/amber/red) zijn functioneel gereserveerd voor confidence-labels (🟢🟡🔴) en foutmeldingen — nooit decoratief elders gebruikt.
- Compacte, dichte tabellen en lijsten; witruimte is functioneel (scheiding van record-rijen), niet esthetisch opgevuld.
- Vrijwel platte elevatie: `shadow-sm` als enige noemenswaardige schaduw, gereserveerd voor kaarten/panelen die boven de pagina-achtergrond "zweven".

## 2. Colors

Een bewust smal palet: één merkrood, één merkblauw, neutrale grijzen voor 90% van het scherm, en drie functionele statuskleuren die uitsluitend confidence/foutstatus communiceren.

### Primary
- **Etil-blauw** (#1e3a5f): primaire actieknop-kleur (`bg-etil`), primaire link-kleur, actieve tab-indicatoren. Draagt "dit is de aanbevolen actie".

### Secondary
- **Etil-rood** (#C8102E): uitsluitend in de app-header (merkidentiteit), nooit als knop- of statuskleur elders. Het rood van de organisatie, niet van "foutmelding" — foutmeldingen gebruiken een apart, zachter rood (#dc2626 / red-50/800).

### Tertiary
- **Signal-ochre** (#b45309): gereserveerd token voor secundaire nadruk/waarschuwing buiten de standaard amber-statuskleur; momenteel licht gebruikt, houd het voor toekomstige "let op"-accenten los van de amber-confidence-kleur.

### Neutral
- **Ink** (#1f2933): primaire tekstkleur op witte/panel-achtergronden.
- **Line** (#d7dde5): alle randen — kaarten, tabellen, inputs, dividers. Eén randkleur voor het hele systeem.
- **Panel** (#f7f8fa): sectie-achtergronden, tabelheaders, hover-states op rijen.
- **Page background** (#eef2f5): de basisachtergrond van elk scherm.
- **Slate-500 / Slate-700**: secundaire/tertiaire tekst (metadata, tijdstempels, labels) — nooit voor primaire leestekst.

### Named Rules
**The Two-Accent Rule.** Precies twee merkkleuren zijn toegestaan buiten status-signalen: Etil-rood (header only) en Etil-blauw (primaire actie/link). Geen derde decoratieve accentkleur wordt toegevoegd zonder dat hij een van deze twee vervangt.

**The Reserved Status Rule.** Emerald/amber/red (groen/geel/rood) zijn uitsluitend gereserveerd voor confidence-labels en foutmeldingen — nooit gebruikt als decoratief accent, illustratie-kleur of willekeurige highlight. Als een kleur op het scherm groen is, betekent het altijd "hoge zekerheid/goedgekeurd", nooit iets anders.

## 3. Typography

**Body Font:** Inter (fallback: Segoe UI, Arial, sans-serif)
**Display/Label Font:** zelfde familie, geen aparte display-font — hiërarchie komt van gewicht en grootte, niet van font-wissel.

**Character:** Eén enkele, functionele sans-serif in meerdere gewichten. Geen sierlijke display-font: dit is een werktuig, geen merkervaring.

### Hierarchy
- **Headline** (600, 1.25rem/20px, 1.2): schermtitels in de header (bv. "Batch #124"), sectietitels.
- **Title** (600, 1rem/16px, 1.3): kaarttitels, tabel-kolomkoppen (uppercase, slate-500, tracked).
- **Body** (400, 0.875rem/14px, 1.5): standaard leestekst, tabelcellen, formuliervelden. Max ~65-75ch voor lopende tekst in chat/toelichtingen.
- **Label** (500, 0.75rem/12px, 1.3): badges, status-pills, metadata-labels.

### Named Rules
**The One-Family Rule.** Eén font-stack (Inter) voor alles. Hiërarchie ontstaat uit `font-weight` en `font-size`, niet uit font-pairing — past bij een dicht, data-zwaar scherm waar rust belangrijker is dan typografisch statement.

## 4. Elevation

Grotendeels vlak systeem met tonale scheiding via `border-line` (#d7dde5) in plaats van schaduw. `shadow-sm` verschijnt alleen op kaarten/panelen/modals die zich onderscheiden van de pagina-achtergrond (login-form, batch-detail-secties, chat-bubbles). `shadow-lg` is gereserveerd voor elementen die letterlijk boven andere content zweven (dropdowns, tooltips).

### Shadow Vocabulary
- **ambient** (`shadow-sm`): kaarten en panelen die rusten op de pagina-achtergrond. Subtiele scheiding, geen dramatische diepte.
- **overlay** (`shadow-lg`): dropdowns, tooltips, contextmenu's — content die tijdelijk over andere UI heen zweeft.

### Named Rules
**The Border-Over-Shadow Rule.** Scheiding tussen elementen op dezelfde laag (tabelrijen, lijstitems) gebeurt via `border-line`, niet via schaduw. Schaduw is gereserveerd voor echte laagverschillen (zwevende overlay vs. rustende paneel).

## 5. Components

### Buttons
- **Shape:** `rounded-md` (8px), consistent voor alle knopvarianten.
- **Primary:** `bg-etil` (#1e3a5f) met witte tekst, 40px hoog, gebruikt voor de hoofdactie per scherm (inloggen, run starten, opslaan).
- **Danger:** `bg-red-600` met witte tekst — destructieve acties (verwijderen, batch stoppen).
- **Default/Ghost:** witte achtergrond met `border-line`, `text-ink`, hover naar `bg-panel` — de meerderheid van de knoppen (secundaire acties, iconknoppen in de actiebalk).
- **Quiet:** transparante achtergrond, `text-slate-600`, hover naar `bg-panel` — voor lage-nadruk acties binnen dichte lijsten.
- **Hover / Focus:** subtiele opacity- of achtergrond-shift, altijd met zichtbare `focus-ring` (2px `etil`-ring, offset 2px) voor toetsenbordnavigatie — niet optioneel gezien de WCAG 2.1 AA-eis.

### Chips / Status
- **LabelBadge (confidence 🟢🟡🔴):** gevulde achtergrond in de zachte tint (emerald-50/amber-50/red-50), tekst in de donkere tint (emerald-800/amber-800/red-800), met een gekleurde stip (`dot`) ervoor. Vorm: `rounded-md`, klein en compact — leesbaar in een dichte tabel zonder de rij te domineren.
- **StatusPill (workflow-status: Open/Goedgekeurd/Gecorrigeerd/Draait/Klaar/Fout):** neutrale variant — witte achtergrond, `border-line`, `text-slate-700`. Bewust NEUTRAAL gehouden zodat hij niet visueel concurreert met de confidence-LabelBadge; workflow-status en confidence-oordeel zijn twee aparte signalen en moeten dat ook ogen.

### Cards / Containers
- **Corner Style:** `rounded-lg` (12px) voor paneel-niveau containers (login-kaart, batch-detail-secties, chatvenster).
- **Background:** wit op de grijze paginakleur (`page-bg` #eef2f5) — het enige contrastsignaal dat een paneel is een paneel.
- **Shadow Strategy:** `shadow-sm`, zie Elevation.
- **Border:** `border-line`, altijd aanwezig naast de schaduw (dubbele, subtiele scheiding — geen zwevende kaarten zonder rand).
- **Internal Padding:** compact, meestal `p-4`–`p-6`, dichter in tabellen (`px-4 py-3`).

### Inputs / Fields
- **Style:** witte achtergrond, `border-line`, `rounded-md`, 40-44px hoog.
- **Focus:** `focus-ring` utility — 2px ring in `etil`-blauw met 2px offset. Consistent over alle interactieve elementen (inputs, knoppen, links) — het enige focus-signaal in het systeem.
- **Error:** rode randkleur + rode foutmelding-banner (`bg-red-50`, `border-red-200`, `text-red-800`) direct onder het veld, nooit alleen een kleurverandering zonder tekst (toegankelijkheid: kleur alleen is niet genoeg).

### Navigation
- **Header:** vast rood (`bg-[#C8102E]`) met wit Etil-wordmark, gebruikersnaam/rol rechts, uitlogknop. Geen hover-navigatiemenu — dit is een taakgerichte tool, geen site met brede navigatie.
- **Actiebalk:** direct onder de header, `bg-panel` met `border-line`, bevat contextuele acties voor het huidige scherm (rechts uitgelijnd).

### Confidence-labels (signatuurcomponent)
Het `LABELS`-object (`hoog`/`middel`/`laag` → groen/geel/rood) is het enige domeinspecifieke kleursysteem in de app en staat los van elke generieke UI-statuskleur (succes/fout van formulieren). Het communiceert een AI-confidence-oordeel, niet een UI-staat — verwar deze twee betekenissen nooit in nieuwe componenten.

## 6. Do's and Don'ts

### Do:
- **Do** gebruik `border-line` (#d7dde5) als enige randkleur door de hele app voor consistentie.
- **Do** reserveer emerald/amber/red uitsluitend voor confidence-labels en foutmeldingen.
- **Do** houd StatusPill (workflow) en LabelBadge (confidence) visueel gescheiden — nooit dezelfde kleurcodering.
- **Do** gebruik `focus-ring` op elk interactief element (WCAG 2.1 AA-eis).
- **Do** houd tabellen en lijsten compact (`px-4 py-3`) — reviewers verwerken veel records, dichtheid is functioneel.

### Don't:
- **Don't** gebruik gradient-tekst, glassmorphism, of decoratieve blur-effecten — dit is geen marketingoppervlak.
- **Don't** voeg een derde merkaccent-kleur toe naast Etil-rood (header) en Etil-blauw (actie).
- **Don't** gebruik kleine uppercase "eyebrows" boven elke sectie of hero-metric-templates — AI-SaaS-clichés die hier misplaatst zijn.
- **Don't** gebruik identieke kaartgrids als standaardoplossing voor elke sectie.
- **Don't** gebruik `border-left`/`border-right` als gekleurde accentstreep op kaarten of lijst-items.
- **Don't** laat kleur de enige drager van betekenis zijn (bv. alleen een rode rand zonder foutmelding-tekst).
