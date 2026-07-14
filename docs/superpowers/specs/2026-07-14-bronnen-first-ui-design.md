# Bronnen-first review-UI + identiteits-/scope-classificatie

**Datum:** 2026-07-14
**Status:** goedgekeurd, klaar voor implementatieplan

## Doel

De reviewer (Armina/Anita) besteedt nu te veel tijd aan handmatig bronnen opzoeken en beoordelen, omdat de AI niet volledig autonoom het juiste WP-getal kan bepalen. In plaats van te blijven optimaliseren richting volledige autonomie, verschuift dit project het doel van de review-UI: **bronnen presenteren zodat het menselijke researchwerk zoveel mogelijk wordt weggenomen**, niet vervangen. Concreet:

- bronnen staan bovenaan de reviewpagina, niet weggestopt in een ingeklapt paneel;
- een klik op een bron opent 'm meteen op de juiste plek — juiste pagina + gemarkeerd citaat voor jaarverslagen (PDF), juiste zin gemarkeerd voor webpagina's;
- de reviewer ziet direct waar extra oplettendheid nodig is versus waar het systeem redelijk zeker is dat bron en WP-getal bij dit bedrijf en deze vestiging horen.

**Buiten scope voor dit project** (apart vervolgtraject): het aantal/de breedte van gevonden kandidaat-bronnen vergroten (nieuwe zoek-nodes, multi-candidate ranking). Dit project werkt met de bronnen die de pipeline nu al oplevert (website, jaarverslag, extra_bronnen).

## Achtergrond / huidige staat

- Reviewpagina: `frontend/src/views/DetailView.jsx`. Bronnen staan nu in een collapsible panel "Gevonden bronnen" (`defaultOpen={false}`, regels 66-100), *onder* de score-uitleg.
- Deep-linking bestaat al gedeeltelijk: `frontend/src/lib/format.js` (`bronLink()`) bouwt `#page=N` voor jaarverslagen en een Chrome/Edge Text Fragment (`#:~:text=...`) voor websites — maar zonder page+highlight in een eigen viewer, en zonder fallback-weergave als de text fragment niet matcht.
- `AgentResult` (`backend/app/models.py`) bevat al: `agent_type` (website|jaarverslag|extra_bron), `bron_type`, `bron_url`, `bron_pagina`, `wp_context` (citaat), `llm_zekerheid` (hoog/middel/laag).
- `extra_bronnen` worden al verzameld en al meegestuurd naar de frontend (`agent_type="extra_bron"`, tot `settings.extra_bronnen_aantal`, default 2), maar de frontend groepeert/toont ze nu niet apart.
- Er bestaat nog geen identiteits- of scope-classificatie per bron (zie `docs/AGENT_ARCHITECTUUR_BRAINSTORM.md`, probleemcases Salon Handmade en Jumbo Supermarkten). Dit project voegt die classificatie toe, puur als informatie voor de reviewer — de reconciliatielogica (welke bron het WP-kandidaatgetal levert) verandert niet.
- Frontend heeft nog geen PDF-viewer-dependency (`frontend/package.json`: geen `pdfjs-dist`/`react-pdf`).

## Architectuurkeuzes

### PDF-highlight: ingebouwde PDF.js-viewer via iframe

We embedden de standaard PDF.js-viewer (dezelfde engine als Firefox' ingebouwde PDF-viewer) in een modal, en geven 'm mee: paginanummer + zoekterm via URL-fragment (`#page=N&search=<citaat>&phrase=true`). PDF.js voert dan zelf "zoek bij laden en markeer alle matches" uit. Dit vermijdt het zelf berekenen van tekstposities/bounding boxes op de pagina (het alternatief, `react-pdf` + eigen highlight-overlay, vereist wél zelf tekstlaag doorzoeken en coördinaten matchen — aanzienlijk meer bouw- en onderhoudswerk voor hetzelfde eindresultaat).

### Identiteits-/scope-classificatie: hybride heuristiek + LLM

1. **Heuristische check eerst** (gratis, deterministisch): komt de bedrijfsnaam/het domein voor in de brontekst/URL? Zo niet → direct `identity_class=mismatch`, geen LLM-call nodig. Vangt de voor-de-hand-liggende cross-company mismatches (Salon Handmade → Heijmans-jaarverslag) goedkoop af.
2. **LLM-classificatie alleen als de heuristiek geen harde mismatch vindt**: één call per bron met company-context (naam, adres, gemeente, KvK) → gestructureerde output `identity_class` + `scope_class`. Scope-onderscheid (vestiging/limburg/nederland/concern) is te semantisch voor pure tekstmatching en heeft LLM-oordeel nodig (bv. "wij tellen X medewerkers in heel Nederland" vs "onze vestiging in Sittard telt X medewerkers").

Dit houdt kosten laag voor de duidelijke gevallen en zet de duurdere LLM-stap alleen in waar nodig.

## Backend-ontwerp

### Datamodel

Nieuwe velden op `AgentResult` (`backend/app/models.py`):

```python
identity_class: Mapped[str]  # exact_match | brand_or_group_match | mismatch | unknown
scope_class: Mapped[str]     # vestiging | limburg | nederland | concern | unknown
```

Gelden voor alle `agent_type`-waarden, inclusief `extra_bron` — de reviewer moet ook bij extra context kunnen zien of die wel over het juiste bedrijf/dezelfde vestiging gaat.

### Pipeline

Nieuwe stap in `backend/app/pipeline/runner.py`, ná extractie en vóór reconciliatie:

1. `heuristic_check(company, result)` → beoordeelt naam-/domeinmatch tussen bedrijfsgegevens en brontekst/URL. Duidelijke mismatch → `identity_class="mismatch"`, `scope_class="unknown"`, geen LLM-call.
2. Anders: `classify_identity_and_scope(result, company_context)` — LLM-call met de verplichte prompt-injectieclausule (externe brontekst = onbetrouwbare input, conform CLAUDE.md-conventie), structured output voor beide velden.
3. Resultaat opslaan op de betreffende `AgentResult`-rij, voor alle agent_types inclusief `extra_bron`.

**Reconciliatie blijft ongewijzigd** in dit project: `identity_class`/`scope_class` zijn puur informatief voor de reviewer, geen nieuwe hard-gate in `reconcile.py`. Dit past bij het projectdoel — de mens beslist, het systeem informeert beter.

### Provider-pattern

Zowel mock als live provider implementeren `classify_identity_and_scope` achter hetzelfde Protocol-interface (conform bestaande conventie). Mock-provider geeft vaste, deterministische classificatie-uitkomsten per testbedrijf in `data/testset.csv`, zodat `python -m scripts.validate` reproduceerbaar blijft.

### API

`backend/app/routers/batches.py`, `company_detail`-endpoint: `identity_class` en `scope_class` toevoegen aan de geserialiseerde `agent_results`-items (naast bestaande velden als `bron_type`, `llm_zekerheid`, `wp_context`).

## Frontend-ontwerp

### Paginavolgorde (`DetailView.jsx`)

1. **Bronnen** (nieuw, bovenaan, altijd uitgeklapt — geen collapsible panel meer)
   - **Hoofdbronnen** (website/jaarverslag, de bronnen die in reconciliatie meetellen): kaart per bron met bron_type-icoon, WP-gevonden, zekerheidsbadge, citaattekst, actieknop "Bekijk bron".
   - **Extra context** (agent_type=extra_bron): aparte subsectie, duidelijk gelabeld "Extra context — telt niet mee in score", zelfde kaartopbouw maar visueel gedempt (grijzere achtergrond) zodat het onderscheid met hoofdbronnen direct duidelijk is.
2. **Score-uitleg** (`ScoreBreakdown`, ongewijzigd, komt nu ná de bronnen)
3. **WP-uitsplitsing / overige secties** zoals nu.

### Zekerheidsindicator per bron

Afgeleid (niet los ingevoerd) uit de combinatie van `confidence`/`llm_zekerheid`, `identity_class` en `scope_class`:

- **Groen — redelijk zeker**: `identity_class=exact_match` én `scope_class` past bij het bedrijfstype (bv. `vestiging` of `limburg` bij een klein bedrijf), `llm_zekerheid=hoog`.
- **Oranje — controleer even**: `brand_or_group_match`, `scope_class=nederland/concern` bij een bedrijf waar dat een schattingsrisico oplevert, of `llm_zekerheid=middel`.
- **Rood — goed nalezen**: `identity_class=mismatch` of `unknown`, of `llm_zekerheid=laag`.

Badge toont kleur + korte tooltip met de reden ("waarom": bv. "Bron noemt een landelijk cijfer, niet per se deze vestiging").

### Bron openen

- **Jaarverslag** (`bron_type=jaarverslag`): klik opent **modal** met ingebouwde PDF.js-viewer, automatisch op `bron_pagina` + het citaat gezocht/gemarkeerd. Sluiten van de modal brengt de reviewer direct terug naar de reviewpagina, geen tabwissel.
- **Website** (`bron_type=website`): klik opent in **nieuwe tab** met de bestaande text-fragment-URL (via `bronLink()`). Als text fragment niet matcht (silent degradation buiten Chromium), blijft het citaat sowieso prominent zichtbaar in de bronkaart zelf (niet alleen als kleine blockquote) zodat de reviewer niet met lege handen op de pagina komt.

### Nieuwe dependency

`pdfjs-dist` toevoegen aan `frontend/package.json` (of de meegeleverde PDF.js-viewerbundel embedden via iframe) — momenteel geen PDF-viewer-library aanwezig.

## Testplan

- **Backend**: unit tests voor `heuristic_check` en `classify_identity_and_scope`, deterministisch via mock-provider. Regressietests met de Salon Handmade- en Jumbo Supermarkten-cases uit `docs/AGENT_ARCHITECTUUR_BRAINSTORM.md` (verwacht: `mismatch` resp. `brand_or_group_match`+`concern`/`nederland`).
- **Validatie**: `python -m scripts.validate` moet op de huidige streefwaarden blijven (coverage 100%, MAPE 🟢 0%, kalibratie 100%) — reconciliatie zelf verandert niet, dus deze cijfers zouden ongewijzigd moeten blijven.
- **Frontend**: geen geautomatiseerde UI-tests in dit project (geen test-runner voor React aanwezig in `package.json`). Handmatige verificatie in de browser:
  - bronnen-sectie staat bovenaan, uitgeklapt, vóór score-uitleg;
  - PDF-modal opent en markeert het citaat correct voor minstens één mock jaarverslag-bron;
  - website text-fragment-link werkt, en de fallback (citaat zichtbaar in kaart) is aanwezig;
  - zekerheidsbadges tonen de juiste kleur/uitleg voor combinaties van identity_class/scope_class/llm_zekerheid, inclusief de mismatch- en unknown-gevallen.
