# Implementatieplan — ibc-huisstijl in de frontend

Status: **uitgevoerd op 2026-09-07**, op branch `frontend/huisstijl-etil`. Geschreven
2026-09-07. De beschrijving hieronder klopt nog, met vier afwijkingen die in
"Wat er anders liep dan gepland" staan — lees die eerst.

Mockups: <https://claude.ai/code/artifact/3425ab14-e827-44c4-9601-8db51ae4235b>

## Beslissingen

| Vraag | Besluit |
| --- | --- |
| Naam | **Bronnenwerkbank** — inlogscherm en `<title>` |
| Primaire actie | **Night**, niet het Data-verloop. Rood blijft afwijzen |
| Merk | **Etil**, niet ibc — zie hieronder |
| Limburg-logo | nog open |
| `ChatForm.jsx` | nog open; overgeslagen bij de restyling |

## Wat er anders liep dan gepland

1. **Etil in plaats van ibc.** `ETIL LOGO 2026` is in het ibc-systeem gebouwd —
   zelfde opbouw, met het Data-verloop rood→geel als streepje in plaats van het
   volledige spectrum. Er is dus geen keuze tussen twee systemen; Etil is de naam
   binnen dat ene systeem. Het oude rode blok (`logo-etil.png`, `#E10613`) is
   daarmee vervallen.
2. **De hero is niet geleend.** `ETIL HEADER 2026.jpg` is dezelfde afbeelding als
   op het SIP-inlogscherm, maar van Etil zelf en op 2560×1440. Het voorbehoud
   onder "Buiten scope" vervalt.
3. **De hairline volgt het Data-verloop**, niet het zevenkleurenspectrum:
   hetzelfde streepje als in het logo. Twee verschillende balkjes boven elkaar
   leest als twee huisstijlen.
4. **De logobestanden moesten gerepareerd.** `ETIL LOGO 2026.jpg` is een JPG
   waarin het witte woordmerk (`#F6F7F8`) plat op een witte ondergrond
   (`#F5F5F5`) staat: onzichtbaar in zijn eigen bestand én zonder transparantie.
   De vier PNG's in `frontend/public/` zijn daaruit gereconstrueerd — de
   scheiding was schoon bimodaal (`b−r` exact 0 tegen exact 2), dus dat kon,
   maar **vraag de huisstijlbeheerder om een SVG of PNG's met transparantie**,
   in Seasalt en in Night, plus een officiële korte variant zonder tagline.
   `etil-merk-*.png` is door mij bijgesneden omdat de tagline op 72 px
   onleesbaar wordt.

Bron: `~/Downloads/ibc group - Brand Guideline 2026-04.pdf` (77 pagina's, versie 1.0, april 2026).
Referentie-inlogscherm: <https://sip-poc-production.up.railway.app/> (Railway-project `sip-poc`).

## Waarom dit kan

Etil Research Group (Sittard) staat in de gids zelf genoemd als onderdeel van de ibc group,
en wel als het **Data**-onderdeel (p29: Data Strategy & Execution, AI & Machine Learning,
Business Intelligence & Dashboarding). De huisstijl is dus van toepassing, en van de vier
kleurwerelden is Data de onze.

Dat is meer dan een formaliteit. Het inlogscherm van SIP POC dat we mooi vinden, gebruikt een
warm verloop van rood naar geel. Dat leek een eigen keuze van dat project, maar het is de
**Data-kleurwereld uit de gids** (p50: `#ff3333` en `#ffff33`). Technology is violet/blauw
(p52), ter vergelijking. We nemen dus geen vreemde stijl over — we nemen onze eigen
kleurwereld over, die daar al goed is toegepast.

## De kleuren en het lettertype

Basispalet (p32) — hiermee bouw je alles, de rest is accent:

| Naam | Hex | Rol volgens de gids |
| --- | --- | --- |
| Night | `#121212` | titelvlakken, containers, donkere achtergrond |
| Seasalt | `#F8F9FA` | tekstrijke schermen, schone interfaces |

Night op 85 / 65 / 50 / 25 % dekking is de grijstrap (p32). Gebruik die in plaats van
Tailwinds `slate-*`, anders lopen er twee grijzen door elkaar.

Het ibc-spectrum (p33), sparzaam en met hoog contrast te gebruiken:

`#330099` violet · `#000099` deep blue · `#0066cc` true blue · `#009966` shamrock green ·
`#ff3333` vermillion red · `#ff6600` pumpkin orange · `#ffff33` bright yellow

Twee dingen om te weten voordat het je opvalt en je denkt dat je iets fout leest:
de gids noemt `#330099` in de kop "Duke Blue" en in de lopende tekst "Violet"; en de
gedrukte swatch op p33 is feitelijk `#4100aa`, niet `#330099`. Houd `#330099` aan, dat is
de gespecificeerde waarde.

Lettertype (p41): **Ubuntu**, gratis via Google Fonts, met Arial als systeemfallback.
Gewichten (p42/p43): Bold voor koppen, Light voor sublines, Regular voor lopende tekst,
Medium voor accenten. Nu staat er Inter in `tailwind.config.js`.

Toon (p45): kort, zonder jargon, "every word serves a purpose". Dat sluit aan op wat we in
deze frontend al aanhouden — geen herhalende bijzin, geen systeemtaal.

## De ene echte keuze: waar het warm mag zijn

Het rood-gele Data-verloop is prachtig op een inlogscherm en verkeerd in het werkscherm.
Rood betekent in deze applicatie al iets: afwijzen. Een primaire actieknop in rood-geel
naast een afwijsknop in rood is een ongeluk dat op je wacht.

Daarom:

- **Inlogscherm donker.** Night als basis, hero-afbeelding, het Data-verloop op de
  inlogknop. Dit is het "title section"-gebruik dat de gids voor Night beschrijft.
- **Werkscherm licht.** Seasalt als achtergrond, Night als tekst, en de primaire actieknop
  in **Night** — niet in een spectrumkleur. Het spectrum komt terug als dunne accentlijn
  (de gids noemt dat expliciet als toepassing, p34) en in statuskleuren.
- **Rood blijft gereserveerd** voor afwijzen en gevaar. Niet voor merkexpressie in het
  werkscherm.

Als je dit anders wilt, is dit de plek om het te veranderen — de rest van het plan volgt
hieruit.

## Wat er nu staat

Gemeten in `frontend/src` (3396 regels JSX):

- Tokens in `tailwind.config.js`: `ink` #1f2933 (84×), `line` #d7dde5 (93×), `panel` #f7f8fa (34×), `etil` #1e3a5f (35×), `signal` #b45309 (**0×, dood token**).
- 214 losse `slate-/gray-/blue-/amber-…`-utilities die *niet* meebewegen als je alleen de tokens verandert. Dit is het echte werk.
- Hardcoded hexes: `#eef2f5` (6×, in `index.css`, `Login.jsx`, `ChatForm.jsx`), `#1f2933` (1×), en `#C8102E` — het Etil-rood in `Login.jsx` en `AppShell.jsx`.
- Grootste bestanden: `KandidatenPaneel.jsx` (598), `InstellingenView.jsx` (335), `MonitoringView.jsx` (292), `BronKaart.jsx` (270), `MappenView.jsx` (266).

## Fase 1 — fundament en inlogscherm

Dit is de fase met het meeste zichtbare effect en het minste risico. Als je maar één fase
doet, doe deze.

1. **Ubuntu laden.** In `frontend/index.html` een `<link>` naar Google Fonts (Ubuntu 300/400/500/700).
   In `tailwind.config.js` `fontFamily.sans` op `["Ubuntu", "Arial", "sans-serif"]`.
   Zet meteen `<html lang="nl">` goed — dat staat al goed, alleen de `<title>` is nu
   "Vestigingsregister Review" en mag mee met de naamgeving die je aanhoudt.

2. **Tokens vervangen** in `tailwind.config.js`. Voorstel, met de bestaande namen intact
   zodat de 246 bestaande token-verwijzingen blijven werken:

   ```js
   colors: {
     night: "#121212",
     seasalt: "#F8F9FA",
     ink: "#121212",        // was #1f2933
     line: "#e3e5e7",       // Night 12%
     panel: "#F8F9FA",      // was #f7f8fa
     etil: "#121212",       // primaire actie wordt Night
     spectrum: {
       violet: "#330099", deepblue: "#000099", trueblue: "#0066cc",
       green: "#009966", red: "#ff3333", orange: "#ff6600", yellow: "#ffff33",
     },
   },
   ```

   Gooi `signal` weg, dat wordt nergens gebruikt.

3. **`index.css`**: `body` achtergrond `#eef2f5` → `#F8F9FA`, kleur `#1f2933` → `#121212`.
   De `focus-ring` gebruikt `ring-etil` en volgt dus vanzelf.

4. **Assets neerzetten** in `frontend/public/`. Ze staan al gedownload klaar in de
   scratchpad van de vorige sessie, maar opnieuw ophalen is één regel:

   ```bash
   curl -o frontend/public/login-hero.jpg https://sip-poc-production.up.railway.app/login-hero.jpg
   curl -o frontend/public/ibc-group-lockup.png https://sip-poc-production.up.railway.app/ibc-group-lockup.png
   ```

   De hero is een donkere ruimte met een gloeiende doorgang in rood/oranje/geel, abstract en
   zonder tekst of merk — herbruikbaar zoals hij is, en het is de Data-kleurwereld.

5. **`Login.jsx` herschrijven** naar de SIP-opzet, maar met onze tokens, onze taal en het
   bestaande gedrag. Wat je overneemt van SIP:

   - fullscreen hero met `background: #121212 url(/login-hero.jpg) center/cover`;
   - een `::before`-overlay met radiaal verloop van 35 % naar 92 % Night, zodat de tekst
     leesbaar blijft ongeacht de foto;
   - een glaspaneel: `max-width: 400px`, `rgba(18,18,18,.55)`, `backdrop-blur(18px) saturate(140%)`,
     1 px rand `rgba(248,249,250,.14)`, radius 16, `box-shadow 0 24px 60px rgba(0,0,0,.45)`;
   - invoervelden 46 px hoog op `rgba(255,255,255,.06)` met rand `rgba(248,249,250,.2)`;
   - knop 48 px met verloop, hier `linear-gradient(90deg, #ff3333, #ffff33)` en Night als
     tekstkleur;
   - de `powered by`-regel onderaan met het ibc-lockup.

   Wat je **niet** overneemt: SIP's eigen verloop `#ff4d2e → #ffb020`, de Engelse teksten,
   en het losse `fetch`-script — wij houden `api.login` en de bestaande `onLogin`-flow.

   Wat behouden moet blijven, want het zit er niet voor niets:
   - de `melding`-prop met de uitleg waarom je opnieuw moet inloggen (anders vlieg je er na
     twaalf uur uit zonder uitleg en lijkt het stuk);
   - `autoComplete="username"` / `"current-password"`;
   - de `error`-weergave, met `role="alert"`;
   - `busy`-toestand op de knop.

   Contrast controleren: Seasalt-tekst op het glaspaneel haalt ruim AA; de gele kant van het
   knopverloop met Night-tekst ook. De grens zit bij `rgba(248,241,238,.45)` voor de
   `powered by`-regel — die haalt op een donkere ondergrond net AA voor kleine tekst, dus
   niet verder verzwakken.

6. **`AppShell.jsx`**: het `#C8102E` Etil-rood eruit, het lockup erin, en het ibc-spectrum
   als 2 px hairline onder de header (`linear-gradient(90deg, #330099, #000099, #0066cc,
   #009966, #ff3333, #ff6600, #ffff33)`). Dat is precies het gebruik dat p34 beschrijft en
   het is de goedkoopste manier om het merk in het werkscherm te laten zien zonder de
   interface te laten schreeuwen.

## Fase 2 — gedeelde componenten

`IconButton.jsx` is de sleutel: vijf varianten, en bijna elke knop in de applicatie gaat
erdoorheen. Pas die eerst aan, dan volgt veel vanzelf.

- `primary`: Night, witte tekst.
- `danger`: `#ff3333` (spectrum red) in plaats van `red-600` — dat is nu een Tailwind-rood dat naast het merkrood staat.
- `default` / `quiet` / `ghost`: op de Night-grijstrap in plaats van `slate-*`.

Daarna `Dialog.jsx`, `Alert.jsx`, `ActieMenu.jsx` — samen 177 regels, allemaal klein.

## Fase 3 — de views

De 214 losse `slate-*`/`gray-*`-utilities, per bestand. Dit is monnikenwerk zonder
denkwerk; doe het bestand voor bestand en draai na elk bestand de rookproef, niet aan het
eind. Volgorde op zichtbaarheid: `OnderzoekView` → `KandidatenPaneel` → `BronKaart` →
`MonitoringView` → `MappenView` → `BatchesView` → `InstellingenView`.

`ChatForm.jsx` (243 regels, 4× `#eef2f5`) hoort bij de gearchiveerde chatstroom en is geen
actieve module. Overslaan, of expliciet aan Arrya vragen of het weg kan.

Statuskleuren 🟢/🟠/🔴 in `onderzoekLabels.js` niet zomaar op het spectrum gooien — die
betekenen iets in het domein. Als je ze aanraakt, alleen om ze op `#009966` / `#ff6600` /
`#ff3333` te zetten, met dezelfde betekenis.

## Controleren

Groene tests zeggen niets over of het er goed uitziet, en de mappenlaag ging live met 463
groene backendtests terwijl niemand erop had geklikt. Dus, in deze volgorde:

```bash
cd frontend && npm test -- --run
cd backend && python -m scripts.ui_check      # verplicht bij elke frontendwijziging
```

De rookproef logt in met een echte browser en laat screenshots achter in
`backend/scripts/ui_check_output/`. **Bekijk die zelf** — een geslaagde assertie betekent
alleen dat de knop bestond. Het inlogscherm is juist het scherm waar de rookproef als
eerste doorheen gaat, dus dat zie je meteen.

Lokaal draaien vereist een `FRONTEND_ORIGIN`-override; "Failed to fetch" is dan CORS en
niet het wachtwoord. Wachtwoord via
`railway variables -s backend --kv | grep DEMO_ADMIN_PASSWORD`, nooit in de repository.

Verder met het oog: donker/licht wisselen, 320 px breed, en tabben door het inlogformulier
om te zien of de focusring op het glaspaneel zichtbaar blijft.

## Buiten scope

- Geen wijzigingen aan de backend, de API of het datamodel.
- Geen nieuwe afhankelijkheden behalve het Google-Fonts-`<link>`. Als je Ubuntu liever
  self-host vanwege de Azure-verhuizing, is dat een bewuste extra stap — zeg het, doe het
  niet stilletjes.
- De hero-afbeelding komt van het SIP-project. Hij is abstract en merkloos, maar het blijft
  een geleende asset; op termijn een eigen variant met het volledige spectrum in plaats van
  alleen het warme deel.

## Openstaand voor Arrya

- Moet het Limburg-logo (`public/logo-limburg.png`) op het inlogscherm terugkomen, naast of
  onder het Etil-logo?
- Mag `ChatForm.jsx` weg? Zolang dat niet beslist is, staan die zeven bestanden nog
  op de oude Tailwind-kleuren. Niets importeert `ChatForm.jsx`, dus het is dode code.
- Officiële logobestanden opvragen (punt 4 hierboven).
- `public/logo-etil.png` (het oude rode blok) kan weg zodra bovenstaande rond is.
