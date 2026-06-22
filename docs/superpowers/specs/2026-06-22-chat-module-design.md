---
title: Chat Module — Conversational WP-dataverzameling
date: 2026-06-22
status: approved
---

## Doel

De statische ChatForm in de KYC Review-frontend vervangen door een conversational chatbot die WP-data (en bij de volledige variant ook vastgoeddata) verzamelt via een natuurlijk gesprek. Gebaseerd op het Cloudcast chatbot-patroon: stateless, OpenAI-powered, met dynamische system prompts per variant.

## Context

Het Vestigingsregister AI Platform heeft drie fases. Fase 1 (pipeline backend) en fase 2 (review interface) zijn af. Fase 3 is de chat-module die bedrijven uitnodigt om zelf hun personeelsgegevens te controleren of aan te vullen. Er zijn twee varianten:

- **Gericht (🟡)**: confidence 0.50–0.79 — het systeem heeft al een WP-schatting, vraagt bevestiging
- **Volledig (🔴)**: confidence <0.50 — het systeem weet weinig, vraagt alles uit

De bestaande backend-infrastructuur (ChatSession, ChatTemplate, e-mail, admin endpoints) blijft intact. Alleen het publieke chat-endpoint en de frontend ChatForm worden vervangen.

## Scope

### In scope

- Nieuw endpoint `POST /chat/{token}/message` in de bestaande KYC backend
- OpenAI-integratie met dynamische system prompts
- Conversational frontend in bestaande KYC React app (vervangt ChatForm)
- Token-hashing (sha256) bij opslag
- Nieuw `messages` veld op ChatSession voor gesprekshervat
- Privacy-transparantie in openingsbericht en footer

### Buiten scope

- DPIA uitvoering (organisatorisch)
- Herinneringsmails voor niet-afgeronde sessies
- Anonimisering van verlopen sessies
- Wijzigingen aan ChatSessiesView, ChatTemplatesView, of admin endpoints

## Backend

### Nieuw endpoint: `POST /chat/{token}/message`

Toegevoegd aan `app/routers/chat.py` (publieke router, geen auth).

```
Request:  { "messages": [{"role": "user", "content": "..."}] }
Response: { "reply": "...", "done": false }
```

Bij `done: true` bevat de response ook:
```json
{"reply": "Bedankt voor...", "done": true, "antwoorden": {"wp_totaal": 250, ...}}
```

De backend:
1. Hasht het token, zoekt de ChatSession
2. Valideert dat de sessie niet verlopen of al afgerond is
3. Bouwt de system prompt op basis van variant + bekende context
4. Stuurt messages + system prompt naar OpenAI
5. Parseert de response (met fallbacks voor malformed JSON)
6. Slaat de bijgewerkte messages op in `ChatSession.messages`
7. Bij `done: true`: parseert antwoorden, schrijft naar `ChatSession.antwoorden`, zet status op `completed`

Het bestaande `POST /chat/{token}/submit` endpoint blijft intact als direct-submit optie voor het geval de conversational flow faalt (bijv. OpenAI niet beschikbaar). De frontend kan dan terugvallen op het formulier.

### System prompt opbouw

Functie: `_build_system_prompt(session, company, enrichment) -> str`

**Variant "gericht" (🟡):**
- Context: bedrijfsnaam, gemeente, pre_fill_wp
- Doel: bevestig of corrigeer de WP-waarde, vraag optionele toelichting
- ~2 beurten
- Groepering: alles in 1-2 vragen

**Variant "volledig" (🔴):**
- Context: alles wat het systeem al weet (bedrijfsnaam, gemeente, adres, enrichment data)
- Doel: verzamel alle velden in gegroepeerde beurten
- ~6-8 beurten
- Groepering:
  1. Begroeting + bevestig bekende gegevens (adres, bedrijfsnaam)
  2. WP totaal + uitsplitsing personeel (eigen/uitzend/detachering/WSW)
  3. Man/vrouw + voltijd/deeltijd + percentage op locatie (≥60% van de tijd)
  4. Oppervlaktes (perceel/winkel/kantoor/bedrijfsvloer) + uitbreidingsruimte
  5. Seizoensverschillen + opmerkingen

**Vragen volledig variant (18 velden):**
1. Adres + correspondentieadres
2. WP totaal
3. Eigen personeel
4. Uitzendkrachten
5. Detachering
6. WSW
7. Man
8. Vrouw
9. Voltijd
10. Deeltijd
11. ≥60% werkzaam op locatie
12. Perceeloppervlakte
13. Winkeloppervlakte
14. Kantooroppervlakte
15. Bedrijfsvloeroppervlakte
16. Uitbreidingsruimte
17. Seizoensverschillen
18. Opmerking

**Vragen gerichte variant (2 velden):**
1. WP totaal (met pre-fill bevestiging: "Onze gegevens tonen X werkzame personen. Klopt dit?")
2. Opmerking

**Gedragsregels in de prompt:**
- Antwoord altijd als geldig JSON: `{"reply": "...", "done": false}`
- Bevestig wat al bekend is, vraag niet opnieuw
- Groepeer gerelateerde vragen (max 3-4 per beurt)
- Spreek de gebruiker formeel maar vriendelijk aan (u)
- Beknopt, geen emojis, geen markdown
- Stel maximaal één groep vragen per beurt
- Open met transparantie: wie vraagt dit, waarvoor, dat antwoorden via een reviewer gaan
- Vraag eerst bevestiging van bedrijfsnaam/rol voordat WP-data wordt getoond

### OpenAI integratie

- Model: `gpt-4o-mini` (configureerbaar via bestaande `OPENAI_MODEL` env var)
- API key: bestaande `OPENAI_API_KEY` env var
- `max_tokens`: 600
- Response parsing: JSON parse → escape-newline fallback → regex fallback (zoals Cloudcast)

### Antwoord-extractie

Bij de laatste beurt instrueert de system prompt de bot om een `antwoorden` object mee te geven:

```json
{
  "reply": "Bedankt voor uw medewerking...",
  "done": true,
  "antwoorden": {
    "wp_totaal": 250,
    "eigen_personeel": 200,
    "uitzend": 30,
    "detachering": 15,
    "wsw": 5,
    "man": 140,
    "vrouw": 110,
    "voltijd": 180,
    "deeltijd": 70,
    "pct_op_locatie": 85,
    "perceeloppervlakte": null,
    "winkeloppervlakte": null,
    "kantooroppervlakte": 2500,
    "bedrijfsvloeroppervlakte": null,
    "uitbreidingsruimte": "nee",
    "seizoensverschil": "geen",
    "opmerking": "Inclusief 10 stagiairs"
  }
}
```

## Frontend

### ChatForm vervanging

De bestaande `ChatForm` component in `frontend/src/App.jsx` wordt vervangen door een conversational chat-interface. Dezelfde route: `?chat={token}`.

### UI-structuur

```
┌──────────────────────────────────────┐
│  Header bar (bg-etil, teal)          │
│  "Vestigingsregister AI"             │
│  "Etil Research Group — Prov. Limb." │
├──────────────────────────────────────┤
│                                      │
│  [bot avatar] Bot bericht            │
│                                      │
│            User bericht [user avatar]│
│                                      │
│  [bot avatar] Volgend bericht        │
│                                      │
│  ● ● ● (typing indicator)           │
│                                      │
├──────────────────────────────────────┤
│  [Typ uw antwoord...        ] [Send] │
├──────────────────────────────────────┤
│  Privacy footer                      │
└──────────────────────────────────────┘
```

### Styling

Volledig conform de bestaande KYC stijl (Tailwind classes):
- Header: `bg-etil text-white`
- Bot bubbels: `bg-panel border border-line`, links uitgelijnd
- User bubbels: `bg-etil text-white`, rechts uitgelijnd
- Typing indicator: drie pulsende dots in etil-kleur
- Input area: `focus-ring border-line rounded-md`
- Privacy footer: `text-xs text-slate-400`

### States

1. **Loading**: sessie ophalen via `GET /chat/{token}` — toon "Laden..."
2. **Active**: chat actief — berichten uitwisselen
3. **Completed**: `done: true` — bedankscherm met groen vinkje (hergebruikt bestaand design)
4. **Error**: sessie niet gevonden of verlopen — foutscherm (hergebruikt bestaand design)

### Berichtenstroom

1. Component mount → `GET /chat/{token}` → sessie-info ontvangen
2. Als `session.messages` bestaan → laad eerder gesprek (hervatting)
3. Auto-trigger eerste bot-bericht → `POST /chat/{token}/message` met `messages: []`
4. User typt → Enter of klik send
5. Append user bubble → `POST /chat/{token}/message` met volledige messages array
6. Toon typing indicator → ontvang reply → append bot bubble
7. Herhaal 4-6 tot `done: true`
8. Toon bedankscherm

## Token-hashing

### Huidige situatie

Token wordt als plain text opgeslagen in `ChatSession.token_hash`.

### Nieuwe situatie

- **Aanmaken**: `token = secrets.token_urlsafe(32)`, sla `sha256(token)` op in `token_hash`
- **E-mail/link**: plaintext token in de URL (`?chat={token}`)
- **Lookup**: bij elk request: `token_hash = sha256(binnenkomend_token)`, zoek op hash
- **Impact**: wijziging in het aanmaak-endpoint (chat_admin.py / review.py) en in alle `GET/POST /chat/{token}` handlers

De `token_hash` kolom en het schema blijven ongewijzigd.

## Follow-up: gesprekshervat

### Nieuw veld

`ChatSession.messages: JSON` — slaat de volledige berichtgeschiedenis op.

Bij elke beurt wordt dit bijgewerkt, zodat:
- Een onderbroken gesprek hervat kan worden bij heropenen van de link
- De admin in `ChatSessiesView` het volledige gesprek kan inzien

### Expiry

`ChatSession.expires_at` (bestaand veld) wordt gezet op 14 dagen na aanmaak. Het endpoint checkt dit bij elk request en retourneert 410 Gone als verlopen.

### Status flow

```
created → sent (na e-mail) → opened (bij eerste GET) → completed (bij done: true)
                                                      → expired (na 14 dagen)
```

## Privacy / AVG

### In de code

1. **Transparant openingsbericht**: de bot opent met wie het vraagt (Etil Research Group, in opdracht van Provincie Limburg), waarvoor (Vestigingsregister), en dat antwoorden door een medewerker worden gecontroleerd
2. **Geen gevoelige pre-fill in opening**: de bot vraagt eerst bevestiging van bedrijfsnaam en rol van de invuller, pas daarna toont hij bekende WP-data
3. **Privacy footer**: "Uw gegevens worden uitsluitend gebruikt voor het Vestigingsregister van Provincie Limburg."
4. **Expiry**: links verlopen na 14 dagen, tokens zijn single-use (na `completed` niet meer bruikbaar)

### Buiten de code (organisatorisch)

- DPIA uitvoering vereist voor pilot (platformdocumentatie §12, open vraag #5)
- Bewaartermijnen formeel vastleggen
- Opt-in/consent afstemmen met Roger

## Technische details

### Bestanden die wijzigen (KYC project)

| Bestand | Wijziging |
|---|---|
| `backend/app/routers/chat.py` | Nieuw `/chat/{token}/message` endpoint + OpenAI integratie |
| `backend/app/models.py` | `messages: JSON` veld op ChatSession |
| `backend/app/routers/chat_admin.py` | Token-hashing bij aanmaak |
| `backend/app/config.py` | Eventueel: `CHAT_MODEL` setting (of hergebruik `OPENAI_MODEL`) |
| `frontend/src/App.jsx` | ChatForm component vervangen door conversational chat |

### Bestanden die NIET wijzigen

- `backend/app/routers/review.py`
- `backend/app/routers/batches.py`
- `backend/app/email.py` (template tekst eventueel bijwerken, maar structuur ongewijzigd)
- `frontend/src/api.js` (bestaande chat API calls blijven, nieuwe `sendChatMessage` toevoegen)

### Dependencies

- `openai` Python package (al aanwezig in KYC backend)
- Geen nieuwe frontend dependencies

### Model en kosten

- Model: `gpt-4o-mini`
- Geschatte tokens per sessie: ~2.000 (gericht) tot ~8.000 (volledig)
- Kosten per sessie: <$0.01
- Bij 10.000 sessies/jaar: ~$50-80
