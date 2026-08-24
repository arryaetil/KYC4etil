# Vestigingsregister AI Platform — Applicatie-spec

> **Actieve stand sinds 13 augustus 2026:** KYC4etil is een bronnenwerkbank.
> De canonieke stroom is `User → Batch → Company → ResearchRun → BronKandidaat
> → reviewbeslissing`. De oude `Candidate`-, chat-, bellijst- en registerstroom
> hieronder is alleen historische context en is niet meer actief.

> Volledige beschrijving van hoe de applicatie op dit moment werkt: doel, architectuur,
> authenticatie, pipeline, externe diensten, datamodel, scoring, review-UI en deployment.
> Voor de historische bouwredenen en oorspronkelijke requirements blijft
> [`PLATFORM_DOCUMENTATIE_v2.md`](../PLATFORM_DOCUMENTATIE_v2.md) de bron van waarheid —
> deze map beschrijft de applicatie zoals ze nu daadwerkelijk werkt, inclusief alles wat
> sindsdien is bijgebouwd (identiteits-/scope-classificatie, bronnen-first review-UI, PDF-modal).

## Inhoud van deze map

1. [Pipeline en agents](01-pipeline-en-agents.md) — de volledige verwerkingsketen per bedrijf,
   de LangGraph-onderzoeksagents (website + jaarverslag), de autonome
   bronnenresearch-supervisor, en welke externe diensten
   (OpenAI, Serper, Google Places, crawl4ai) waar en waarom worden ingezet.
2. [Datamodel en scoring](02-datamodel-en-scoring.md) — alle databasetabellen, de
   reconciliatieregels en de confidence-scoreformule.
3. [Review-UI en bronnenpresentatie](03-review-ui-en-bronnen.md) — hoe reviewers (Armina,
   Anita) het resultaat te zien krijgen, inclusief de bronnen-first-layout, de
   zekerheidsindicator en de PDF-viewer.
4. [Authenticatie en deployment](04-authenticatie-en-deployment.md) — login, rollen, en hoe
   de applicatie op Railway draait (mock- vs. live-modus).
5. [Bronnenverzameling en datacontract](05-bronnenverzameling-en-datacontract.md) — het
   proces van aanlevering tot uitlevering, welke gegevens VVL moet meesturen en
   waarom, en wat het systeem aantoonbaar niet weet.

## Doel van de applicatie

Provincie Limburg (via Etil Research Group) houdt een **Vestigingsregister** bij: per
vestiging van een bedrijf in Limburg het aantal **Werkzame Personen (WP)** — niet FTE, dat
is een bewust andere maateenheid en wordt nooit stilzwijgend omgerekend. Dit register werd
voorheen handmatig samengesteld door reviewers die zelf websites en jaarverslagen doorzochten
en bedrijven belden. Dit platform automatiseert het grootste deel van dat opzoekwerk: een
pipeline verzamelt en verifieert WP-cijfers uit publieke bronnen, en presenteert het
resultaat aan een menselijke reviewer met een expliciete zekerheidsinschatting — de reviewer
beslist, het systeem doet het voorwerk.

**Belangrijk ontwerpprincipe:** de AI-pipeline levert nooit rechtstreeks data aan het
register. Een reviewer beoordeelt bronnen en de kwaliteit van het geëxtraheerde WP.
Het oorspronkelijke gevonden aantal blijft bij een menselijke correctie altijd bewaard.

De actieve researchservice maakt vóór iedere run een klein routeplan op basis van
de beschikbare SBI-context. Website en media zijn de basis; DUO, DigiMV,
team-/afspraakonderzoek en formele documenten worden alleen toegevoegd wanneer
het organisatieprofiel daar aanleiding toe geeft. Iedere route krijgt een eigen
eindstatus, zodat `niet_gevonden` onderscheiden blijft van `technisch_onvolledig`.

## Architectuur op hoofdlijnen

```
CSV-upload (20 testbedrijven, of een echte batch)
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ Backend — FastAPI (Python), SQLAlchemy 2, async pipeline     │
│                                                               │
│  Batch → per Company:                                        │
│    1. Verrijking       (locatie/contactdata: KvK/Places)      │
│    2. Website-agent     (LangGraph state-graph)                │
│    3. Jaarverslag-agent (LangGraph state-graph, met retries)   │
│    4. Bronnenresearch   (website/document/media → top-3)       │
│    5. Extra bronnen     (aanvullende, niet-reconciliërende)     │
│    6. Identity/scope-classificatie (per gevonden bron)         │
│    7. Reconciliatie    (welke bron wint bij verschil)          │
│    8. Confidence scoring (§9 — gewogen som + caps)             │
│                                                               │
│  Resultaat: Candidate met wp_kandidaat, confidence_label       │
│  (🟢/🟡/🔴), score_breakdown, en alle onderliggende            │
│  AgentResult-bronnen (elk met eigen zekerheid + classificatie)  │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ Frontend — React 19 + Vite + Tailwind                         │
│                                                               │
│  Reviewer opent een bedrijf → bronnen-first detailpagina:      │
│  bronnen bovenaan (met zekerheidsbadge, PDF-modal), dan        │
│  vestigings-/contactgegevens, dan score-uitleg.                │
│  Reviewer keurt goed, corrigeert, of stuurt naar bellijst/chat.│
└─────────────────────────────────────────────────────────────┘
```

**Provider-pattern (mock vs. live):** elke externe afhankelijkheid (locatie-lookup,
website-agent, jaarverslag-agent, identity/scope-classifier) zit achter een Python
`Protocol`-interface met twee implementaties: een `Mock*`-variant (volledig deterministisch,
geen netwerkverkeer, gebruikt voor de 20 testbedrijven en voor `pytest`/`scripts.validate`)
en een `Live*`-variant (roept echte externe diensten aan). Welke variant actief is, bepaalt
de environment-variabele `PROVIDER_MODE` (`mock` of `live`) — zie
[04-authenticatie-en-deployment.md](04-authenticatie-en-deployment.md).

## Belangrijkste domeinregels (blijven gelden, overal)

- Een proportionele schatting (`is_schatting=True`) mag nooit het label 🟢 krijgen.
- LLM-zekerheid kan een confidence-score alleen begrenzen (cap), nooit verhogen.
- `count_lb == count_nl` (alles in Limburg) telt als locatie-eenduidig.
- Chat-antwoorden gaan altijd via de review-wachtrij, nooit direct het register in.
- FTE ≠ WP: nooit stilzwijgend omrekenen.
- Identity/scope-classificatie is puur informatief voor de reviewer — het is nooit een
  hard gate en beïnvloedt de reconciliatie/confidence-berekening niet.
