# Agent-architectuur brainstormnotitie

## Use case

ETIL wil per vestiging het aantal werkzame personen (WP) vinden, beoordelen en laten accorderen. De kernvraag is niet alleen: "welk getal staat ergens op internet?", maar vooral:

- hoort de bron echt bij dit bedrijf?
- geldt het getal voor deze vestiging, Limburg, Nederland, of een concern?
- is het headcount of FTE?
- is het actueel genoeg voor het peiljaar?
- kan een reviewer snel zien waarom het systeem dit getal voorstelt?

De pipeline moet goedkoop genoeg blijven voor batches, maar betrouwbaar genoeg zijn om grote foutpositieven te voorkomen. Website-informatie is leidend bij kleine bedrijven/praktijken, omdat team- of vestigingspagina's vaak letterlijk de lokale medewerkers tonen. Jaarverslagen zijn nuttig bij grote organisaties, maar gevaarlijk bij filialen en generieke namen omdat ze vaak landelijke of concernbrede cijfers bevatten.

## Huidige hoofdarchitectuur

De batchpipeline draait per bedrijf grofweg:

1. `lookup`: website/contact/adres via Serper Places, Google Places fallback voor locatietelling.
2. `website_agent`: bezoekt bedrijfswebsite en navigeert met tool-use naar relevante pagina's.
3. `jaarverslag_agent`: zoekt PDF/jaarverslag, extraheert WP uit PDF.
4. `extra_bronnen`: verzamelt aanvullende media/LinkedIn/KvK-achtige bronnen voor reviewer, niet voor reconciliatie.
5. `reconcile`: kiest kandidaat uit website + jaarverslag.
6. `confidence`: scoort kandidaat met locatie, specificiteit, bronkwaliteit, consensus, adres en actualiteit.
7. reviewer keurt goed, past aan of zet op bellijst.

Belangrijke bestanden:

- `backend/app/pipeline/runner.py`: orchestration per bedrijf.
- `backend/app/providers/live.py`: live agents, websearch, PDF-search, website tool-use-loop.
- `backend/app/pipeline/reconcile.py`: beslislogica website/jaarverslag.
- `backend/app/pipeline/confidence.py`: confidence score.
- `backend/data/testset.csv`: referentiebedrijven en verwachte WP.
- `backend/data/mock_data.json`: mock-mode baseline.
- `docs/kosten/KOSTENOVERZICHT.md`: kosteninschatting.

## Recente beslissingen

Website blijft leidend bij kleine bedrijven. De jaarverslag-agent wordt overgeslagen als de website-agent al een hoge zekerheidsbevinding heeft. Dit verlaagt kosten en voorkomt ruis bij bedrijven zonder eigen jaarverslag.

Extra bronnen blijven voorlopig puur informatief voor de reviewer. Ze tellen niet mee in reconciliatie, omdat extra bronnen laten "meestemmen" een grotere kalibratiewijziging is.

Niet-Limburg-specifieke bronnen zonder bekende vestigingscount mogen geen kandidaat meer worden. Voorbeeld: een landelijk of concernbreed getal mag niet als vestigingsgetal gebruikt worden als er geen herleidingsbasis is.

## Bekende probleemcases

### Salon Handmade

Klein bedrijf, verwacht websitebron rond 3 medewerkers. Jaarverslag-search pakte eerder een Heijmans-document met 6.158 medewerkers. Dat is een pure cross-company mismatch.

Architectuurles: elke gevonden bron moet eerst bron-identiteit valideren voordat extractie/reconciliatie plaatsvindt.

### Jumbo Supermarkten - Filiaal

Zoekroute vindt echte Jumbo-jaarverslagen, maar die zijn landelijk/concerngericht. Dat is niet "verkeerd bedrijf", maar wel verkeerde scope voor één filiaal.

Architectuurles: bronvalidatie mag niet boolean zijn. Nodig is:

- `exact_match`
- `brand_or_group_match`
- `mismatch`
- `unknown`

Daarna moet scope worden geclassificeerd:

- `vestiging`
- `limburg`
- `nederland`
- `concern`

### Mondriaan

Live search is niet-deterministisch. De ene run vindt juiste Mondriaan-jaarverantwoording, een andere run kan een minder relevante kwaliteitsbron of ander Mondriaan-gerelateerd document vinden.

Architectuurles: zoekresultaten moeten gerankt en gecachet worden. Een eerder goede bron-URL moet worden hergebruikt zolang hij nog bereikbaar is.

### Hallux Podotherapie

Websitepagina's kunnen per vestiging/team letterlijk het aantal behandelaars tonen. Dit soort bronnen zijn voor kleine praktijken vaak betrouwbaarder dan jaarverslagen. Het historische mock-domein resolveerde tijdens test niet meer, maar het functionele patroon blijft belangrijk.

Architectuurles: website-agent moet beter naar team/vestigingspagina's navigeren en locatie-specifieke context zwaarder wegen.

## Playwright

Playwright is geen extra API-kost, maar kost serverruntime: CPU, geheugen en seconden per render.

Gemeten geforceerde renders:

- Fysiosittard team: ongeveer 4.6 seconden.
- IKEA Heerlen: ongeveer 2.1 seconden.

Bij geteste bereikbare sites gaf Playwright meestal geen extra tekst boven gewone HTTP. Daarom niet standaard gebruiken.

Aanbevolen beleid:

1. Eerst gewone HTTP-fetch.
2. Alleen Playwright als:
   - tekstlengte zeer laag is,
   - HTML vooral `root`/app-shell bevat,
   - relevante links ontbreken,
   - pagina duidelijk JS-heavy is,
   - eerdere run op domein aantoonde dat Playwright meer tekst geeft.
3. Cache per domein of URL of Playwright nuttig is.

## MCP

OpenAI Responses API ondersteunt remote MCP servers als tooltype `mcp`. Dit kan nuttig zijn voor browserdiensten, interne bronnen of gespecialiseerde navigatie. Er is geen aparte OpenAI fee per MCP-call; de kosten zitten in tokens voor tooldefinities en tool-call context, plus de kosten van de MCP-server zelf.

Voor deze use case is MCP niet de eerste stap. Een interne backend-toolset is simpeler, goedkoper en beter controleerbaar:

- `fetch_page`
- `render_page`
- `extract_links`
- `download_pdf`
- `validate_source_identity`
- `classify_scope`

MCP wordt interessant als er echte browserinteractie nodig is:

- klikken door cookie/modals,
- scrollen,
- screenshots,
- interactieve zoekpagina's,
- SharePoint/Drive/interne bronnen,
- aparte browser-service met observability.

Veiligheidsregel: alleen read-only MCP-tools, domeinrestricties, logging van gedeelde data, en approval voor gevoelige acties.

## Aanbevolen LangGraph-architectuur

### Websitegraph

```text
start
  -> resolve_known_website
  -> fetch_http
  -> classify_page_quality
  -> maybe_render_playwright
  -> rank_internal_links
  -> visit_relevant_links
  -> extract_wp_candidates
  -> validate_source_identity
  -> classify_scope
  -> select_best_website_finding
```

Belangrijke verbetering: extractie moet meerdere candidates kunnen produceren, niet alleen eerste hit. Daarna kiest een deterministic/scoring node de beste.

### Jaarverslaggraph

```text
start
  -> try_cached_source_url
  -> search_site_domain_first
  -> search_open_web
  -> rank_candidate_documents
  -> validate_source_identity
  -> classify_document_type
  -> extract_pdf_pages
  -> extract_wp_candidates
  -> classify_scope
  -> return finding_or_baseline_source
```

Belangrijk: `site:{eigen domein}` eerst zoeken wanneer website bekend is. Open web pas daarna.

### Reconciliatiegraph

```text
website_finding + jaarverslag_finding + location_counts
  -> reject_mismatches
  -> prefer_exact_location_website_for_small_business
  -> accept_consensus_if_scope_matches
  -> proportional_estimate_only_with_location_counts
  -> never_green_on_estimate
  -> produce_candidate + reviewer_explanation
```

## Scoringregels die belangrijk zijn

- Exacte vestigingswebsite met hoog vertrouwen wint bij kleine bedrijven.
- Jaarverslag met `concern` of `nederland` scope mag niet direct filiaal-WP worden.
- Proportionele schatting alleen als `count_nl` en `count_lb` bekend zijn.
- Proportionele schatting nooit groen.
- Cross-company mismatch direct weggooien.
- Unknown identity/scope niet automatisch kandidaat maken; wel tonen als reviewerbron/baseline.
- Extra bronnen niet laten meetellen totdat er aparte kalibratie/evals zijn.

## Test/eval-aanpak

Maak een kleine eval-harness met de 20 bedrijven uit `backend/data/testset.csv`.

Per bedrijf loggen:

- gevonden website URL,
- bezochte pagina's,
- HTTP tekstlengte,
- Playwright tekstlengte indien gebruikt,
- gevonden PDF URL,
- identity class,
- scope class,
- geextraheerd WP,
- kandidaat WP,
- confidence,
- reden,
- runtime per node,
- externe API-kosten per node.

Meet niet alleen accuracy, maar ook fouttype:

- exact correct,
- acceptabele schatting,
- wrong company,
- wrong scope,
- no source found,
- extraction glitch,
- stale source.

De belangrijkste metric is niet gemiddelde fout, maar voorkomen van catastrofale foutpositieven zoals 3 medewerkers -> 6.158.

## Concrete volgende stappen

1. Maak `validate_source_identity` multi-class in plaats van bool.
2. Voeg `classify_scope` toe voor website en jaarverslag.
3. Geef `LiveJaarverslagAgent.run()` meer context: website URL, adres, gemeente, KvK.
4. Zoek jaarverslagen eerst op eigen domein.
5. Cache goede bron-URL's per bedrijf/jaar.
6. Maak Playwright domein/URL-gated, niet standaard.
7. Bouw een eval-script voor de 20 testsetbedrijven zonder reviewer-UI.
8. Pas reconciliatie pas aan na eval-output, niet op basis van losse cases.

## Kernsamenvatting voor een andere LLM

We bouwen geen simpele scraper maar een bronbeoordelingssysteem. De grootste kwaliteitswinst zit niet in een duurder model, maar in betere graafstappen vóór extractie: juiste bron vinden, bronidentiteit valideren, scope classificeren, en pas daarna WP extraheren. Website is leidend voor kleine vestigingen; jaarverslagen zijn waardevol voor grote organisaties maar riskant voor filialen. Playwright is een gerichte fallback voor JS-heavy sites, geen standaardpad. MCP kan later als browser/integratielaag, maar eerst zijn deterministic backend-tools beter. De beste architectuur is een LangGraph met aparte nodes voor search, fetch/render, link-ranking, identity, scope, extraction, reconciliation en eval logging.
