# Live monitoringronde 17-08-2026: wat er misging en wat daaruit te leren valt

## Eindstand van de volledige ronde

174 organisaties gecontroleerd in 19,1 minuten voor **11 cent** (som van per
organisatie afgeronde centen, dus in werkelijkheid iets meer — zie punt E).

| | vóór | ná |
|---|---|---|
| verslag over het doeljaar (2025) | 53 | **69** |
| alleen verslagjaar 2024 | 26 | 15 |
| alleen verslagjaar 2023 | 13 | 7 |
| beoordeelbare bronkaart | ~32 | **70** |
| geen bron | 108 | 110 |

Pipelinestatussen: 114 × geen bron gevonden, 19 × nieuw verslag, 16 × betere
extractie, 18 × bronkaart toegevoegd, 4 × ouder verslag genegeerd,
2 × ongewijzigd, 1 × fout.

Twee dingen vallen op. De bronkaart-achterstand is grotendeels weg (32 → 70) en
zestien organisaties schoven van 2024/2023 naar het doeljaar. Maar "geen bron"
liep met twee op: dat zijn de baselines die de hervalidatie introk (punt C).

Aanleiding: de watchlist `Jaarverslag-monitoringlijst` (205 organisaties,
`batch.jaar = 2026`, doeljaar verslagjaar 2025) had 108 organisaties zonder
enige bron. Deze notitie legt vast wat een live ronde met echte providers
(Serper, OpenAI; `OPENAI_WEB_SEARCH_ENABLED=false`) opleverde, welke fouten
daarin structureel waren, en wat er wel en niet aan is gedaan.

## Opgelost in `app/pipeline/monitoring.py`

### 1. Een ouder verslag werd nooit een beoordeelbare bron

`valideer_bron` wijst een afwijkend verslagjaar hard af. Voor de batchpipeline
is dat juist — die zoekt gericht één jaar — maar monitoring vraagt "wat is het
nieuwste dat er is?". Gevolg: `rank_bronnen` sloeg de bron over en
`_sla_moderne_bron_op` keerde terug vóór het opslaan. Van de 26 organisaties op
verslagjaar 2024 en de 13 op 2023 had er **0** een bronkaart.

Monitoring scheldt dat motief nu lokaal kwijt, met dezelfde
waarschuwingssleutel `afwijkend_verslagjaar` die `source_reviewer.py` voor de
batchflow gebruikt.

### 2. "Ongewijzigd" bevroor 66 organisaties zonder bronkaart

Dit was de grootste vondst van de live ronde. "Ongewijzigd" betekende: dezelfde
URL en geen nieuw WP-getal → niets opslaan. Ook als er nog **nooit** een
bronkandidaat voor die URL was aangemaakt. Gemeten: **66 van de 205**
organisaties hadden een bekende bron-URL en 0 bronkandidaten, inclusief
organisaties die al op verslagjaar 2025 stonden. Hun URL verandert niet meer,
dus zij zouden nooit iets te beoordelen krijgen.

Voorbeelden uit de ronde, nu wel met bronkaart en in 12–18 seconden voor
**0 cent** (geen PDF-extractie nodig): Zuyd Hogeschool (2025), Sint Jozef wonen
en zorg (2025), Stichting Punt Welzijn (2025), Proteion (2023).

Nieuwe pipelinestatus `bronkaart_toegevoegd`, bewust geen `new`/`updated`: er is
niets aan de bron veranderd, dus het mag niet als bevinding meetellen.

### 3. De skip-optimalisatie sloot precies die 66 uit

`_heeft_doeljaar_al` filterde op verslagjaar. Daarmee sloeg de ronde de
organisaties over die het verslag over het doeljaar hadden — inclusief die
zonder bronkaart. Twee eigen verbeteringen die elkaar tegenwerkten.
`bepaal_over_te_slaan_companies` eist nu beide: verslag binnen **én**
beoordeelbaar. Eén plek voor dat begrip, gebruikt door de ronde én door de
teller in `routers/monitoring.py`.

### 4. Een vondst zonder jaartal verdrong een gedateerde baseline

De ouder-dan-check kijkt alleen naar een aantoonbaar lager jaartal. Bij een URL
zonder jaartal liep de controle daar langs en zette `laatste_verslagjaar` op
None: een organisatie mét het verslag over 2025 zakte stil terug naar "verslag
zonder jaartal" en de goede URL was weg. Gereproduceerd en vastgelegd in een
regressietest.

### 5. DigiMV werd nooit bevraagd

Monitoring riep alleen de jaarverslag-agent aan. De route hangt nu ná die agent
en draait alleen als die geen verslag over het doeljaar vond. Eerste resultaat:
MeanderGroep Zuid-Limburg ging van verslagjaar 2023 naar **2025**, met
WP = 5.199 en het bewijsfragment "MeanderGroep (ultimo 2025): FTE 3.261; aantal
medewerkers 5.199" — FTE en WP correct gescheiden. Kosten: 1 cent.

Twee dingen waren daarvoor nodig:

- **Het boekjaar komt uit de `year=`-parameter van de archief-URL.** De
  bestandsnaam noemt vaak geen jaar, dus `inspect()` gaf `verslagjaar=None`.
- **Een archiefdocument wordt niet op de naamheuristiek afgewezen.** Een bestand
  heet `Jaardocument.pdf` op `digimv13.desan.nl`, dus luidde het oordeel
  "verkeerde organisatie" precies zo vaak als de naam toevallig in het
  geciteerde zinnetje stond. DigiMV identificeert scherper (exact KvK of unieke
  exacte kernnaam, fail-closed bij naamgenoten), zoals `source_reviewer.py` dat
  ook voor de gestructureerde DUO-bron doet. Bewust `possible_match` en geen
  `exact_entity`: DigiMV kent de rechtspersoon, niet de vestiging, en de
  watchlist heeft 0 KvK-nummers.

## Niet opgelost: dit zit in `app/research/` en vraagt een beslissing

### A. DigiMV wordt om het verkeerde boekjaar gevraagd — ook in de batchflow

`digimv.py::_kandidaat_boekjaren` telt twee jaar terug vanáf `gevraagd_jaar`,
omdat dat veld destijds het peiljaar was (`batch.jaar`, 2026) en het boekjaar
daarvan nog niet bestaat. Inmiddels geeft `service.py:381` `batch.jaar - 1`
door. Het archief wordt dus om boekjaar 2024 en 2023 gevraagd — **nooit om het
doeljaar zelf**.

Gemeten op 17-08-2026 bij MeanderGroep:

| `gevraagd_jaar` | boekjaren | resultaat |
|---|---|---|
| 2025 | [2024, 2023] | Bestuursverslag boekjaar **2024** |
| 2026 | [2025, 2024] | "Jaarverslag 2025 definitief gestempeld", boekjaar **2025** |

Het verslag over 2025 ligt er dus wél (jaarverantwoording over boekjaar X is
uiterlijk 31 mei X+1 aangeleverd). Monitoring zoekt nu lokaal één jaar hoger en
inspecteert met het doeljaar. **De batchflow heeft deze afwijking nog steeds.**

### B. `website_url` is bij een derde onbruikbaar

Van de 205 organisaties:

- **149** hebben `?utm_source=openai` in hun `website_url`;
- **64** hebben een domein waarin geen enkel deel van de organisatienaam
  voorkomt — dus vermoedelijk niet de eigen site.

Voorbeelden: Politie Limburg → `allebiz.nl`, CZ Groep →
`eur-lex.europa.eu`, Stichting Pedagogisch Sociaal Werk → `zorgkiezer.nl`,
MeanderGroep → `stagemarkt.nl`, Newtone Advies → `belastingadviseur-info.nl`.

Dit raakt twee mechanismen tegelijk: `domain_matches_company` levert geen
identiteit meer (waardoor alles op de naamheuristiek leunt) en de
`site:{domein}`-zoekopdrachten in `live_tools.py` zoeken op de verkeerde site.
Dat is de sterkste verklaring voor een groot deel van de "geen bron gevonden".
Een verzamelsite als officiële website is erger dan geen website: het stuurt de
zoektocht actief de verkeerde kant op.

### C. Een strikte hervalidatie gooit goede baselines weg

Twee gevallen uit de ronde verloren een bruikbare bron doordat
`validate_source` de baseline afwees:

- ANWB: `merk.anwb.nl/.../2024-Jaarrekening-ANWB-BV.pdf` (2024) → `None`
- Smurfit Kappa Roermond: `smurfit_kappa_annual_report_2023.pdf` (2023) → `None`

De reviewer ziet daar nu "Geen jaarverslag gevonden", terwijl we een plausibele
jaarrekening hadden. De intrekking is er bewust ingebouwd (een legacy-baseline
kan naar een ander bedrijf wijzen — zie de Zorgboog/Pergamijn-verwisseling),
dus dit is een afweging, geen simpele bug. Voorstel: de baseline niet leegmaken
maar bewaren met een waarschuwing, zodat strengheid geen informatie wist.

### D. De sectorvocabulaire mist de publieke sector

Gemeenten publiceren "jaarstukken" of een "programmaverantwoording", geen
"jaarverslag". Gemeente Horst aan de Maas leverde na 143 seconden niets op. De
watchlist bevat 16 gemeenten plus provincie, waterschap en veiligheidsregio.
De queryvocabulaire staat in `query_planner.py`.

### E. Ingetrokken: Serper stond wél in de kostenrapportage

Eerst opgeschreven als bevinding ("Serper-aanroepen worden niet geteld"), maar
dat was een fout in mijn eigen meetscript. `providers/search.py` roept
`record_provider_call("serper_search", kosten_micro_usd=1_000)` netjes aan. Ik
las `get_cost_summary()` uit in het ouderproces, waar `start_usage_tracking()`
nooit is aangeroepen — `check_batch_jaarverslagen` doet dat per organisatie in
een eigen task. Vandaar een leeg overzicht.

Wat er wél overblijft, is een afrondingseffect: `totaal_cents` is
`round(micro_usd / 10_000)`, dus twee Serper-aanroepen (1.000 micro-USD elk)
worden per organisatie 0 cent. Een rondetotaal dat per organisatie afgeronde
centen optelt, valt daardoor te laag uit. `usage.py::neem_token_delta`
documenteert precies deze afweging voor pipelinestappen; voor een rondetotaal
zou je de micro-USD moeten optellen in plaats van de centen.

### F. De LLM-zekerheid ís de confidence geworden, en dat spreekt CLAUDE.md tegen

`CLAUDE.md`: *"LLM-zekerheid kan een confidence-score alleen begrenzen (cap),
nooit verhogen."* De code doet het omgekeerde. `confidence.py:10,31`:

```python
ZEKERHEID_BASE = {"hoog": 0.90, "middel": 0.65, "laag": 0.35}
score = ZEKERHEID_BASE.get(zekerheid, 0.35)
```

Eén LLM-oordeel "hoog" levert dus 0,90, boven `drempel_hoog` (0,80) — label 🟢,
zonder tweede bron. De moduledocstring zegt dit ook openlijk ("zekerheid van de
LLM als primair signaal … geen MCDA-formule meer"), dus dit lijkt een bewuste
herziening waarbij `CLAUDE.md` niet is meegegaan. Dat moet één kant op: of de
regel in `CLAUDE.md` klopt niet meer, of de confidence mag niet op één
LLM-oordeel groen worden. Dit is de enige bevinding die raakt aan wanneer een
cijfer als betrouwbaar de deur uit gaat.

### G. Onbetrouwbare LLM-invoer liet één controle klappen (opgelost)

Stichting XONAR faalde met `invalid literal for int() with base 10:
'8d\xc2\x94…'`. `wp_extractie.py` deed `int(data["wp_gevonden"])` op een
LLM-veld; de bron was een PDF die als platte tekst binnenkwam, de LLM kreeg
bytes te zien en gaf een stuk van die ruis terug als aantal. Nu valt alleen die
bron weg in plaats van de hele controle. Zie `_als_aantal`.

### H. Een WP-getal uit een DigiMV-PDF kan nonsens zijn

Stichting Dichterbij kreeg `wp_gevonden = 16`, met als bewijsfragment de
samenstelling van de ondernemingsraad ("Oost Marcel Pleunis, Marleen
Hartjes-Jacobs; West …"). Dichterbij heeft duizenden medewerkers. Het getal is
geen telling maar een misgreep in een namenlijst; de bronkaart toont het als
"16 WP, met citaat" en dat leest zelfverzekerd. Cicero Zorggroep ging juist goed:
1.507 met eenheid `fte` en de waarschuwing `fte_geen_wp`, precies zoals de
FTE ≠ WP-regel vraagt. Buurtzorg Nederland leverde 12.100 met een correcte zin,
maar met `scope=concern` — dat is het concerncijfer, niet de vestiging.

Het patroon: de extractie is bruikbaar maar niet zelfstandig te vertrouwen. Voor
een namenlijst bestaat al machinerie (`wp_afgeleid_uit_naamlijst` →
`draag_naamlijsttelling_over_aan_reviewer`), maar die vlag komt van
`_llm_extract` via `raw_data`, en monitoring geeft `finding.raw` niet mee aan het
`SourceDocument`. Daardoor mist monitoring die bescherming. Dat is bewust zo
gelaten: het aanzetten trekt WP-getallen in die nu wél doorkomen, en dat is een
afweging die eerst gemeten moet worden.

### I. Bronkaarten zonder getal: 15 van de 23

Van de bronkaarten die de ronde opleverde had de meerderheid `wp_gevonden = None`.
Bij een reeds bekende URL doet de agent geen PDF-extractie meer (Zuyd: 14
seconden, 0 cent, geen enkele modelaanroep), dus de reviewer krijgt een document
zonder voorstel en moet zelf zoeken. Eén PDF-extractie kost ongeveer 1 cent
(MeanderGroep), dus de hele achterstand van 66 organisaties een getal geven kost
in de orde van € 0,60. Dat lijkt de goedkoopste kwaliteitswinst die er nog ligt,
maar het is een kostenbesluit en staat daarom hier en niet in de code.

## Wat een misser meestal wél is

Niet elke lege uitkomst is een fout. Medtronic B.V., Trespa International en
Vissers Energy Group leverden niets op, en dat is vermoedelijk correct: een
Nederlandse B.V. van een buitenlands concern publiceert geen eigen jaarverslag
met een personeelsaantal per vestiging. Voor die groep is "niets gevonden" het
eerlijke antwoord en moet de reviewer een andere route krijgen (bellijst,
handmatige bron), niet een nog agressievere zoekopdracht.
