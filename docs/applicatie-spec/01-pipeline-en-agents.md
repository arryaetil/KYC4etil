# Pipeline en agents

> **Actieve bronnenwerkbank:** de hoofdregie staat in
> `backend/app/research/service.py` en `supervisor.py`, niet meer in de historische
> `pipeline/runner.py`. De supervisor gebruikt gewone async Python. LangGraph
> blijft beperkt tot adaptief website- en jaarverslagonderzoek.

Voor iedere organisatie maakt `query_planner.py` een deterministisch routeplan.
De basis bestaat uit website en media. SBI-profielen voegen waar relevant DUO,
DigiMV, team-/afspraakonderzoek of formele documenten toe. De supervisor bewaart
per route `afgerond`, `overgeslagen` of `mislukt`, inclusief aantal queries en
bruikbare bronnen. Een verplichte mislukte of wegens budget overgeslagen route
maakt de inhoudelijke runstatus `technisch_onvolledig`.

Voor onderwijs is DUO niet alleen een zoekquery. `research/duo.py` leest de
officiële PO-, VO- en MBO-adresbestanden rechtstreeks in, koppelt naar een
instellingscode en haalt uit het jaarlijkse personenbestand het gevraagde of
laatst beschikbare jaar. Pydantic valideert de externe rijen. Een getal houdt
de eenheid `onderwijspersoneel_personen`; bij meerdere instellingscodes worden
alle deelwaarden bewaard maar niet opgeteld.

Elke `Company` in een `Batch` doorloopt dezelfde reeks stappen, gecoördineerd in
`backend/app/pipeline/runner.py` (functie `verwerk_company`). Elke stap logt zijn
tijdsduur en status (`ok`/`skipped`/`error`) naar de `PipelineRun`-tabel.

## Stap 1 — Verrijking

Haalt vestigings- en contactdata op: KvK-gegevens primair, Google Places als secundaire
bron (voor locatiecount en adresvalidatie). Bepaalt `count_nl`/`count_lb` (aantal
vestigingen in Nederland resp. Limburg) — cruciaal voor de reconciliatielogica, want
`count_lb == count_nl` betekent dat het hele bedrijf in Limburg zit en dus
locatie-eenduidig is.

## Stap 2a — Website-agent (LangGraph)

Een agentic onderzoeksagent, geïmplementeerd als een LangGraph `StateGraph`
(`backend/app/providers/live.py`, `_build_website_research_graph`). De gedeelde state
(`WebsiteResearchState`) bevat `naam`, `adres`, `website_url`, `gemeente` en `best` (het
uiteindelijke resultaat, indien gevonden).

**Nodes:**
- **`inspect_website`** — de kern van de agent: een multi-turn OpenAI tool-use-lus
  (`_tool_use_loop`) waarin het taalmodel zelf beslist welke pagina's van de eigen
  bedrijfswebsite het wil bezoeken via een `bezoek_pagina`-tool ("over ons", "vacatures",
  "contact", etc.), tot het model zelf een `meld_resultaat`-tool aanroept of het
  paginabudget (`max_website_pages + 2`, standaard dus 5 aanroepen) op is.
- **`web_search_fallback`** — als de eigen website niets opleverde: een generieke
  zoekopdracht (via Serper, zie hieronder) als vangnet.

**Overgang:** conditionele edge `after_website` — als `best` gevuld is → `END`, anders
naar `web_search_fallback` (die altijd naar `END` gaat). Kortom: eerst grondig de eigen
website doorzoeken, pas als vangnet een generieke zoekopdracht.

**Paginafetch met kostenbeheersing (`_haal_pagina_op`):** eerst een simpele `httpx`-GET
+ BeautifulSoup-parse (goedkoop, snel). Alleen als dat minder dan 500 tekens bruikbare
tekst oplevert (teken van een JS-zware site — React/Vue/Angular die serverside niets
rendert) én `PLAYWRIGHT_ENABLED` aan staat, valt de agent terug op **crawl4ai**: een
volledige headless Chromium-browser via Playwright die de pagina daadwerkelijk rendert,
waarna crawl4ai's `PruningContentFilter`/`DefaultMarkdownGenerator` de boilerplate
(navigatie, sidebars) wegfiltert voordat de tekst naar de extractie-LLM gaat. crawl4ai
wordt dus **nooit standaard** gebruikt — alleen als expliciete, duurdere fallback,
precies zoals de docstring in de code het zegt: "Duurder... daarom alleen ingezet als
fallback." Er is geen externe factuur voor crawl4ai zelf (het draait zelf-gehost op de
Railway-container) — de kosten zitten in compute/latency, niet in een API-rekening.

## Stap 2b — Jaarverslag-agent (LangGraph, met retry-lus)

Rijker dan de website-agent, omdat jaarverslagen vaker het verkeerde bedrijf betreffen
(bijvoorbeeld een landelijk concernverslag i.p.v. het verslag van deze ene vestiging).
State (`JaarverslagResearchState`): `naam`, `jaar`, `website_url`, `pdf_url`,
`laatste_pdf_url`, `afgewezen_urls` (een set), `pogingen`, `source_identity_class`,
`finding`.

**Nodes:**
- **`find_pdf`** — zoekt een jaarverslag-PDF-url, sluit expliciet al eerder afgewezen
  URL's uit, verhoogt de pogingenteller.
- **`valideer_bron`** — classificeert of de gevonden PDF daadwerkelijk over dít bedrijf
  gaat. Bij een mismatch wordt de URL toegevoegd aan `afgewezen_urls`, zodat een volgende
  poging gedwongen een ander resultaat oplevert. Dit is een directe reactie op een
  concreet, eerder gedocumenteerd bugscenario: Salon Handmade (Weert) kreeg ooit het
  jaarverslag van Heijmans (6.158 medewerkers) toegewezen als bron — een pure
  cross-company mismatch. De code documenteert dit scenario letterlijk als voorbeeld.
- **`extract_pdf`** — haalt het WP-getal uit de gevalideerde PDF.
- **`web_search_fallback`** / **`baseline_source`** — als er na alle pogingen nog niets
  bruikbaars is, wordt als allerlaatste redmiddel de laatst gevonden (ook al afgewezen)
  PDF alsnog gebruikt, met de classificatie zichtbaar meegegeven aan de reviewer.

**Overgangen:** bij een mismatch of een geldige bron zonder bruikbaar getal gaat de graph
terug naar `find_pdf`, zolang `pogingen < jaarverslag_max_pogingen` (standaard 3). Pas
daarna volgt de fallback-keten. Dit maakt de jaarverslag-agent een echte beslisboom met
terugkoppeling, geen lineaire pijplijn.

Beide graphs zijn gecompileerd (`.compile()`) en worden per bedrijf één keer aangeroepen
via `.ainvoke(initial_state)`.

## Stap 3 — Extra bronnen

Naast de twee hoofdbronnen verzamelt de pipeline ook aanvullende publieke media-bronnen
(`agent_type="extra_bron"`). Deze tellen **niet mee** in de reconciliatie/confidence-score
— ze zijn puur informatief voor de reviewer ("human-in-the-loop context") en worden in de
UI apart en visueel gedempt getoond.

## Stap 4 — Identity-/scope-classificatie

Voor elke gevonden bron (website, jaarverslag, extra bronnen) wordt bepaald:
- **`identity_class`**: hoort deze bron aantoonbaar bij dít bedrijf? Waarden:
  `exact_entity`, `same_brand_or_group`, `possible_match`, `mismatch`, `unknown`.
- **`scope_class`**: voor welke schaal geldt het gevonden getal? Waarden: `vestiging`,
  `limburg`, `nederland`, `concern`, `unknown`.

**Twee-traps aanpak** (kostenbeheersing, `backend/app/pipeline/identity_scope.py`):
1. Eerst een gratis, deterministische heuristiek: een domeinmatch (bron-URL-domein
   vergeleken met het bekende bedrijfsdomein) plus een naam-tokenmatch tegen het citaat.
   Bij een confident domeinmatch wordt de LLM helemaal overgeslagen.
2. Alleen bij twijfelgevallen (geen domeinmatch, of de naammatch is niet eenduidig) wordt
   een LLM-classificatie ingezet (`LiveIdentityScopeClassifier`), met de verplichte
   prompt-injectieclausule in de prompt (externe tekst = onbetrouwbare input).

Deze classificatie is **puur informatief**: ze wordt nooit doorgegeven aan de
reconciliatie- of confidence-berekening (die blijven ongewijzigd op `w_finding`/
`j_finding` werken). Ze is bedoeld om de reviewer in de bronnen-UI direct te laten zien
welke bronnen extra aandacht verdienen (zie
[03-review-ui-en-bronnen.md](03-review-ui-en-bronnen.md)).

Een fout tijdens deze classificatie (bijvoorbeeld een tijdelijke LLM-storing in
live-modus) mag de rest van de bedrijfsverwerking nooit blokkeren: de aanroep is
omgeven door een try/except die terugvalt op `unknown`/`unknown`, zodat het
"informatief-only, nooit een hard gate"-principe ook standhoudt bij storingen.

## Stap 5 — Reconciliatie en Stap 6 — Confidence scoring

Zie [02-datamodel-en-scoring.md](02-datamodel-en-scoring.md) voor de volledige regels en
formule.

## Externe diensten — overzicht en kostenprofiel

| Dienst | Waarvoor | Wanneer aangeroepen | Kostentype |
|---|---|---|---|
| **OpenAI** (`gpt-4o-mini` voor extractie; `gpt-4.1-mini` voor hosted search) | Extractie, identity/scope-classificatie en alleen bij lege klassieke zoekindexen hosted web search | Meerdere extractie-/reviewcalls; hosted search maximaal 1× domeinresolutie + 1× per website/document/media-pad | Per-token en per hosted tool-call, betaald |
| **Serper** | Places-lookup (locatie) én algemene web-zoekopdrachten | 1× Places per bedrijf (als key ingesteld), plus fallback-zoekopdrachten | Per-zoekopdracht, betaald — bewust gekozen als **goedkoper alternatief voor OpenAI's ingebouwde web_search** (letterlijke config-comment: "kostenbeheersing") |
| **Google Places (Text Search API)** | Locatie-lookup, fallback als Serper geen key heeft | 1× per bedrijf, alleen als Serper niet beschikbaar is | Per-call, betaald |
| **crawl4ai + Playwright/Chromium** | JS-rendering fallback voor de website-agent | Alleen als de goedkope httpx+BeautifulSoup-route <500 tekens tekst oplevert | Geen externe factuur — zelf-gehost compute (CPU/geheugen op de Railway-container), dus latency-kosten, geen dollar-per-call |

**Kostenindicatie** (uit `docs/PLATFORM_DOCUMENTATIE_v2.md`, §5): grofweg 1
Places-call (±$0,02) + 2–6 LLM-calls (±$0,05–0,30 per bedrijf, afhankelijk van
documentgrootte) per bedrijf. Bij een zoekproviderstoring kunnen daar maximaal
vier hosted web-searchcalls per bedrijf bijkomen. Voor een batch van 20 bedrijven
blijft **circa $1,40 tot $6,40 totaal** daarom alleen een basisindicatie; er bestaat nog
geen daadwerkelijk gemeten kostendata (het `kosten_cents`-veld op `PipelineRun` is wel
gedefinieerd in het datamodel, maar wordt nergens in de pipelinecode daadwerkelijk
gevuld).
