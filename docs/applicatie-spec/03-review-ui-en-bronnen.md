# Review-UI en bronnenpresentatie

React 19 + Vite + Tailwind CSS (puur utility-classes, `classNames()`-helper uit
`frontend/src/lib/format.js`, lucide-react-iconen — geen aparte component-/styling-library).

## Views (`frontend/src/views/`)

| View | Rol |
|---|---|
| **Login** | Inlogscherm. |
| **Dashboard** | Startpunt na inloggen. |
| **BatchView** | Primaire werkplek voor autonome batchresearch: voorgestelde bron, research-WP, legacy-WP, vergelijking, reviewstatus en inline beoordeling. |
| **DetailView** | Het bedrijfsdetailscherm — bronnen-first (zie hieronder). |
| **BellijstView** | Overzicht van bedrijven die telefonisch benaderd moeten worden. |
| **ChatSessiesView** / **ChatTemplatesView** | Beheer van chat-sessies en herbruikbare vraagsets (admin). |
| **ChatForm** | De publieke, token-based chatpagina die een extern bedrijf te zien krijgt (niet ingelogd). |
| **JaarverslagenView** / **JaarverslagChatView** | Los subsysteem voor ad-hoc jaarverslaganalyse, buiten de hoofdbatchpipeline. |
| **MonitoringView** | Bronnenmonitoring met filters voor actiegevallen, doorlopende controle en autonoom brononderzoek per organisatie. |

## Human-in-the-loop brononderzoek

In `BatchView` start **Bronnenonderzoek starten** standaard een autonome
researchrun voor iedere organisatie. De uitvoering loopt sequentieel om
zoek- en modelbudget beheersbaar te houden. De samenvatting toont afgeronde
runs, reviewgevallen, geaccepteerde bronnen, niet-gevonden bronnen en fouten.
**Legacy vergelijken** start de oude pipeline uitsluitend als expliciete
vergelijkingsrun.

Een gevonden WP-getal is alleen direct vergelijkbaar als de eenheid
`werkzame_personen` is en de scope `vestiging` of `limburg`. Een landelijk of
concerncijfer wordt met waarschuwing als context getoond, niet als bruikbaar
vestigings-WP. Daardoor betekent “bron gevonden” niet automatisch “getal
geschikt voor het register”.

Vanuit `MonitoringView` opent **Brononderzoek** een inline reviewwerkplek. De
reviewer ziet:

- welke drie bronfamilies worden onderzocht: website, documenten en media;
- de top-3 in rangorde, inclusief brontype, bronmatch, verslagjaar,
  peilmoment, scope, bewijsfragment en waarschuwingen;
- één expliciet geaccepteerde primaire bron;
- acties om een kandidaat te accepteren of af te wijzen;
- een handmatige broninvoer als de agent geen geschikte bron vindt.

De interface is bewust beslissinggericht. De organisatiepopulatie kan worden
gefilterd op **Actie nodig** of **Bron gevonden**; de reviewer hoeft daardoor
niet eerst alle zoekresultaten door te lopen. Een researchrun stelt alleen
kandidaten voor en wijzigt nooit zelfstandig het definitieve register.

## De bronnen-first detailpagina (`DetailView.jsx`)

Dit is het onderdeel dat in een recent project specifiek is herontworpen met als doel:
**de reviewer minder handmatig laten researchen** door de bronnen — en hoe zeker die
zijn — meteen bovenaan te tonen, in plaats van weggestopt onder de score.

**Layout, van boven naar beneden:**
1. **Bronnensectie** (`BronnenSectie`/`BronKaart` in `DetailView.jsx`) — altijd
   uitgeklapt, geen collapsible panel meer. Per bron een kaart met:
   - Het gevonden WP-getal en het citaat waar dat getal vandaan komt.
   - Een **zekerheidsbadge** (zie hieronder).
   - Voor jaarverslag-bronnen: een knop "Bron bekijken (pagina X)" die de PDF-modal
     opent op de juiste pagina. Voor website-bronnen: een directe link die in een nieuw
     tabblad opent (met, waar mogelijk, een text-fragment-link die direct naar de
     relevante zin springt).
   - **Extra bronnen** (`agent_type="extra_bron"`, tellen niet mee in de score) staan in
     een apart, visueel gedempt blok eronder, met het label "Extra context — telt niet
     mee in score".
2. **Vestigingsgegevens-, contactgegevens-, WP-uitsplitsing- en vastgoedkaarten** — in
   dezelfde relatieve volgorde als voorheen, nu ná de bronnen.
2. **Score-uitleg** (inklapbaar, standaard dicht) — de onderliggende
   `score_breakdown`-factoren, nu ná de bronnen in plaats van ervoor.

### De zekerheidsindicator (`frontend/src/lib/zekerheid.js`)

Een pure functie `deriveZekerheid(result)` die per bron, op basis van diens
`identity_class`, `scope_class` en `llm_zekerheid`, een **binaire** badge aflevert:

- 🟢 **groen — "Bron gevonden"**: de bron hoort aantoonbaar bij dit bedrijf
  (`identity_class` is `exact_entity` of `same_brand_or_group`) én op de juiste schaal
  (`scope_class` is `vestiging` of `limburg`) én met voldoende zekerheid (`llm_zekerheid`
  is `hoog` of `middel`).
- 🔴 **rood**: alle overige gevallen. Bij een expliciete `mismatch` het label "Verkeerd
  bedrijf?", anders "Goed nalezen" (onbekende identiteit, lage zekerheid, of een
  landelijk/concern-cijfer in plaats van deze vestiging).

Er is bewust **geen tussenliggend "oranje"-niveau** meer (dit was in een eerdere versie
een driewaardig risico-gewogen systeem — op verzoek vereenvoudigd naar een directe
ja/nee-vraag: hoort deze bron er duidelijk bij, of niet).

**Belangrijk:** deze badge is volledig gescheiden van de eigenlijke confidence-score
(§9 in [02-datamodel-en-scoring.md](02-datamodel-en-scoring.md)). De badge kan de
confidence-score niet beïnvloeden en andersom — het is een aparte, puur informatieve laag
voor de reviewer per bron, niet de officiële score van het bedrijf als geheel.

### De PDF-modal (`BronModal.jsx` + `pdfViewerLink.js`)

Voor jaarverslag-bronnen wordt PDF.js (Firefox' PDF-engine, vendored als standalone
viewer-app onder `frontend/public/pdfjs/`) in een iframe-modal getoond, met de PDF
automatisch geopend op de juiste pagina en — waar mogelijk — het relevante citaat
gemarkeerd via de viewer's zoek-/highlight-parameter. Dit bespaart de reviewer het
handmatig doorbladeren van vaak tientallen pagina's tellende jaarverslagen.

> **Bekende open kwestie:** jaarverslag-PDF's worden client-side, cross-origin geladen
> (rechtstreeks vanaf de externe bronwebsite, zonder backend-proxy). Of dit voor alle
> reële jaarverslag-hosts werkt hangt af van of die hosts CORS-headers meesturen — dit
> is nog niet in een echte browser tegen echte bronnen geverifieerd. Zie ook de
> deploy-sectie hieronder.

## Export en bellijst

- **"Bellijst"** = de lijst bedrijven die telefonisch benaderd moeten worden omdat
  automatische verwerking of chat niet tot een voldoende zekere waarde leidde. Reviewers
  zetten een candidate op de bellijst, en na het telefoongesprek wordt het resultaat via
  "doorvoeren" als definitieve, goedgekeurde WP-waarde in het register gezet.
- Twee losse Excel-exports (via `openpyxl`): het volledige register
  (`GET /batches/{id}/export.xlsx`) en alleen de bellijst
  (`GET /batches/{id}/bellijst.xlsx`).

## API-oppervlak (kort overzicht per routerbestand)

| Bestand | Belangrijkste functionaliteit |
|---|---|
| `auth.py` | Login, huidige gebruiker ophalen. |
| `batches.py` | CSV uploaden, autonome batchresearch starten, legacy-vergelijking draaien, annuleren/resetten, researchsamenvatting en bedrijvenlijst met bron-/WP-vergelijking leveren. |
| `chat_admin.py` | Chat-templates beheren, chat-sessies per batch, sessie-antwoorden doorvoeren naar het register. |
| `chat.py` | De publieke, token-based chatflow voor het benaderde bedrijf zelf (niet ingelogd). |
| `jaarverslagen.py` | Los jaarverslag uploaden/chatten/WP opslaan, buiten de batchpipeline om. |
| `monitoring.py` | Doorlopende jaarverslag-monitoring ophalen/draaien. |
| `research.py` | Autonome researchrun starten/pollen, top-3 ophalen en reviewerbeslissingen of handmatige bronnen vastleggen. |
| `review.py` | Candidate goedkeuren/corrigeren/naar bellijst zetten, bulk-goedkeuren van alle 🟢-candidates, bellijst-CRUD en doorvoeren, Excel-exports. |
