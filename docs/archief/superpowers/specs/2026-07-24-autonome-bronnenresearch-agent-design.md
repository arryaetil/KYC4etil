# Autonome bronnenresearch-agent — Design

**Project:** Vestigingsregister AI Platform (Etil / Provincie Limburg)
**Datum:** 2026-07-24
**Status:** Goedgekeurd uitgangspunt voor implementatie

---

## 1. Doel

De Research Agent zoekt per organisatie autonoom naar de meest actuele en
relevante openbare bronnen voor informatie over werkzame personen (WP). De
agent past de zoekstrategie aan op de beschikbare bronsoorten, verzamelt
meerdere kandidaten, controleert identiteit, scope, actualiteit en
bronkwaliteit, en legt de best onderbouwde resultaten voor aan een menselijke
reviewer.

Een jaarverslag is één mogelijke bron, niet het doel van de agent. Kleine
organisaties hebben vaak geen jaarverslag; daar moeten de officiële website,
recente media en andere controleerbare openbare bronnen het onderzoek dragen.
Voor grote organisaties worden officiële documenten altijd aangevuld met
recente media, zodat ontwikkelingen na de verslagperiode zichtbaar blijven.

De agent schrijft nooit zelfstandig een bron of WP-waarde definitief naar het
Vestigingsregister. Alleen een reviewer kan een bron en waarde accepteren.

---

## 2. Succesdefinitie

De agent is succesvol wanneer de reviewer niet meer zelf het open web hoeft af
te zoeken, maar voor vrijwel iedere organisatie een kleine, controleerbare set
van relevante bronkandidaten ontvangt.

### Meetbare criteria op de benchmark

- De bekende beste bron staat in minimaal 95% van de gevallen in de top 3.
- De bekende beste bron staat in minimaal 85% van de gevallen op positie 1.
- Een bron van een aantoonbaar verkeerde organisatie staat nooit op positie 1.
- Verslagjaar, publicatiejaar en informatiepeilmoment worden afzonderlijk
  behandeld.
- Iedere kandidaat heeft bewijs, herkomst, validatieresultaten en een
  verklaarbare score.
- Een zoekactie zonder resultaat wordt expliciet als `niet_gevonden`
  geregistreerd.
- De reviewer kan een kandidaat accepteren, een alternatief kiezen, alles
  afwijzen of zelf een bron toevoegen.
- Reviewerkeuzes worden als evaluatiedata bewaard.

WP-extractie wordt apart beoordeeld van bronvinding. Een correcte bron met een
verkeerd geëxtraheerd getal is een extractiefout, geen bronvindingsfout.

---

## 3. Bronstrategie

### 3.1 Officiële-organisatieonderzoeker

Doorzoekt het officiële domein op:

- over-ons-, team- en organisatiepagina's;
- nieuws- en persberichten;
- vestigings- en locatiepagina's;
- vacatures met expliciete organisatieomvang;
- jaarverslagen, jaarrekeningen, bestuursverslagen en downloads;
- sitemaps en relevante interne links.

Dit pad is doorgaans leidend voor kleine organisaties.

### 3.2 Documentonderzoeker

Zoekt op het officiële domein en betrouwbare publicatieportals naar:

- jaarverslagen;
- jaarrekeningen;
- bestuursverslagen;
- sociale jaarverslagen;
- impact- en duurzaamheidsrapporten;
- wettelijke jaarverantwoording;
- officiële sector- en overheidsdocumenten.

Verslagjaar en publicatiejaar zijn verschillende velden. Een verslag over 2025
dat in 2026 wordt gepubliceerd blijft verslagjaar 2025.

### 3.3 Recente-mediaonderzoeker

Zoekt standaard binnen een configureerbaar actualiteitsvenster, aanvankelijk
18 maanden, naar:

- regionaal en landelijk nieuws;
- vakmedia;
- interviews en persberichten;
- groei, reorganisatie, overname, ontslagen en nieuwe locaties;
- expliciete medewerkerstaantallen.

Media is aanvullend bewijs en een actualiteitssignaal. Het overschrijft een
officiële bron niet stilzwijgend. Tegenstrijdigheden worden zichtbaar gemaakt.

### 3.4 Overige openbare bronnen

Bedrijvengidsen, sociale bedrijfsprofielen en zoekresultaatsnippets kunnen als
zoekaanwijzing of ondersteunend bewijs dienen. Ze krijgen nooit dezelfde
autoriteit als een expliciete officiële publicatie en mogen zonder
ondersteunende bron geen hoge aanbeveling krijgen.

---

## 4. Adaptieve onderzoeksrouter

De agent hoeft de organisatie niet vooraf perfect als klein of groot te
classificeren. Een goedkope eerste scan bepaalt welke paden extra budget
krijgen.

| Situatie | Primair pad | Aanvullend pad |
|---|---|---|
| Kleine organisatie, geen documenten | Officiële website | Recente lokale/vakmedia |
| Middelgrote organisatie | Website + documenten | Recente media |
| Grote organisatie | Officiële documenten | Website + recente media |
| Zorg/onderwijs/overheid | Wettelijke/sectorportals | Eigen domein + media |
| Onbekend | Brede eerste scan | Supervisor verdeelt vervolgbudget |

Alle paden mogen parallel draaien. De supervisor bepaalt na iedere ronde of:

1. voldoende bewijs is gevonden;
2. een bronconflict nader onderzoek vereist;
3. een nieuwe zoekvraag nodig is;
4. het onderzoeksbudget is bereikt.

---

## 5. Open-source adoptiestrategie

We bouwen geen algemeen researchplatform opnieuw en vervangen de bestaande
KYC4etil-applicatie niet. We nemen gerichte, bewezen componenten en patronen
over.

### 5.1 Open Deep Research — researchregie

**Repo:** `langchain-ai/open_deep_research`
**Licentie:** MIT
**Gebruik:** primaire technische referentie

Overnemen/adopteren:

- iteratieve `search -> summarize -> reflect -> follow-up`-loop;
- tool-callende researcher;
- configureerbare zoekproviders;
- onderzoeksbudgetten en stopcriteria;
- parallelle researchtaken;
- conditionele routing;
- traceerbare broncontext;
- human-in-the-loop interrupt/approval-patroon.

Niet overnemen:

- algemene rapportgenerator;
- generieke eindrapportprompt;
- deployment en UI;
- researchcomplexiteit die geen bijdrage levert aan bronvinding.

### 5.2 Crawl4AI — website-exploratie

**Repo:** `unclecode/crawl4ai`
**Licentie:** Apache 2.0 met aanvullende attributievoorwaarde; exacte
licentiecontrole verplicht vóór distributie.

Voorkeursgebruik:

- sitemap- en URL-discovery;
- async crawling en browserfallback;
- JavaScript-pagina's;
- relevante-paginaselectie;
- schone Markdown-output;
- crawlbudget, caching en resume.

De eerste implementatie abstraheert crawling achter een eigen interface. Zo kan
de bestaande lichte fetcher blijven werken en kan Crawl4AI later zonder
domeinlogica te herschrijven worden aangesloten.

### 5.3 GPT Researcher — multi-source verzameling

**Repo:** `assafelovic/gpt-researcher`
**Licentie:** Apache 2.0

Als referentie gebruiken voor:

- parallelle zoekvragen;
- brontracking;
- contextaggregatie;
- filtering van verzamelde resultaten.

Niet als volledige runtime adopteren; dat zou bestaande LangGraph- en
KYC4etil-logica dupliceren.

### 5.4 Company Research Agent — gespecialiseerde nodes en voortgang

**Repo:** `guy-hartstein/company-research-agent`

Als referentie gebruiken voor:

- taakverdeling over company-, document- en news-researchnodes;
- async jobstatus;
- voortgang per onderzoekspad;
- aggregatie en presentatie.

### 5.5 Niet adopteren in de MVP

- Firecrawl-code: AGPL-risico; alleen als geïsoleerde service na licentiecheck.
- STORM: geoptimaliseerd voor kennisartikelen, niet voor gerichte
  bronselectie.
- FinRobot: te sterk gericht op beursgenoteerde bedrijven en financiële
  analyse.
- Een general-purpose agentplatform zoals Hermes/OpenClaw: te brede runtime en
  duplicatie van bestaande domeinlogica.

---

## 6. Architectuur

```text
KYC4etil FastAPI + database + review-UI
                    |
           Research Supervisor
        (Open Deep Research-patroon)
                    |
       +------------+-------------+
       |            |             |
       v            v             v
Website Research  Document      Recent Media
crawler-interface bestaande     multi-query
                 PDF-extractie  research-loop
       +------------+-------------+
                    |
                    v
         Evidence Normalizer
                    |
                    v
      Validatie, deduplicatie en ranking
                    |
                    v
             Top-3 bronkandidaten
                    |
                    v
            Human-in-the-loop review
```

De bestaande confidence- en reconciliatielogica blijft verantwoordelijk voor
de uiteindelijke WP-kandidaat. Bronranking is een aparte beslissing en mag niet
stilzwijgend met de bestaande WP-confidence worden vermengd.

---

## 7. Uniform bronkandidaatmodel

Alle onderzoekspaden leveren hetzelfde semantische object:

```json
{
  "company_id": "uuid",
  "url": "https://example.nl/over-ons",
  "canonical_url": "https://example.nl/over-ons",
  "brontype": "officiele_website",
  "documenttype": "teampagina",
  "titel": "Ons team",
  "verslagjaar": null,
  "publicatiedatum": "2026-05-14",
  "informatie_peilmoment": "2026-05",
  "wp_gevonden": 47,
  "eenheid": "werkzame_personen",
  "scope_class": "concern",
  "identity_class": "exact_entity",
  "bewijsfragment": "Ons team bestaat uit 47 medewerkers",
  "bron_pagina": null,
  "autoriteit_score": 0.95,
  "actualiteit_score": 0.90,
  "identiteit_score": 1.0,
  "relevantie_score": 0.93,
  "ranking_score": 0.94,
  "validaties": {},
  "waarschuwingen": [],
  "status": "voorgesteld"
}
```

### Vereiste scheiding van tijdsvelden

- `verslagjaar`: formele verslagperiode van een document;
- `publicatiedatum`: datum waarop de bron gepubliceerd is;
- `informatie_peilmoment`: moment waarop de gevonden WP-waarde betrekking
  heeft.

### Vereiste scheiding van scores

- bronranking: hoe geschikt is deze bron om aan een reviewer te tonen;
- extractiezekerheid: hoe zeker is de gevonden WP-interpretatie;
- bestaande kandidaatconfidence: mag de gevonden WP-waarde als sterk
  registervoorstel worden gezien.

---

## 8. Ranking en validatie

Ranking is deterministisch en verklaarbaar. Alle gewichten en drempels staan in
`app/config.py`.

Factoren:

- juiste organisatie-identiteit;
- officieel domein of betrouwbare publicatiebron;
- expliciete en passende document-/paginatype;
- actualiteit ten opzichte van het gevraagde peilmoment;
- juiste verslagperiode;
- expliciet WP-bewijs;
- passende organisatorische scope;
- bereikbaarheid en leesbaarheid;
- bevestiging door onafhankelijke bron;
- waarschuwingen, bijvoorbeeld FTE in plaats van WP.

Harde uitsluitingen:

- `identity_class == mismatch`;
- onbereikbare of lege bron;
- aantoonbaar verkeerd verslagjaar wanneer een specifiek jaar gevraagd is;
- vacature-/directorypagina als enige basis voor een hoge aanbeveling;
- bron zonder herleidbare URL.

De top 3 moet waar mogelijk brondiversiteit bevatten: niet drie kopieën van
dezelfde publicatie of drie zoekresultaten die naar hetzelfde document wijzen.

---

## 9. Human-in-the-loop

Per kandidaat kan een reviewer:

- accepteren;
- afwijzen met reden;
- een lager gerankte kandidaat kiezen;
- alle kandidaten afwijzen;
- een eigen URL toevoegen;
- de bron wel accepteren maar de extractie corrigeren.

Iedere beslissing bewaart:

- reviewer;
- tijdstip;
- beslissing;
- reden;
- gekozen bron;
- eventuele gecorrigeerde waarde;
- versie van ranking/configuratie.

Reviewerfeedback verandert niet automatisch prompts of gewichten. Het wordt
eerst evaluatiedata; aanpassingen gebeuren gecontroleerd en regressiegetest.

---

## 10. Benchmark

De bestaande monitoringlijst vormt het startpunt, maar wordt uitgebreid tot een
golden set met minimaal:

- kleine organisaties zonder jaarverslag;
- middelgrote organisaties met website- en mediabronnen;
- grote organisaties met jaarverslag én recente media;
- concern/vestiging-ambiguïteit;
- foutieve lookalike-bronnen;
- documenten die in jaar N+1 over verslagjaar N zijn gepubliceerd;
- bronnen met alleen FTE;
- geen-resultaatgevallen.

Per testcase:

- organisatie-identificatoren;
- gevraagde periode;
- geaccepteerde bron-URL('s);
- relevante bronsoorten;
- verwachte scope;
- eventueel WP-ground-truth;
- bekende foutieve bronnen;
- toelichting.

---

## 11. Niet-functionele eisen

- Bestaand `mock|live` providerpatroon behouden.
- Python 3.10+-compatibel.
- Iedere researchrun is begrensd op zoekopdrachten, pagina's, tijd en kosten.
- Externe content blijft onbetrouwbare input; prompt-injectionclausule blijft
  verplicht.
- Respecteer robots.txt, rate limits en bronvoorwaarden.
- Eén falende bron of onderzoeker mag de volledige batch niet stoppen.
- Iedere pipelinefase logt status, duur en foutinformatie.
- Geen automatische registermutatie zonder reviewer.
- Open-source licenties en attributie worden vóór code-adoptie geregistreerd.

---

## 12. Gefaseerde oplevering

1. Benchmark + uniform bronkandidaatmodel.
2. Multi-query/multi-provider discovery, canonicalisatie en deduplicatie.
3. Deterministische bronvalidatie en ranking.
4. Research supervisor met website/document/media-routing.
5. Human-in-the-loop API en review-UI.
6. Benchmarkevaluatie, kalibratie en gecontroleerde monitoringuitrol.
