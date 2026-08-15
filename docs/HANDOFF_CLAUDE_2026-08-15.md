# Overdracht aan Claude — VR Bronnenwerkbank

**Datum:** 15 augustus 2026  
**Project:** `/Users/arryawillems/Desktop/Projects/KYC4etil`  
**Productnaam:** VR Bronnenwerkbank  
**Status van onderstaande feedback:** geanalyseerd en genoteerd, nog niet geïmplementeerd

## 1. Begin hier

Lees in deze volgorde:

1. `CLAUDE.md`
2. `docs/applicatie-spec/00-overzicht.md`
3. `docs/OPENSTAANDE_OBSERVATIES_RESEARCH_EN_UI.md`
4. Voor UI-context: `docs/applicatie-spec/03-review-ui-en-bronnen.md`

De derde bron bevat de meest recente productfeedback en de besluiten uit de
testreview. Voer die punten niet automatisch uit; bespreek eerst prioriteit en
implementatievolgorde met Arrya.

## 2. Actuele test-run

**Batch:** `VR_research_testset_50_vestigingen`  
**Batch-ID:** `f575fc9c-69fa-4294-b013-8598f21abb2f`  
**Testbestand:** `/Users/arryawillems/Downloads/VR_research_testset_50_vestigingen.csv`

De run bevat vijftig afgeronde researchruns. Gemeten gebruik:

- 344 betaalde Serper Search-calls;
- 50 betaalde Serper Places-calls;
- 46 cache-hits zonder zoekkosten;
- 3.209.807 OpenAI-inputtokens;
- 207.163 OpenAI-outputtokens;
- exacte gemeten kosten: circa USD 0,9998;
- Serper: USD 0,394;
- OpenAI: circa USD 0,606.

De som van de afgeronde centbedragen per vestiging is USD 1,02; dat verschil
komt door afronding per afzonderlijke researchrun.

## 3. Belangrijkste bevindingen

### Hallux Podotherapie Roermond

- Invoer bevat Roermond en Bredeweg 12.
- De website-resolver vond de juiste vestigingspagina.
- De uiteindelijke kandidaat werd toch de algemene teampagina.
- De juiste locatiepagina noemt vier medewerkers.
- Dit is een regressie: de oude flow behield de locatiepagina doorgaans wel.

**Kernprobleem:** de scope wordt na correcte vestigingsresolutie niet als vast
anker door alle navigatie- en extractiestappen gedragen.

### Poulissen

- Een teampagina met afzonderlijk vermelde medewerkers werd gevonden.
- Er werd geen zichtbare, serieuze telpoging opgeslagen.

**Besluit:** iedere gevonden team- of medewerkerspagina krijgt minimaal een
extractie- en telpoging, met uitleg over gemiste kaarten, namen, foto's,
lazy-loaded delen en onzekerheid.

### Aviko Lomm

**Researchrun-ID:** `bd140af5-8138-4538-9c1e-a30019a8553e`

- Een relevant nieuwsartikel werd gevonden, maar medewerkerstal en
  bewijsfragment bleven leeg.
- De gewone inspectieroute gebruikt `fetch._fetch_text()` en schakelt voor deze
  zoekresultaten niet over op de bestaande Crawl4AI-browserfallback.
- Een JavaScript-nieuwssite kan daardoor met succes laden terwijl alleen de
  lege paginaschil wordt gelezen.
- De eerste drie kandidaten waren de corporate hoofdpagina, de Nederlandse
  hoofdpagina en de Engelse contactpagina. Technisch verschillende URL's, maar
  zonder verschillend personeelsbewijs.

**Besluiten:**

- taalvarianten van dezelfde pagina gelden als één bronroute;
- algemene hoofdpagina's en contactpagina's zonder verschillend bewijs worden
  niet naast elkaar gepresenteerd;
- meerdere pagina's van één domein blijven alleen wanneer hun bewijsfunctie
  daadwerkelijk verschilt;
- Crawl4AI mag veel vaker worden gebruikt. Extra runtime is aanvaardbaar;
  Crawl4AI zelf verbruikt geen Serper- of OpenAI-tokens.

### Basisschool De Groenling

**Researchrun-ID:** `bea1f6c6-644e-4d5d-8aed-6193e68a6dee`

- De testregel bevat alleen de naam; gemeente, adres en SBI-code zijn leeg.
- Er bestaan gelijknamige scholen in Panningen en IJsselmuiden.
- De resolver koos eerst IJsselmuiden, terwijl voor Limburg waarschijnlijk
  Panningen bedoeld wordt.
- Kandidaten van beide scholen werden toch als exacte identiteit behandeld.
- Acht van de vijftien onderzochte pagina's kwamen van Scholen op de Kaart:
  zes bewaarde kandidaten en twee afgewezen portaalpagina's.
- Hierdoor ging meer dan de helft van het paginabudget naar één portal.
- De gerenderde profielpagina toont waardevolle grafieken over onder andere
  geslacht, leeftijd en functiegroepen. Platte HTML bevat vooral de koppen en
  het huidige kandidaatcontract bewaart zulke percentages niet.

**Besluiten:**

- één schoolprofiel op een sectorportaal wordt één samengestelde bron;
- intern mogen meerdere tabbladen, secties en API-responses worden gelezen,
  maar de reviewer krijgt één gebundelde bronkaart;
- eerst stabiel school-ID, plaats en adres vaststellen;
- nooit een gelijknamig profiel op een andere locatie accepteren vanwege alleen
  naam- en domeinovereenkomst;
- dynamische personeelsgrafieken via Crawl4AI of de onderliggende openbare data
  uitlezen en als aanvullend bewijs bewaren;
- na voldoende portaalonderzoek het resterende budget aan andere bronfamilies
  besteden.

### Dreessen Advocaten

**Researchrun-ID:** `2187f4ab-5606-4978-9217-059217647003`

- De advocatenpagina bevat in gewone HTML vier bij naam genoemde advocaten en
  één ondersteunende medewerker.
- Crawl4AI is hier niet nodig; de extractor telt een namenlijst momenteel niet
  omdat er geen letterlijk personeelsgetal staat.
- Zes kandidaten van hetzelfde domein werden bewaard. Inclusief afwijzingen
  werden minimaal elf van de vijftien onderzochte pagina's aan hetzelfde domein
  besteed.
- De vijf genoemde personen zijn sterke organisatiecontext, maar de website
  verdeelt ze niet over de hoofdlocatie Sittard en nevenlocatie Maastricht.
- Het adres van de Maastrichtse nevenlocatie op de website wijkt bovendien af
  van het adres in de testregel.

**Besluit:** teamlijsten als aparte bewijssoort herkennen; aantal, namen en
functies bewaren; duidelijk markeren dat het aantal uit een lijst is afgeleid;
en telzekerheid scheiden van vestigingsscope.

## 4. Frontendfeedback

De bronkaart is momenteel niet in één oogopslag begrijpelijk. Voorbeeldlabels:

- `Dit bedrijf`
- `Onbekend bereik`
- `verslagjaar 2025`
- `Geen getal gevonden`
- `Alleen context, geen WP-getal`

Problemen:

- dubbele meldingen zeggen hetzelfde;
- kleurbetekenis is niet duidelijk;
- technische classificaties staan vóór de menselijke hoofdconclusie;
- gevonden bron, extractiestatus, scope en bruikbaarheid lopen door elkaar.

Gewenste opbouw van iedere kaart:

1. één primaire conclusie in gewone taal;
2. bedrijf/identiteit;
3. geografisch bereik;
4. gevonden bewijs;
5. concrete vervolgstap.

Websites moeten bij voorkeur in een interne bronviewer openen, vergelijkbaar met
de PDF-weergave. Omdat sommige sites iframe-weergave blokkeren, is een hybride
oplossing gewenst: eerst intern proberen, daarna een duidelijke fallback naar
een nieuw tabblad.

## 5. Architectuurprincipes die uit de review volgen

- Vindst, extractie, scopebeoordeling en acceptatie zijn aparte statussen.
- Een bron mag niet “geen getal gevonden” krijgen zonder aantoonbare
  extractiepoging.
- Correcte vestigingscontext moet een invariant zijn door de hele flow.
- URL-deduplicatie alleen is onvoldoende: dedupliceer ook taalvarianten,
  paginadoel, inhoudelijke overlap en stabiele portalprofielen.
- Meerdere relevante bronnen blijven gewenst; diversiteit gaat om verschillende
  bewijsfuncties, niet om zoveel mogelijk URL's.
- Relevante context zonder absoluut WP-getal kan waardevol zijn en moet
  gestructureerd worden bewaard.
- Kostenoptimalisatie mag de bronkwaliteit niet verminderen.

## 6. Nog niet uitvoeren zonder overleg

- Geen oude flow terugzetten.
- Geen rankinggewichten veranderen zonder benchmarkvergelijking.
- Geen UI-herontwerp direct bouwen voordat de gewenste kaartstructuur kort is
  geschetst en bevestigd.
- Geen harde domeinlimiet van één bron invoeren; één domein kan meerdere echt
  verschillende bewijsbronnen bevatten.
- Geen Crawl4AI-wijziging uitvoeren zonder time-outs en foutgedrag mee te nemen.

## 7. Aanbevolen volgende stap

Maak eerst een korte implementatievolgorde met twee groepen:

1. **Veilige correcties zonder verwacht kwaliteitsverlies:** locatieanker,
   taalvarianten/inhoudelijke duplicaten, browserfallback bij lege HTML,
   expliciete extractiediagnostiek en portalprofiel-bundeling.
2. **Wijzigingen die eerst een benchmark nodig hebben:** ranking, adaptief
   stoppen, paginabudget per bronfamilie, nieuw bewijscontract voor grafieken en
   de uiteindelijke frontendhiërarchie.

Gebruik de vijftig cases als regressieset, maar herstel eerst de ontbrekende
locatievelden of een stabiele evaluatie-identiteit. Anders worden
locatiemismatches ten onrechte als researchkwaliteit beoordeeld.

## 8. Werkstatus

- Er zijn op basis van deze review geen applicatie- of infrastructuurwijzigingen
  uitgevoerd.
- Alleen `docs/OPENSTAANDE_OBSERVATIES_RESEARCH_EN_UI.md` en dit
  overdrachtsdocument zijn lokaal toegevoegd/bijgewerkt.
- Controleer de Git-status en vergelijk de lokale code met de draaiende Railway-
  deployment voordat nieuwe wijzigingen worden gemaakt; ga niet uit van een
  schone of identieke toestand.
