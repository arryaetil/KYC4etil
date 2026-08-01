# Research-agent: efficiëntie- en kostentracking-verbeteringen — Design

**Project:** Vestigingsregister AI Platform (Etil / Provincie Limburg)
**Datum:** 2026-07-25
**Status:** Goedgekeurd uitgangspunt voor implementatie
**Vervolg op:** [2026-07-24-autonome-bronnenresearch-agent-design.md](2026-07-24-autonome-bronnenresearch-agent-design.md)

---

## 1. Aanleiding

Tijdens een sessie waarin de researchagent uitgebreid werd getest (na het
oplossen van een productie-incident: DuckDuckGo onbereikbaar op Railway +
verlopen Serper-credits) zijn vijf concrete verbeterpunten geïdentificeerd
door de bestaande implementatie te doorlopen:

1. De reviewer ziet nu slechts de top 3 bronkandidaten, terwijl er vaak meer
   goedgekeurde kandidaten beschikbaar zijn.
2. Twee onafhankelijke code-paden proberen hetzelfde jaarverslag te vinden.
3. Een aantal onafhankelijke researchstappen loopt onnodig sequentieel.
4. De bronreview-LLM-calls wachten sequentieel op elkaar.
5. De kostentrackingvelden op `ResearchRun` (`tokens_in`, `tokens_out`,
   `kosten_cents`) worden nergens gevuld, terwijl budgetbewaking nu actueel
   is (Serper-credits raakten op tijdens dezelfde sessie).

Alle vijf zijn kwaliteit-neutraal of kwaliteit-verbeterend; geen enkele
verandert de bronstrategie uit het vorige designdocument. Het media-pad
(nieuws/reorganisatie-queries) blijft bewust ongewijzigd altijd meelopen —
dat is expliciet overwogen en afgewezen als optimalisatie, omdat het
actualiteit boven besparing stelt.

---

## 2. Werkitem 1 — Kandidaten-limiet 3 → 8

**Doel:** de reviewer meer bruikbare kandidaten tonen dan de huidige harde
top 3, zonder de lijst onbeheersbaar te maken.

**Wijziging:**
- `app/config.py`: nieuwe setting `research_max_kandidaten: int = 8`.
- `app/research/supervisor.py`: `ResearchSupervisor` krijgt een
  `max_kandidaten`-parameter (analoog aan de bestaande `max_queries` en
  `max_pages`). De regel `ranked = rank_bronnen(validaties)[:3]` wordt
  `ranked = rank_bronnen(validaties)[:self.max_kandidaten]`.
- `app/research/service.py`: geeft `max_kandidaten=settings.research_max_kandidaten`
  door bij het aanmaken van de `ResearchSupervisor`.

**Randvoorwaarden:**
- Het bestaande paginabudget (`max_pages`, standaard 15) blijft de praktische
  bovengrens — 8 is dus een zachte cap binnen een al begrensd budget.
- De succesmetriek "bekende beste bron staat in ≥95% van de gevallen in de
  top 3" (§2 van het vorige designdocument) blijft ongewijzigd en apart
  meetbaar; een grotere opslaglimiet doet daar niets aan af.
- Frontend heeft geen harde aanname over exact 3 kandidaten (geverifieerd);
  rendert de array zoals die terugkomt.

**Risico:** laag.

---

## 3. Werkitem 2 — Jaarverslag-dubbeling wegwerken

**Doel:** voorkomen dat twee onafhankelijke strategieën hetzelfde jaarverslag
zoeken wanneer de eerste al succesvol was.

**Huidige situatie (`app/research/service.py`):** vóór de brede
supervisor-zoektocht draaien drie seed-stappen na elkaar, ongeacht elkaars
resultaat:
1. `find_officiele_website` — verpakt de al bekende website-URL.
2. `find_nieuwste_officiele_document` — eigen zoekstrategie (2 queries + tot
   4 pagina-probes) gericht op het jaarverslag van het gevraagde jaar.
3. `find_jaarverslag` — draait de volledige LangGraph-jaarverslagagent
   (eigen zoekstrategie, tot 3 retries) met hetzelfde doel als stap 2.

**Wijziging:** `find_jaarverslag` wordt alleen nog aangeroepen als stap 2
**niet** al een document heeft opgeleverd met zowel
`verslagjaar == gevraagd_jaar` als een niet-lege `wp_gevonden`. Levert stap 2
dat al op, dan wordt stap 3 overgeslagen.

**Dekking blijft behouden:** in alle andere gevallen (geen match, of wel een
match maar zonder WP-getal) blijft de huidige volgorde ongewijzigd — er gaat
dus geen bestaande vindkans verloren, alleen herhaalde inspanning wanneer de
eerste strategie al raak schoot.

**Risico:** laag — voorwaarde is expliciet en eng geformuleerd (jaar én
WP-getal moeten allebei kloppen).

---

## 4. Werkitem 3 — Seed-stappen parallelliseren

**Doel:** wachttijd verminderen zonder het aantal calls te veranderen.

**Wijziging:** in dezelfde sectie van `service.py` worden
`find_officiele_website` en `find_nieuwste_officiele_document` via
`asyncio.gather` parallel uitgevoerd in plaats van sequentieel. Deze twee
zijn functioneel onafhankelijk: beide werken op de al vooraf bekende
`context.website_url` (uit company/enrichment/Places-lookup), niet op elkaars
resultaat.

`find_jaarverslag` blijft daarna, en conditioneel (werkitem 2) — die
beslissing hangt af van de uitkomst van stap 2 en kan dus niet meelopen in
dezelfde `gather`.

**Risico:** laag — pure herordening van onafhankelijke `await`-calls.

---

## 5. Werkitem 4 — Bronreview-calls concurrent i.p.v. sequentieel

**Doel:** wachttijd verminderen tijdens de reviewfase, zonder de
beoordelingskwaliteit per kandidaat aan te tasten.

**Huidige situatie (`app/research/supervisor.py`):** de review van elk
geïnspecteerd document gebeurt in een `for`-lus met een blokkerende `await
self.reviewer.review(...)` per item.

**Wijziging:** deze calls worden via `asyncio.gather` concurrent uitgevoerd.
Aantal calls blijft gelijk; wall-clock tijd daalt naar het langzaamste van de
gelijktijdige calls in plaats van de som van allemaal.

**Bewust niet gedaan — echte prompt-bundeling:** meerdere kandidaten
samenvoegen in één LLM-prompt (minder calls, niet alleen sneller) is
overwogen en afgewezen voor dit werkitem. Risico: de fail-closed
identiteitsbeoordeling per bron (§9-achtige striktheid, "bij twijfel
afwijzen") is lastiger te garanderen wanneer één promptaanroep meerdere
bronnen tegelijk beoordeelt, en moeilijker te testen. Gegeven de expliciete
eis om kwaliteit niet aan te tasten, blijft dit een aparte, later te
heroverwegen optie — geen onderdeel van dit werkitem.

**Risico:** laag.

---

## 6. Werkitem 5 — Kostentracking vullen

**Doel:** `ResearchRun.tokens_in`, `tokens_out` en `kosten_cents` daadwerkelijk
vullen, zodat spend per run/batch zichtbaar wordt — relevant voor het
lopende budgetgesprek over Serper/OpenAI-kosten.

**Huidige situatie:** deze kolommen bestaan in het model maar worden nergens
beschreven; alle bestaande runs hebben `None`.

**Wijziging:**
- Nieuwe module `app/research/usage.py` met een `ContextVar`-gebaseerde
  accumulator. `ContextVar` is gekozen omdat deze correct meepropageert over
  `asyncio.gather`-taken (relevant na werkitem 3 en 4, die juist meer
  concurrency introduceren) — een simpel gedeeld object zonder task-isolatie
  zou hier telbaar fout kunnen gaan.
- Elke plek die tijdens een researchrun een OpenAI-call doet, registreert
  `response.usage` bij deze accumulator:
  - `_llm_extract` (WP-extractie uit paginatekst, `providers/live.py`)
  - `IntelligentSourceReviewer._llm_review` (`research/source_reviewer.py`)
  - de LangGraph-agents in `providers/live.py` (website- en
    jaarverslagagent, inclusief `_tool_use_loop` en de identiteitsclassificatie
    binnen die graven)
- `run_research_run()` (`research/service.py`) start de tracking bij aanvang
  van de run en leest de totalen uit na afloop van de supervisor, om
  `run.tokens_in` / `run.tokens_out` te vullen.
- `kosten_cents` wordt berekend via nieuwe configwaarden in `config.py`
  (prijs per 1000 input-tokens en per 1000 output-tokens apart, want die
  verschillen in prijs per model).

**Openstaand voor implementatie:** het exacte veldnaam-contract van
`response.usage` (bv. `input_tokens`/`output_tokens`) wordt bij de eerste
call-site geverifieerd tegen de daadwerkelijke OpenAI-SDK-response — dit is
nergens elders in de codebase al in gebruik, dus geen bestaand precedent om
op te leunen.

**Risico:** middel — raakt de meeste bestanden van de vijf werkitems (6-8
call-sites), maar verandert geen bestaand gedrag voor de gebruiker; puur
observability. Fouten hier zijn zichtbaar (verkeerde/ontbrekende getallen),
niet functioneel schadelijk voor de researchflow zelf.

---

## 7. Volgorde van implementatie

Aanbevolen volgorde, van laag naar hoger risico en met toenemende
afhankelijkheid:

1. Werkitem 1 (kandidaten-limiet) — volledig losstaand.
2. Werkitem 2 (jaarverslag-dubbeling) — losstaand.
3. Werkitem 3 (seed-parallellisatie) — bouwt voort op dezelfde sectie als 2.
4. Werkitem 4 (reviewer-concurrency) — losstaand van 1-3.
5. Werkitem 5 (kostentracking) — als laatste, omdat deze het meest gebaat is
   bij een codebase die al de concurrency-vorm van werkitem 3/4 heeft (om de
   `ContextVar`-propagatie meteen goed te testen).

Elk werkitem is los te verifiëren met een testrun tegen de bestaande
testset (`data/testset.csv`) en de bestaande pytest-suite
(`pytest tests/ -q`).
