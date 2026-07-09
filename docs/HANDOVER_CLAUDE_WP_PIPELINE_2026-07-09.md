# Handover Claude - WP Pipeline Architectuur en Hardening

Datum: 2026-07-09  
Project: KYC4etil / ETIL WP-pipeline  
Doel: publieke bronnen onderzoeken en een voorstel doen voor `werkzame personen` per vestiging. De reviewer beslist altijd.

## Kerncontext

De pipeline moet uiteindelijk ongeveer 100.000 bedrijven per jaar kunnen verwerken. Daarom mag productiecode niet testset-specifiek zijn. De testbatch wordt alleen gebruikt als regressieset om foutklassen te vinden. Alle fixes hieronder zijn generieke bronklasse-regels: identiteit, scope, documenttype, URL-type, contextsteun en confidence-calibratie.

Belangrijkste productprincipe:

- Website/team/vestigingspagina is leidend voor kleine en lokale bedrijven.
- Jaarverslagen zijn nuttig voor grotere organisaties, maar riskant voor filialen, franchises, concerns, holdings en juridische shells.
- Extra bronnen blijven voorlopig reviewer-informatie en tellen niet mee in reconciliatie.
- Catastrofale false positives zijn erger dan geen kandidaat. Bij twijfel liever `laag` en review.

## Wat is gebouwd

### Architectuurdocument

Nieuw:

- `docs/AGENT_ARCHITECTUUR_BRAINSTORM.md`

Inhoud:

- LangGraph/StateGraph-richting met kleine nodes en deterministische control logic.
- WebsiteGraph, AnnualReportGraph, ReconciliationGraph.
- Advies: nu nog niet volledig migreren naar LangGraph, maar huidige runner graph-like refactoren.
- Playwright alleen gated fallback; MCP later, niet centraal.

### Evidence model

Nieuw:

- `backend/app/pipeline/evidence.py`
- `backend/tests/test_evidence_eval.py`

Bevat:

- `IdentityClass`
- `ScopeClass`
- `DirectnessClass`
- `EvidenceAssessment`
- `assess_finding_evidence()`

Doel: LLM mag evidence classificeren, maar confidence moet deterministisch blijven.

### Live provider hardening

Aangepast:

- `backend/app/providers/live.py`

Belangrijk:

- Jaarverslagbronvalidatie toegevoegd voordat PDF-extractie wordt vertrouwd.
- `source_identity_class` wordt opgeslagen in graph state / finding raw.
- Zoekresultaat-extractie slaat cross-company resultaten over.
- Zoekresultaat-extractie slaat vacature/job/career URLs over.
- `_haal_pagina_op()` kan optioneel Playwright gebruiken als HTTP-tekst te kort is en `settings.playwright_enabled` aanstaat.

### Runner gedrag

Aangepast:

- `backend/app/pipeline/runner.py`

Wijziging:

- Jaarverslag-agent wordt overgeslagen als de website-agent al een hoge-zekerheidsbevinding heeft.

Waarom:

- Kosten en performance bij schaal.
- Minder kans dat kleine/generieke bedrijven per ongeluk een verkeerd jaarverslag matchen.

### Reconciliatie hard gates

Aangepast:

- `backend/app/pipeline/reconcile.py`
- `backend/tests/test_pipeline.py`

Nieuwe generieke regels:

- Vacature/job/career URL wordt nooit WP-kandidaat.
- Niet-Limburg-specifiek / nationaal totaal zonder vestigingscount wordt geen directe kandidaat.
- Als vestigingscount bekend is, mag proportionele schatting, maar nooit groen.
- Media/search en jaarverslag moeten contextsteun hebben voor het gekozen WP-getal.
- Website/team/over-ons-vondsten worden niet afgewezen alleen omdat raw context niet perfect gepersisteerd is.
- Duidelijk verkeerde jaarverslagdocumenttypen zoals AVG/privacy/vacature-PDF worden geweigerd.
- Klein FTE-getal uit holding/legal-shell jaarverslag wordt geweigerd als vestigings-WP.

Belangrijke nuance:

- De website-route is bewust minder streng dan media/jaarverslag, omdat kleine bedrijven vaak alleen een team/over-ons pagina hebben en dat de beste bron is.

### Confidence calibratie

Aangepast:

- `backend/app/pipeline/confidence.py`

Wijziging:

- `media` bronnen kunnen niet meer groen worden als zelfstandige kandidaat.
- Schattingen konden al niet groen worden; dat blijft zo.

### Evaluatie tooling

Nieuw:

- `backend/scripts/evaluate_testset.py`
- `backend/scripts/compare_eval_with_api_batch.py`
- `docs/TESTSET_BATCH_VERGELIJKING_2026-07-09.md`

Doel:

- Testset lokaal evalueren.
- Productie-batches via API vergelijken.
- Foutklassen expliciet maken: exact, near, wrong, catastrophic, no_candidate.

`.gitignore` negeert nu gegenereerde JSONL eval-output:

- `backend/evals/*.jsonl`

## Tests

Gerichte test-suite:

```bash
python3 -m pytest backend/tests/test_evidence_eval.py backend/tests/test_improvements.py backend/tests/test_pipeline.py backend/tests/test_adaptive_website_agent.py -q --tb=short
```

Laatste resultaat:

- `52 passed`
- Alleen bestaande warnings over FastAPI `on_event` en SWIG/Python.

Mock-eval:

```bash
python3 backend/scripts/evaluate_testset.py --provider-mode mock --output backend/evals/testset_eval_mock.jsonl
```

Laatste resultaat:

```json
{
  "exact_correct": 17,
  "acceptable_estimate": 1,
  "wrong_scope": 2
}
```

Volledige backend-suite is niet leidend gebruikt, omdat lokale auth-tests falen door een bestaande passlib/bcrypt/Python 3.13 issue. Niet door deze pipeline-wijzigingen.

## Deploys

Laatste relevante Railway deploy:

- `074f77e3-c3b9-48b1-b445-c20df77a847b`
- Message: `Reject legal holding shell annual report candidates`
- Status: `SUCCESS`
- Created: `2026-07-09T16:43:26.220Z`

Eerdere relevante deploys:

- `655f0b85-fac6-45b8-8f8c-59cf90c7e39e` - `Harden source gates for jobs media and context support`
- `adff2f5f-e514-4635-953b-3ffb41c8ca37` - `Tune generic source gates for website evidence`

## Live batchresultaten

### Oude batch

Batch:

- `fc200a31-5ed6-4c8a-8767-d93fe5422a95`
- Naam: `testset`
- Labels: 16 hoog, 0 middel, 4 laag

Inhoudelijke classificatie:

- `no_candidate`: 3
- `wrong`: 7
- `catastrophic`: 4
- `near`: 3
- `exact`: 3

Probleem: veel groene kandidaten waren fout of catastrofaal fout.

### Strenge hardening batch

Batch:

- `9afda224-c797-45e4-bb31-d6bbdb2918b2`
- Naam: `testset-generic-hardening`
- Labels: 2 hoog, 4 middel, 14 laag

Inhoudelijke classificatie:

- `no_candidate`: 14
- `wrong`: 6

Conclusie:

- Catastrofale fouten weg, maar te conservatief.
- Goede websitevondsten vielen weg omdat contextsteun te breed werd geëist.

### Getunede batch

Batch:

- `8295596b-0a38-44f7-a958-31715f8ce17e`
- Naam: `testset-generic-tuned`
- Labels: 7 hoog, 2 middel, 11 laag

Inhoudelijke classificatie vóór laatste holding/shell-gate:

- `no_candidate`: 11
- `wrong`: 4
- `near`: 2
- `exact`: 2
- `catastrophic`: 1

Belangrijk:

- De resterende catastrofale fout was een holding-jaarverslag met 2 FTE als juridische entiteit, niet een vestigings-WP.
- Daarna is de generieke holding/shell-gate toegevoegd, getest en gedeployed.
- Er is nog geen nieuwe live batch gedraaid ná deploy `074f77e3-c3b9-48b1-b445-c20df77a847b`.

## Belangrijkste conclusies

1. De richting klopt: deterministische hard gates verminderen catastrofale false positives.
2. De eerste hard gates waren te streng voor websites. Website/team-pagina's moeten leidend blijven.
3. Media/search-bronnen zijn nuttig voor reviewers, maar niet groen als zelfstandige kandidaat.
4. Jaarverslagen moeten veel strenger worden behandeld op identiteit, scope en documenttype.
5. Voor 100k bedrijven moet de pipeline source-class-first denken, niet company-case-first.

## Openstaande risico's

- Website-agent kan nog misnavigeren naar de verkeerde vestiging binnen een multi-locatie website.
- Jaarverslag-agent kan nog concern/holding/legal-entity cijfers vinden die niet passen bij vestigings-WP.
- Extra bronnen kunnen goede signalen geven, maar zijn nog niet gekalibreerd voor reconciliatie.
- De live webroute blijft niet-deterministisch; dezelfde query kan andere pagina's/PDF's opleveren.
- Playwright is alleen gated fallback en nog geen volledige browser-navigatieagent.

## Aanbevolen volgende stappen

1. Draai nog één live testbatch na deploy `074f77e3-c3b9-48b1-b445-c20df77a847b`.

   Waarom eerst: valideert of de holding/shell-gate de resterende catastrofale fout in productiegedrag opvangt.

2. Voeg eval-output per node toe aan `pipeline_runs` of een aparte eval-log.

   Log minimaal: source URL, source type, identity class, scope class, rejected reason, node runtime, tool/API kosten.

3. Maak website-navigatie betrouwbaarder vóór meer reconciliatie-complexiteit.

   Concrete richting:
   - rank internal links op `team`, `medewerkers`, `over ons`, `vestigingen`, plaatsnaam/adres;
   - Playwright alleen als HTTP-tekst te kort is of relevante links ontbreken;
   - locatie/adres-match als boost voor kleine bedrijven.

4. Verplaats richting graph-like nodes zonder direct grote LangGraph-migratie.

   Eerst functies/node boundaries stabiliseren:
   - resolve website
   - fetch/render page
   - rank links
   - extract candidates
   - validate identity
   - classify scope
   - reconcile

5. Bouw pas daarna bredere LangGraph/StateGraph orchestratie.

   Waarom later: nu zit de meeste winst in bronvalidatie en evalbaarheid, niet in frameworkmigratie.

## Niet doen

- Geen bedrijfsnamen in productiecode hardcoden.
- Extra bronnen niet laten meestemmen in reconciliatie zonder eval-calibratie.
- Jaarverslag-agent niet standaard laten winnen bij kleine bedrijven.
- Geen groene kandidaat geven op proportionele schatting.
- Geen groene kandidaat geven op media/search als enige bron.
- MCP niet centraal maken voordat duidelijk is welke browser/internal tools structureel nodig zijn.

## Bestanden gewijzigd of toegevoegd

Nieuw:

- `.railwayignore`
- `backend/app/pipeline/evidence.py`
- `backend/scripts/evaluate_testset.py`
- `backend/scripts/compare_eval_with_api_batch.py`
- `backend/tests/test_evidence_eval.py`
- `docs/AGENT_ARCHITECTUUR_BRAINSTORM.md`
- `docs/TESTSET_BATCH_VERGELIJKING_2026-07-09.md`
- `docs/HANDOVER_CLAUDE_WP_PIPELINE_2026-07-09.md`

Aangepast:

- `.gitignore`
- `backend/app/pipeline/confidence.py`
- `backend/app/pipeline/reconcile.py`
- `backend/app/pipeline/runner.py`
- `backend/app/providers/live.py`
- `backend/tests/test_adaptive_website_agent.py`
- `backend/tests/test_improvements.py`
- `backend/tests/test_pipeline.py`
- `backend/tests/test_wp_uitsplitsing.py`

Let op:

- Er staan ook lokale/untracked bestanden in de worktree die niet per se bij deze wijziging horen, zoals `.claude/`, `Testbatch Jaarverslagen.xls`, `Zorggroep.xlsx` en een tijdelijke Word lockfile in `docs/`.

## Snelle verificatie voor Claude

```bash
rg -n "IKEA|Jumbo|Salon|Handmade|Pergamijn|Zuyderland|Hoensbroek|BAM|Mondriaan|Hallux|DSM|Okechamp|Fysiosittard" backend/app
```

Verwachting: geen output. Dat bevestigt dat productiecode geen testbedrijf-specifieke regels bevat.

```bash
python3 -m pytest backend/tests/test_evidence_eval.py backend/tests/test_improvements.py backend/tests/test_pipeline.py backend/tests/test_adaptive_website_agent.py -q --tb=short
```

Verwachting: `52 passed`.

