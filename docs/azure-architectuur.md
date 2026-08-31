# KYC4etil op Azure — voorgestelde architectuur

*31 augustus 2026*

De werkbank draait nu op Railway. Productiesystemen moeten op termijn naar
Azure. Dit stuk beschrijft hoe dat eruitziet, wat er al klaar voor is en waar
het werk zit.

Uitgangspunt: er staat niets Railway-specifieks in de code. Het is een gewone
FastAPI-service, een PostgreSQL-database en een map statische bestanden. De
verhuizing is bouw- en configuratiewerk, geen herschrijving.

Wel duurder: ongeveer $29 per maand tegen ongeveer $5 nu. Railway rekent naar
verbruik en onze werkbank staat het grootste deel van de dag stil; Azure rekent
naar gereserveerde capaciteit. Kosten zijn dus geen argument om te verhuizen —
zie [de vergelijking verderop](#wat-het-kost-en-waarom-het-meer-is-dan-nu).

## Het plaatje

```mermaid
flowchart TB
    reviewer["Reviewer<br/>(browser)"]

    subgraph azure["Azure — regio West Europe"]
        swa["Static Web Apps<br/><i>frontend (dist/)</i>"]
        app["App Service B1<br/><i>FastAPI + Playwright</i><br/>1 instantie, altijd aan"]
        pg[("PostgreSQL<br/>Flexible Server")]
        files[["/home<br/><i>brondocumenten + back-ups</i><br/>inbegrepen in het plan"]]
        kv["Key Vault<br/><i>sleutels</i>"]
        foundry["AI Foundry<br/><i>modeldeployment</i>"]
    end

    subgraph extern["Buiten Azure"]
        serper["Serper<br/><i>zoeken</i>"]
        places["Google Places<br/><i>locatietelling</i>"]
        duo["DUO / DigiMV<br/><i>open data</i>"]
        resend["Resend<br/><i>e-mail</i>"]
    end

    reviewer --> swa
    reviewer -->|"API-calls"| app
    app --> pg
    app --> files
    app --> kv
    app --> foundry
    app --> serper
    app --> places
    app --> duo
    app --> resend
```

## Component voor component

| Nu (Railway) | Azure | Waarom deze |
|---|---|---|
| backend-service | **App Service B1 (Linux, container)** | Goedkoopste vorm die altijd aan staat én een eigen image draait, zodat Chromium mee kan. Container Apps kan ook, maar kost bij een altijd-aan replica het dubbele tot het viervoudige. |
| frontend-service (`serve dist`) | **Static Web Apps** | Het is een gebouwde Vite-map. Een container ervoor is verspilling. |
| Railway PostgreSQL | **Azure Database for PostgreSQL — Flexible Server** | Zelfde Postgres, `DATABASE_URL` wijst er gewoon heen. |
| volume op `/data/brondocumenten` (90 MB / 5 GB) | **`/home`**, het meegeleverde schijfruimte van het App Service-plan | `documenten.py` en `backup.py` werken met een gewoon bestandspad; twee variabelen wijzen het om. B1 bevat 10 GB, ruim genoeg. Vereist `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true`, anders is de schijf bij elke herstart leeg. |
| omgevingsvariabelen met sleutels erin | **Key Vault** + App Service-instellingen | Nu staan `OPENAI_API_KEY`, `SERPER_API_KEY` en `JWT_SECRET` als platte variabelen ingesteld. |
| OpenAI rechtstreeks | **AI Foundry-deployment** | Eén variabele om: `AZURE_OPENAI_ENDPOINT`. |

Regio **West Europe** (Amsterdam) — relevant als de vraag opkomt waar de
gegevens staan. Let op: modelbeschikbaarheid verschilt per regio, zie hieronder.

## Wat al klaar is

- **De modelprovider is omschakelbaar.** Alle modelaanroepen lopen door
  `maak_client()` in `backend/app/providers/llm.py`. Leeg endpoint = OpenAI,
  gevuld endpoint = Azure. Eén variabele, geen codewijziging. Dat is vorige
  week zo gebouwd, precies met het oog hierop.
- **Providers zitten achter Protocol-interfaces** (`app/providers/base.py`).
  Een dienst vervangen is één implementatie, niet een pipeline.
- **De code kent geen Railway.** Nul platformafhankelijkheden in `backend/app`.
- **De monitoring loopt via een knop**, niet via een cron buiten de app.

## Waar het werk zit

### 1. Een Dockerfile met Chromium — het grootste deel

`crawl4ai` en Playwright hebben een echte browser nodig. Railway lost dat nu
op met twee instellingen die je in geen enkele repository terugvindt:

- `RAILPACK_DEPLOY_APT_PACKAGES` met twintig X11- en font-bibliotheken
- `crawl4ai-setup` in de buildstap (`backend/railway.toml`)

Op Azure moet dat in een Dockerfile, die er nu niet is. De pakketlijst hebben
we — die staat in de Railway-variabelen en kan er rechtstreeks in. Reken op een
image van rond de 2 GB. B1 heeft 1,75 GB werkgeheugen; dat is genoeg voor de
146 MB die de service nu gebruikt plus Chromium tijdens een run, maar het is
niet ruim. Blijkt het te krap, dan is B2 de volgende stap (± $26).

### 2. Foundry is niet één-op-één OpenAI

Twee dingen om te controleren vóór de overstap, niet erna:

- **`model` is op Azure de deploymentnaam**, niet de modelnaam. `OPENAI_MODEL`
  staat nu op `gpt-5.6-luna`; op Azure wordt dat de naam die jij aan je
  deployment geeft.
- **Draait dat model daar?** Zo niet, dan wissel je van model — en dan moeten
  de prompts en `scripts.validate` opnieuw langs, inclusief de
  temperature-eigenaardigheid die luna heeft (`llm.py` vangt die nu af). Dat is
  een testronde, geen instelling.

### 3. Eén instantie, niet nul en niet twee

De onderzoeksrun draait in het proces zelf, en de nachtelijke back-up hangt aan
een planner in datzelfde proces. Dus:

- **niet naar nul schalen** — een instantie die tussendoor afschakelt, breekt
  een lopende run af. Daarom valt de goedkope schaal-naar-nul-optie af, en
  daarmee de goedkoopste Azure-vorm;
- **niet meer dan één instantie** — twee processen betekent twee back-ups per
  nacht en twee monitoringrondes. Zet `Always On` aan en het aantal instanties
  op één.

Wil je later wél meerdere instanties, dan moet de planner eruit en wordt het
een aparte geplande taak. Nu niet nodig.

### 4. Losse eindjes

- `FRONTEND_ORIGIN` (CORS) en `VITE_API_URL` (buildtijd) wijzen naar de
  Railway-URL's en moeten mee.
- De `DEMO_*_PASSWORD`-variabelen kunnen weg. Accounts worden sinds vorige week
  in de applicatie zelf beheerd; die variabelen zijn een restant van
  `seed_users.py`.
- `requirements.txt` pint geen versies. Bij Railway merk je dat pas als een
  build breekt; in een image wil je weten wat erin zit. Dit hoort vóór de
  verhuizing te gebeuren, niet erna.

## Zoeken blijft buiten Azure

Er is geen Azure-alternatief voor Serper dat bij ons past.

Microsoft heeft alle Bing Search-API's op 11 augustus 2025 uitgezet. De
opvolger, *Grounding with Bing Search* in AI Foundry, is geen hernoemd
endpoint: de oude API gaf een lijst zoekresultaten, grounding geeft een agent
webcontext en laat het model een antwoord formuleren.

Dat is voor ons de verkeerde kant op. `_serper_search` levert nu een kale lijst
URL's met titel en snippet, waarna onze eigen pipeline valideert, rankt en
scoort. Het uitgangspunt is dat de LLM een score alleen mag begrenzen, nooit
bepalen. Bij grounding doet het model de selectie en houden wij de uitkomst
over. Daar komt bij:

- **Prijs**: Microsoft noemt $14 per 1.000 transacties (oudere bronnen $35), en
  één vraag kan meerdere transacties kosten. Wij rekenen Serper op $1 per 1.000.
- **Toonplicht**: de Use and Display Requirements schrijven voor dat je de
  Bing-citaties én de link naar de Bing-zoekopdracht aan de eindgebruiker laat
  zien.

Serper laten staan is dus het voorstel. Hosting op Azure betekent niet dat elke
afhankelijkheid van Microsoft moet zijn: het is een HTTPS-call, die werkt vanaf
Azure net zo goed als vanaf Railway. Wat er naartoe gaat is een
zoekopdracht met een organisatienaam erin — geen persoonsgegevens, geen
documenten.

Moet Serper er tóch uit, dan zijn Brave Search API of Google Custom Search de
realistische vervangers, en dat is één functie in
`backend/app/providers/search.py`.

*Azure AI Search is iets anders, mocht die naam vallen: dat doorzoekt je eigen
documenten, niet het web.*

## Wat het kost, en waarom het meer is dan nu

Eerst de eerlijke vergelijking, want die valt niet in Azure's voordeel.

**Railway rekent naar verbruik.** Vandaag gemeten: de backend gebruikt 146 MB
geheugen en vrijwel geen rekenkracht, de frontend 31 MB, de database 68 MB.
Samen 245 MB en nul vCPU zolang niemand een onderzoek start. Bij Railway's
tarieven is dat een paar dollar per maand; met het volume erbij zit je rond de
$5.

**Azure rekent naar gereserveerde capaciteit.** Een instantie die altijd aan
staat kost hetzelfde of hij nu werkt of stilstaat. Dat is het hele verschil.
Niet dat Azure duur is, maar dat wij een applicatie hebben die 99% van de tijd
niets doet — en dat is precies het geval waarin verbruiksfacturering wint.

Met de goedkoopste vorm die nog aan alle eisen voldoet:

| Onderdeel | Configuratie | Per maand |
|---|---|---|
| App Service | B1 Linux, container, altijd aan | ± $13 |
| PostgreSQL Flexible Server | B1ms + 32 GB opslag | ± $16 |
| Static Web Apps | Free | $0 |
| Documentopslag | `/home`, 10 GB inbegrepen bij B1 | $0 |
| Key Vault | enkele duizenden bewerkingen | < $1 |
| AI Foundry | per token, zoals nu | gelijk |

Samen **ongeveer $29 per maand**, tegen ongeveer $5 nu. Zo'n €22 per maand
meer, of €270 per jaar.

Kies je Container Apps in plaats van App Service, dan wordt het $40–$70; die
dienst rekent bij een altijd-aan replica het dubbele tot het viervoudige. Dat
was mijn eerste inschatting en die was te ruim.

Drie dingen die het verder omlaag brengen:

- **Een reservering van één jaar** scheelt ongeveer een derde op App Service en
  Postgres.
- **Bestaande afspraken.** Heeft Etil een Enterprise Agreement of ergens
  Azure-tegoed staan, dan verandert het hele plaatje. Dat is een vraag aan
  inkoop, geen technische.
- **Het eerste jaar** is PostgreSQL Flexible Server B1ms gratis voor nieuwe
  abonnementen.

Deze bedragen zijn richtwaarden uit publieke prijspagina's. Laat ze door de
Azure-prijscalculator lopen voordat je ze doorgeeft.

### Dus: is dit een reden om te verhuizen?

Nee. Op kosten wint Railway, en dat blijft zo zolang de werkbank het grootste
deel van de dag stilstaat. De reden om naar Azure te gaan is dat productie daar
volgens afspraak hoort — beheer, inkoop, en de vraag waar de gegevens staan.
Als niemand dat eist, is er geen technische reden om nu iets te doen.

Wat wél verstandig is, ongeacht de keuze: de Dockerfile bouwen. Die maakt de
werkbank draagbaar en haalt tegelijk het enige echte risico uit de verhuizing.
Daarna kun je op elk moment overstappen zonder dat het een project wordt.

## Volgorde van uitvoeren

1. Versies pinnen in `requirements.txt`.
2. Dockerfile schrijven en **lokaal** draaien tot `scripts.ui_check` erdoorheen
   komt. Chromium is hier het risico; dat wil je niet in de cloud ontdekken.
3. Foundry-deployment aanmaken, `AZURE_OPENAI_ENDPOINT` zetten en
   `scripts.validate` draaien. Streefwaarden: coverage ≥70%, MAPE ≤10%,
   kalibratie ≥80%. Blijft dat staan, dan klopt het model.
4. Postgres opzetten, back-up van Railway terugzetten met
   `scripts/herstel_backup.py` in de lege database.
5. App Service en Key Vault inrichten; `/home` als documentmap zetten.
6. Frontend naar Static Web Apps, `VITE_API_URL` en `FRONTEND_ORIGIN` omzetten.
7. Railway laten draaien tot Azure aantoonbaar werkt, dan pas afschakelen.

Stap 2 en 3 zijn de enige met echte onzekerheid. De rest is inrichten.

## Open vragen

- Draait `gpt-5.6-luna` in West Europe, of moeten we naar een andere regio of
  een ander model?
- Wie beheert de Azure-tenant en het abonnement — Etil zelf of via VVL?
- Blijft Serper staan, of is er een inkoopreden om ervan af te willen? Dat is
  een ander gesprek dan een technisch alternatief.
