# Openstaande observaties: researchkwaliteit en review-UI

**Vastgelegd op:** 15 augustus 2026  
**Status:** alleen genoteerd — nog niets geïmplementeerd

Dit document verzamelt de bevindingen uit de eerste beoordeling van de nieuwe
researchflow en frontend. Het zijn onderzoeks- en ontwerpvragen; er is op basis
hiervan nog geen code aangepast.

## 1. Exacte vestigingscontext mag niet verloren gaan

### Hallux Podotherapie Roermond

- De invoer specificeert Roermond en Bredeweg 12.
- De researchflow vindt de juiste vestigingspagina, maar de uiteindelijke
  kandidaat wordt de algemene teampagina.
- Op de exacte vestigingspagina staan vier medewerkers vermeld.
- De eerdere flow behield deze vestigingspagina doorgaans wel en kwam daardoor
  meestal tot vier medewerkers.

**Gewenste eigenschap:** zodra een exacte vestigingspagina is gevonden, blijft
die het vaste anker van de research. Een algemene organisatie- of teampagina mag
de exacte vestigingsbron niet vervangen. Dit moet later als regressietest worden
vastgelegd.

## 2. Een gevonden teampagina ook werkelijk analyseren

### Paulussen

- De flow vindt een pagina zoals **Mijn team** waarop medewerkers afzonderlijk
  worden vermeld.
- Er lijkt geen serieuze vervolgpoging te zijn gedaan om de vermeldingen te
  tellen of als personeelsbewijs te structureren.
- Ook wanneer automatische extractie onzeker is, hoort de flow minimaal een
  telling te proberen en zichtbaar te maken waarom die telling wel of niet
  betrouwbaar is.

**Onderzoeksvraag:** wordt Crawl4AI in de huidige flow daadwerkelijk ingezet op
dit soort teamoverzichten, en gebeurt dat vroeg en consequent genoeg? Later
controleren of de extractor onder meer namen, profielkaarten, lazy-loaded
onderdelen, foto's met onderschrift en verder naar beneden geplaatste
teamleden meeneemt.

**Gewenst resultaat:** bijvoorbeeld: “12 personen herkend op de teampagina;
telling onzeker omdat 2 kaarten geen naam/functie bevatten.” Geen stille
overgang van een bruikbare teampagina naar “geen getal gevonden”.

## 3. De bronkaart vertelt nu geen helder verhaal

De huidige kaart bevat onder meer:

- `Dit bedrijf`
- `Onbekend bereik`
- `verslagjaar 2025`
- `Geen getal gevonden`
- `Alleen context, geen WP-getal`
- `Geen citaat geëxtraheerd — beoordeel de bron zelf`

### Problemen

- In één oogopslag is niet duidelijk wat er wél en niet is gevonden.
- `Geen getal gevonden` en `Alleen context, geen WP-getal` zeggen vrijwel
  hetzelfde.
- De afwijkende kleur van `Onbekend bereik` suggereert betekenis of urgentie,
  maar legt niet uit welke.
- `Verslagjaar 2025` staat zonder dezelfde visuele behandeling tussen badges,
  waardoor de hiërarchie willekeurig aanvoelt.
- Technische classificaties worden getoond zonder eerst de hoofdconclusie te
  geven.
- De kaart maakt onvoldoende onderscheid tussen:
  1. bron hoort bij het juiste bedrijf;
  2. bron hoort bij de juiste vestiging/regio;
  3. bron bevat personeelsinformatie;
  4. bron bevat een bruikbaar WP-getal;
  5. menselijke beoordeling is nog nodig.

### Gewenste richting

Iedere bronkaart moet beginnen met één gewone, ondubbelzinnige samenvatting,
bijvoorbeeld:

> **Juiste bedrijfswebsite gevonden, maar nog geen medewerkerstal uitgelezen.**
> De locatie waarop deze informatie betrekking heeft is nog niet vastgesteld.

Daaronder kan compacte ondersteunende informatie staan, zonder dubbele labels:

- **Bedrijf:** komt overeen
- **Bereik:** nog niet vastgesteld
- **Bewijs:** geen medewerkerstal uitgelezen
- **Actie:** teampagina verder analyseren of bron handmatig beoordelen

Kleur moet steeds één vaste betekenis hebben en mag niet het enige middel zijn
om status over te brengen. Het is nog te bepalen welke beperkte kleurenset het
best bij de taken van de reviewer past.

## 4. Een gevonden nieuwsartikel wordt niet altijd werkelijk uitgelezen

### Aviko Lomm

- De mediazoekroute vond onder meer artikelen van Omroep Venlo en L1 over het
  personeel van Aviko in Lomm.
- In minimaal één gevonden artikel staat personeelsinformatie, maar de
  opgeslagen kandidaat bevat geen medewerkerstal en geen bewijsfragment.
- De huidige HTML-inspectieroute gebruikt voor zo'n mediapagina een eenvoudige
  HTTP-ophaling. Wanneer de server wel een pagina teruggeeft maar de
  artikeltekst pas met JavaScript wordt geladen, wordt alleen de paginaschil
  gelezen.
- De Crawl4AI-browserfallback bestaat elders in de code, maar wordt vanuit deze
  inspectieroute voor zoekresultaten niet aangeroepen.
- Het systeem registreert de bron daardoor als actuele context, terwijl de
  relevante zin uit het artikel niet in de frontend verschijnt.

**Gewenste eigenschap:** een gevonden nieuws- of teampagina die na eenvoudige
HTML-ophaling geen betekenisvolle hoofdinhoud bevat, krijgt een browser-rendered
vervolgpoging. De uiteindelijke kandidaat vermeldt vervolgens het gevonden
bewijs of een concrete extractiefout.

**Besluit:** Crawl4AI mag hiervoor ruim worden ingezet. Het veroorzaakt vooral
extra runtime en geen afzonderlijk zoek- of modeltokenverbruik. Een iets langere
doorlooptijd is aanvaardbaar wanneer daardoor relevante personeelsinformatie
wel wordt uitgelezen. De precieze trigger en maximale looptijd moeten later nog
worden vastgesteld, maar te terughoudend gebruik is niet gewenst.

### Drie kandidaten van hetzelfde officiële domein

Bij Aviko zijn de eerste kandidaten technisch verschillende URL's:

- de corporate hoofdpagina;
- de Nederlandse corporate hoofdpagina;
- de Engelse contactpagina.

Ze leveren echter alle drie geen medewerkerstal of bewijsfragment. De eerste
twee zijn inhoudelijk grotendeels dezelfde onderzoeksroute. De huidige
deduplicatie vergelijkt hoofdzakelijk de volledige genormaliseerde URL en de
portfolio begrenst herhaling per rol, maar voorkomt niet dat meerdere
laag-informatieve pagina's van hetzelfde domein boven een inhoudelijk sterker
nieuwsartikel komen.

**Besluit:** taalvarianten en algemene duplicaten worden niet als afzonderlijke
bronkandidaten gepresenteerd. Een Engelse en Nederlandse variant van dezelfde
pagina mogen dus niet meerdere posities innemen. Ook een hoofdpagina en
contactpagina zonder verschillend personeelsbewijs horen niet naast elkaar in
de belangrijkste bronnenlijst.

Meerdere pagina's van hetzelfde domein blijven alleen toegestaan wanneer ze
daadwerkelijk verschillende informatie of bewijsfuncties hebben, bijvoorbeeld
een locatiespecifieke teampagina naast een formeel document. De deduplicatie
moet daarom niet alleen naar de volledige URL kijken, maar ook naar taalvariant,
paginadoel en inhoudelijke overlap.

## 5. Een sectorportaal is één bronprofiel, niet iedere subpagina een nieuwe bron

### Basisschool De Groenling

- De testregel bevat alleen de naam `De Groenling`; gemeente, adres en SBI-code
  zijn leeg.
- Er bestaan minimaal twee basisscholen met deze naam: één in Panningen en één
  in IJsselmuiden.
- De resolver koos de contactpagina van de school in IJsselmuiden als officiële
  website, terwijl voor Limburg waarschijnlijk de school in Panningen wordt
  bedoeld.
- De uiteindelijke kandidaten mengen pagina's van beide scholen en classificeren
  ze toch als exacte identiteit.
- Van de vijftien onderzochte pagina's kwamen er acht van Scholen op de Kaart:
  zes bewaarde kandidaten en twee afgewezen pagina's van andere scholen.
- Daarmee gebruikte één portal meer dan de helft van het beschikbare
  paginabudget. Het is aannemelijk dat hierdoor andere complementaire bronnen
  niet zijn onderzocht.

De profielpagina bevat wel waardevolle personeelsinformatie, zoals de verdeling
van mannen en vrouwen, leeftijden en functiegroepen. De platte HTML bevat vooral
de koppen; de waarden van de grafieken worden dynamisch geladen. De huidige
bronkandidaat bewaart bovendien alleen een WP-getal en bewijsfragment en heeft
geen passend contract voor zulke procentuele personeelskenmerken. Daarom
verschijnen deze gegevens niet in de frontend, ook wanneer de gebruiker ze in
de gerenderde pagina kan zien.

**Besluit:** alle pagina's onder één specifiek schoolprofiel op Scholen op de
Kaart worden als één samengestelde bron behandeld. De flow mag intern meerdere
tabbladen, secties of API-responses uitlezen, maar presenteert daarvan één
bronkaart met gebundeld bewijs. Pagina's van een ander school-ID gelden nooit
als dezelfde vestiging alleen omdat de naam en het portaldomein overeenkomen.

**Gewenste onderzoeksrichting:**

- eerst het juiste schoolprofiel vaststellen met plaats, adres en waar mogelijk
  een stabiel school-ID;
- na die keuze binnen dat ene profiel blijven;
- grafiekwaarden met Crawl4AI of de onderliggende openbare data/API uitlezen;
- de gevonden personeelskenmerken als aanvullend bewijs tonen, ook wanneer ze
  nog geen absoluut WP-totaal opleveren;
- na voldoende onderzoek van het profiel het resterende budget gebruiken voor
  andere bronfamilies, in plaats van nog meer portaalpagina's te openen.

## 6. Een zichtbare namenlijst moet als telbaar bewijs worden herkend

### Dreessen Advocaten

- De gewone HTML van de advocatenpagina bevat vier bij naam genoemde advocaten
  en één bij naam genoemde ondersteunende medewerker.
- Hiervoor is geen browser-rendering of Crawl4AI nodig; de tekst is al direct
  beschikbaar.
- De extractor bewaart toch geen WP-getal of bewijsfragment. De huidige prompt
  is gericht op een letterlijk genoemd personeelsgetal en telt een lijst met
  afzonderlijke namen niet als afgeleid bewijs.
- Zes kandidaten van dezelfde website werden bewaard. Inclusief afgewezen
  nieuws-, publicatie- en vacaturepagina's onderzocht de flow minimaal elf
  pagina's van hetzelfde domein binnen een totaalbudget van vijftien pagina's.
- Daardoor werd opnieuw veel budget besteed aan één website zonder dat de
  duidelijkste personeelsbron goed werd benut.

De website noemt een hoofdlocatie in Sittard en een nevenlocatie in Maastricht,
maar verdeelt de vijf genoemde personen niet over die locaties. De bron is dus
sterk organisatiebewijs, maar ondersteunt niet zonder meer een registratie van
vijf WP voor alleen de Maastrichtse vestiging. Bovendien wijkt het adres in de
testregel af van het adres op de website en moet dit als controlesignaal worden
getoond.

**Besluit:** herken expliciete teamlijsten als een aparte bewijssoort. Bewaar
zowel het aantal herkende personen als de onderliggende namen/functies en geef
duidelijk aan dat de telling uit een lijst is afgeleid. Scheid vervolgens de
zekerheid over de telling van de zekerheid over de vestigingsscope. Een
organisatiebrede telling mag als waardevolle context worden getoond, ook als de
locatieverdeling nog onbekend is.

## 7. Websites binnen de applicatie bekijken

De voorkeur is om niet voor iedere website een nieuw browsertabblad te openen,
maar de reviewer in de bronnenwerkbank te houden, vergelijkbaar met de huidige
PDF-weergave.

Dit kan conceptueel met een **interne bronviewer**: een zijpaneel of modal met
de bron naast de onderzoeksgegevens. Voor gewone websites is dit minder
voorspelbaar dan voor PDF's:

- sommige websites mogen in een iframe worden getoond;
- andere websites blokkeren dit met beveiligingsheaders;
- tekstfragmenten en links moeten binnen de viewer correct blijven werken;
- bij een blokkade is een duidelijke fallback naar een extern tabblad nodig.

**Voorkeursrichting voor later ontwerp:** probeer de website eerst in een
interne viewer te openen en bied alleen wanneer de site dit blokkeert de knop
**Open in nieuw tabblad** aan. Onderzoek daarbij veiligheid, navigatiegedrag en
of de externe pagina voldoende groot en leesbaar kan worden weergegeven.

## 8. Acceptatiecriteria voor een latere verbetering

- De exacte vestigingsbron blijft behouden gedurende de volledige flow.
- Een gevonden teamoverzicht krijgt altijd een extractie- en telpoging.
- De output vermeldt wat is geteld, hoe is geteld en waarom de telling onzeker
  of onbruikbaar kan zijn.
- De bronkaart heeft één primaire conclusie en vermijdt synonieme waarschuwingen.
- Identiteit, geografisch bereik, bewijs en vervolgstap zijn afzonderlijk maar
  in gewone taal zichtbaar.
- Een JavaScript-pagina zonder leesbare hoofdinhoud krijgt een browser-rendered
  extractiepoging voordat de bron als bewijsloos wordt opgeslagen.
- Inhoudelijk gelijkwaardige pagina's van hetzelfde domein verdringen geen
  complementaire bron met concreter bewijs.
- Taalvarianten van dezelfde pagina worden als één bronroute behandeld.
- Subpagina's van één portaalprofiel worden als gebundelde bron behandeld en
  niet als losse topresultaten.
- Een gelijknamige organisatie op een andere locatie wordt niet als exacte
  vestiging geaccepteerd.
- Dynamische personeelsgrafieken worden uitgelezen en als aanvullend bewijs
  bewaard, ook wanneer ze geen absoluut WP-totaal bevatten.
- Een expliciete namenlijst wordt geteld en met namen/functies als afgeleid
  personeelsbewijs bewaard.
- Zekerheid over het aantal en zekerheid over de vestigingsscope blijven twee
  afzonderlijke beoordelingen.
- Een bron opent bij voorkeur binnen de applicatie, met een gecontroleerde
  fallback naar een nieuw tabblad.

## 9. Nog niet doen

- Geen bestaande flow terugzetten.
- Geen nieuwe rankingregels invoeren.
- Geen frontendcomponenten aanpassen.
- Geen Crawl4AI-configuratie wijzigen.
- Geen viewer implementeren voordat het gewenste gedrag en de technische
  beperkingen zijn getoetst.
