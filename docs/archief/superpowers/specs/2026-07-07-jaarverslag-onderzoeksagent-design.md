# Onderzoeksagent voor WP-verzameling — Design

**Project:** Vestigingsregister AI Platform (Etil / Provincie Limburg)
**Datum:** 2026-07-07
**Auteur:** Arrya Willems

---

## 1. Context

Uit een teamoverleg (actiepuntenlijst van Armina/Bas/Roger) en vervolg-mailwisseling kwamen meerdere
verbeterwensen voor de WP-verzamelingspipeline naar voren. Twee daarvan zijn samen uitgewerkt tot dit
ontwerp, omdat ze allebei neerkomen op "de agent moet zelfstandiger en slimmer zoeken, een mens hoeft
alleen te controleren en bevestigen":

1. **Periodieke jaarverslag-monitoring.** Armina/Anita houden nu handmatig bij welke bedrijven een
   nieuw jaarverslag gepubliceerd kunnen hebben — "pokkenwerk" volgens Armina. Testdata (zie
   `Testbatch Jaarverslagen.xls`) bevat de monitoringlijst: 1898 rijen ("Alles vorig jaar 16") plus
   een fallback-lijst van 97 organisaties ("Alles map Jaarverslagen") waar het jaarverslag ook bruikbaar
   is maar vorig jaar niet nodig was. Dezelfde structuur bestaat gefilterd op zorginstellingen (1106 +
   19 rijen) — dat is de afgesproken eerste testcase.

2. **Totaal-WP per CO'er (centrale organisatie).** Bij grote organisaties (bijv. Politie Limburg) wordt
   het totaal-WP nu handmatig verdeeld over vestigingen via een Excel-rekenblad met een vaste
   ratio-formule (aandeel per vestiging = WP-vestiging-vorig-jaar ÷ totaal-vorig-jaar; nieuw-totaal ×
   dat aandeel — zie `Zorggroep.xlsx` als werkend voorbeeld). Die verdeelrekenmethode bestaat al en
   wordt vernieuwd/onderhouden in een **los systeem, "VVL"** (de "Imputatie CO totaal module"), niet in
   dit project. Uit de mailwisseling met Bas is al gekozen voor **Optie 2**: de AI-tool levert een
   controleerbare lijst (CO'er, enquêtejaar, totaal-WP-huidig, totaal-WP-vorig-jaar) die Armina/Anita
   controleren en in één keer importeren in VVL — geen automatische doorschrijving.

Tijdens het ontwerpen kwam een derde, losstaand maar verwant probleem naar boven: de **bestaande
website-agent is niet adaptief**. Hij faalt structureel wanneer WP-informatie niet op een van zijn
vaste kandidaat-paginapaden staat, of wanneer personeel over meerdere subpagina's verspreid staat
(bijv. per specialisme bij een zorginstelling). Dit hoort inhoudelijk bij dezelfde behoefte
("de agent moet zelf een doel nastreven en zich aanpassen als de eerste poging niet werkt") en is
daarom in scope van deze spec opgenomen als derde deelstuk.

**Belangrijke koerscorrectie tijdens het ontwerp:** het oorspronkelijke idee was deze agent te bouwen
bovenop **Hermes Agent** (Nous Research), zelf gehost op een CPU-VPS (Hetzner/Hostinger), met een
eigen MCP-server als brug naar de backend. Na onderzoek in de bestaande code bleek dit onnodig:

- De **daadwerkelijke zoek-en-extractiestap bestaat al** (`LiveJaarverslagAgent` en `LiveWebsiteAgent`
  in `backend/app/providers/live.py`), inclusief de domeinregels (confidence-scoring, prompt-injection-
  clausule, `is_schatting`-regel) en 17 unit tests + een validatiescript. Dat opnieuw bouwen op een
  extern, general-purpose multi-kanaal-assistent-platform (gebouwd voor Telegram/Slack/Discord-gebruik)
  zou die kalibratie weggooien en dupliceren.
- Wat écht ontbrak was **planning/scheduling** (deze agents draaien nu alleen binnen een handmatige
  batch-run) en **adaptiviteit** (vaste kandidaat-paden i.p.v. een echte tool-use-loop) — beide zijn
  met de bestaande providers/Anthropic-OpenAI-integratie en `playwright` (al een dependency) op te
  lossen, zonder nieuw extern platform of hosting.
- "Hermes Agent is supergoed" bleek bij doorvragen te gaan over generieke agent-eigenschappen
  (tool-use/MCP, geheugen) die inmiddels standaard zijn en al aanwezig zijn in de bestaande stack — niet
  om iets wat dit specifieke probleem beter oplost. Hermes Agent blijft wél een kansrijke suggestie voor
  Rogers aparte AI-vraagbaak-POC (een gesprek-voerende, geheugen-gebruikende assistent — dát is het
  profiel waar zo'n platform voor gebouwd is), maar dat valt buiten deze spec.

---

## 2. Doel & Scope

**Doel:** minder handmatig zoekwerk voor Armina/Anita bij het verzamelen van WP-gegevens, door de
bestaande agents periodiek, doelgerichter en adaptiever te laten werken. Een mens controleert en
bevestigt altijd, voordat iets het register in gaat (bestaande regel, blijft gehandhaafd).

**In scope (drie deelstukken):**
1. Periodieke jaarverslag-monitoring per vestiging — nieuw jaarverslag detecteren en verwerken via de
   bestaande `LiveJaarverslagAgent`.
2. Totaal-WP per CO'er + vorig-jaar-vergelijking, als controleerbare exportlijst (Optie 2) voor
   handmatige import in VVL.
3. Adaptieve website-WP-agent: vervang de vaste kandidaat-padenlijst door een echte tool-use-loop die
   zelf linkjes volgt, meerdere pagina's combineert, en een andere aanpak probeert als de eerste niet
   lukt.

**Expliciet buiten scope:**
- De verdeel-/imputatierekenlogica over vestigingen zelf — blijft in VVL (los systeem, Bas's domein).
- Social media (Facebook) als bron — apart traject, juridisch/technisch te onzeker.
- KvK-groepsstructuur-data — geblokkeerd op de ontbrekende KvK-API-key (bestaand open punt, CLAUDE.md).
- DUO-data-koppeling — Armina vraagt nog na bij Stefan waar die data vandaan komt; aparte, kleinere
  integratie zodra bekend.
- Voorkeursbron-per-sector en contactgegevens-uitbreiding (contactpersoon/socials) — aparte
  sub-projecten, later te spec'en.
- Hermes Agent / extern agent-platform / nieuwe hosting — bewust niet gebruikt, zie koerscorrectie
  hierboven.

**Succescriterium:** Armina/Anita hoeven nog alleen te controleren en bevestigen; het periodiek
nazoeken en de eerste-poging-mislukt-probeer-opnieuw-stap gebeurt zelfstandig.

---

## 3. Architectuur

Alles blijft binnen de bestaande backend (`backend/app/`), als uitbreiding van het bestaande
provider-patroon (`PROVIDER_MODE=mock|live`, `app/providers/`). Geen nieuwe externe dependency, geen
nieuwe hosting.

### 3.1 Scheduling (deelstuk 1 en 2)

Een geplande achtergrondtaak (bijv. APScheduler binnen de FastAPI-app, of een extern cron-getriggerde
endpoint via Railway's cron-functionaliteit) die:
- wekelijks door de monitoringlijst loopt (deelstuk 1), of
- op aanvraag door een opgegeven lijst CO'ers loopt (deelstuk 2).

Verwerking gebeurt via een **begrensde concurrency-pool** (bijv. 5-10 tegelijk, niet de hele lijst van
~1900 in één keer) — dezelfde aanpak die de bestaande batch-pipeline al gebruikt voor
sectorlijsten van 40-370 bedrijven.

### 3.2 Adaptieve extractie (deelstuk 3)

`LiveWebsiteAgent` wordt uitgebreid van "vaste padenlijst + één LLM-call per pagina" naar een
tool-use-loop: het model krijgt tools als `bezoek_pagina(url)`, `volg_link(linktekst)`,
`tel_personen(paginatekst)` en beslist zelf, itererend, welke pagina's te bezoeken en wanneer het
resultaat betrouwbaar genoeg is (of een ingebouwd budget aan stappen op is). `playwright` is al een
dependency (`requirements.txt`) en dient als browse-tool.

### 3.3 Wat blijft ongewijzigd

- Confidence-scoring, reconciliatie, `is_schatting`-regel, review-wachtrij: ongewijzigd, gelden voor
  alle nieuwe resultaten net als nu.
- Prompt-injection-clausule: blijft van toepassing waar de LLM redeneert over gevonden tekst
  (extractie-stap) — al aanwezig in de bestaande prompts (zie `EXTRACT_PROMPT` in `live.py`).
- Provider-patroon: mock-tegenhangers voor beide nieuwe stukken, consistent met de rest van het project.

---

## 4. Dataflow

### Scenario 1 — Periodieke monitoring per vestiging
1. Scheduler triggert wekelijks.
2. Haal monitoringlijst op (vestigingen uit "Alles vorig jaar" + fallback "map Jaarverslagen").
3. Concurrency-pool verwerkt de lijst: roep per vestiging `jaarverslag_agent.run(naam, jaar)` aan
   (bestaande functie, ongewijzigd).
4. Geen (nieuw) jaarverslag gevonden → niets gebeurt, vestiging blijft in de lijst voor de volgende cyclus.
5. Wél gevonden (en verschillend van de laatst bekende bron/waarde) → resultaat gaat via de bestaande
   confidence-scoring naar de review-wachtrij, zoals nu al gebeurt bij chat-/bellijst-resultaten.

### Scenario 2 — Totaal-WP per CO'er (Optie 2)
1. Armina/Anita geven een lijst CO'ers op (bijv. "alle zorginstellingen", cf. de Zorginstellingen-tabbladen).
2. Concurrency-pool verwerkt de lijst: per CO'er wordt gezocht naar het totaal-WP voor het enquêtejaar
   (vaak: één jaarverslag voor de hele organisatie) én het totaal van vorig jaar.
3. Resultaat: één regel per CO'er in een exportlijst — `CO'er, enquêtejaar, totaal-WP-huidig,
   totaal-WP-vorig-jaar, bron`. Een CO'er waarvoor niets gevonden wordt, verschijnt zichtbaar als
   "niet gevonden" (niet stilzwijgend weggelaten).
4. Geen schrijfactie naar de eigen database/review-wachtrij — dit is een export voor handmatige
   controle en import in VVL.

### Scenario 3 — Adaptieve website-extractie
1. Bestaande pipeline roept (zoals nu) de website-agent aan wanneer er een `website_url` bekend is.
2. In plaats van de vaste `CANDIDATE_PATHS` te doorlopen, start een tool-use-loop: bezoek startpagina,
   laat het model beslissen of het genoeg heeft of een link wil volgen (bijv. naar een team- of
   specialisme-subpagina), tel personen eventueel over meerdere bezochte pagina's op.
3. Loop stopt bij: voldoende zekerheid (`zekerheid: hoog`), of een maximaal aantal stappen/pagina's
   (kostenbeheersing — vergelijkbaar met de bestaande `max_website_pages`-instelling).
4. Resultaat gaat via dezelfde bestaande confidence-scoring naar de review-wachtrij.

---

## 5. Error handling & edge cases

- Geen nieuw jaarverslag/geen wijziging → geen actie, blijft in de lijst voor de volgende cyclus.
- Jaarverslag gevonden maar onleesbaar/corrupt → loggen en overslaan (net als bestaande
  `pipeline_fouten` op company-niveau).
- Achtergrondtaak faalt op één bedrijf/CO'er → loggen, doorgaan met de rest van de lijst; niet de hele
  run laten vastlopen op één fout geval.
- Scenario 2: CO'er zonder resultaat moet zichtbaar "niet gevonden" in de exportlijst staan.
- Scenario 3: tool-use-loop heeft een hard maximum aan stappen/paginabezoeken om kosten en
  oneindige loops te voorkomen; bij het bereiken daarvan wordt het beste tot dan toe gevonden resultaat
  gebruikt (zelfde patroon als de huidige `best`-variabele in `LiveWebsiteAgent`).

---

## 6. Testing & validatie

- **Testbatch:** de zorginstellingen-lijst uit `Testbatch Jaarverslagen.xls` (16 rijen "vorig jaar" +
  19 rijen "map") — de al met het team afgesproken eerste testcase voor scenario 1 en 2.
- **Succesmaat:** hoeveel vestigingen/CO'ers krijgt de agent automatisch een bruikbaar resultaat voor,
  en hoe vaak moet de reviewer het voorstel corrigeren — vergelijkbaar met de bestaande MAPE/kalibratie-
  validatie (`python -m scripts.validate`) die dit project al gebruikt. Streefwaarden daar (coverage
  100%, MAPE groen 0%, kalibratie 100%) gelden als referentiekader, niet als harde eis voor dit nieuwe
  stuk.
- Scenario 3 apart valideren tegen de bekende faalgevallen die Armina/Anita nu al tegenkomen
  (WP-informatie op onverwachte pagina's / verspreid over meerdere subpagina's).

---

## 7. Open vragen / vervolgstappen

- Exacte officiële betekenis van "CB-er"/"CO-er" navragen bij Armina (functioneel begrepen als
  groepeersleutel voor vestigingen onder één centrale organisatie; `companies.cb_er` bestaat al in het
  datamodel).
- DUO-brondata: wachten op info van Armina/Stefan over de herkomst van de data, voordat dit als los
  sub-project wordt opgepakt.
- Overige sub-projecten uit de actiepuntenlijst (voorkeursbron-per-sector/zorgsector-test,
  contactgegevens-uitbreiding, bronoptimalisatie/ranking, DUO) blijven apart en worden niet in deze
  spec meegenomen.
- Rogers AI-vraagbaak-POC: Hermes Agent blijft daar een kansrijke suggestie, los van dit project.
