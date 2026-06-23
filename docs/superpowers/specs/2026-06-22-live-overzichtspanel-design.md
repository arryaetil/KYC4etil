# Live Overzichtspanel voor Chat — Design Spec

## Doel

Een live-bijwerkend overzichtspanel naast de chat zodat gebruikers (bedrijven) tijdens het gesprek direct zien welke gegevens al zijn verzameld. Maakt het eindoverzicht in de chattekst grotendeels overbodig en geeft visuele voortgangsfeedback.

## Scope

- Frontend: nieuw overzichtspanel in `ChatForm` component (`App.jsx`)
- Backend: system prompt aanpassing + response-parsing uitbreiding (`chat_service.py`, `chat.py`)
- Overzicht-formatting: komma als scheidingsteken ipv vetgedrukte punt

Buiten scope: admin-dashboard wijzigingen, nieuwe chat-varianten, SSE/websockets.

## Layout

Twee-kolom layout: overzichtspanel links, chatvenster rechts.

```
┌─────────────────────────────────────────┐
│  Vestigingsregister AI                  │
├─────────────────┬───────────────────────┤
│ Voortgang: 66%  │                       │
│ ████████░░░░░░  │  Chat-berichten       │
│                 │  ...                  │
│ ▸ Personeel     │  ...                  │
│   ✓ WP    25    │  ...                  │
│   ✓ Eigen 20    │                       │
│   ○ WSW   —     │                       │
│                 ├───────────────────────┤
│ ▸ Vastgoed      │ [Typ uw antwoord...]  │
│   ✓ Adres ...   │                       │
│                 │                       │
│ ▸ Overig        │                       │
│   ○ Seizoen —   │                       │
└─────────────────┴───────────────────────┘
```

Op mobiel (<768px): overzicht stackt boven de chat als inklapbaar panel.

## Datafeed

### System prompt aanpassing

De OpenAI system prompt wordt uitgebreid zodat de assistent bij **elke beurt** een `gegevens` JSON-object meestuurt met alle tot dan toe verzamelde waarden. Velden die nog niet zijn besproken blijven `null`.

### Responseformaat

Elke assistant-response bevat drie velden:

```json
{
  "reply": "Dank u. Hoeveel uitzendkrachten werken er?",
  "done": false,
  "gegevens": {
    "wp_totaal": 25,
    "eigen_personeel": 20,
    "uitzend": null,
    "detachering": null,
    "wsw": null,
    "man": null,
    "vrouw": null,
    "voltijd": null,
    "deeltijd": null,
    "pct_op_locatie": null,
    "adres": "Hoofdstraat 1, Maastricht",
    "correspondentieadres": null,
    "perceeloppervlakte": null,
    "winkeloppervlakte": null,
    "kantooroppervlakte": null,
    "bedrijfsvloeroppervlakte": null,
    "uitbreidingsruimte": null,
    "seizoensverschil": null,
    "opmerking": null
  }
}
```

Bij de laatste beurt (`done: true`) stuurt het LLM zowel `gegevens` (voor de sidebar) als `antwoorden` (voor de database-opslag, bestaand contract). Het backend kopieert `gegevens` naar `antwoorden` als het LLM alleen `gegevens` meestuurt, zodat het bestaande opslagcontract intact blijft.

### Backend wijzigingen

1. **`chat_service.py`** — `_FORMAT_RULES` en `_build_system_prompt()`:
   - Voeg instructie toe: "Stuur bij ELKE beurt een `gegevens` object mee met alle tot nu toe bekende waarden."
   - Wijzig scheidingsteken-instructie: komma ipv vetgedrukte punt.
   - Bevestigingsstap: verwijzing naar sidebar ipv volledig overzicht in tekst.

2. **`chat_service.py`** — `_parse_response()`:
   - Parse ook het `gegevens` veld uit de response.

3. **`chat_service.py`** — `get_chat_reply()`:
   - Geef `gegevens` door in het return-dict.

4. **`routers/chat.py`** — `chat_message()`:
   - Stuur `gegevens` mee in de response naar de frontend.

## Overzichtspanel structuur

### Voortgangsbalk

Bovenaan het panel. Percentage = ingevulde verplichte velden / totaal verplichte velden.

Optionele velden (`seizoensverschil`, `opmerking`) tellen NIET mee in de voortgang.

Verplichte velden (15): wp_totaal, eigen_personeel, uitzend, detachering, wsw, man, vrouw, voltijd, deeltijd, pct_op_locatie, adres, perceeloppervlakte, winkeloppervlakte, kantooroppervlakte, bedrijfsvloeroppervlakte.

Optionele velden (4): correspondentieadres, uitbreidingsruimte, seizoensverschil, opmerking.

### Groepen

Drie groepen met headers:

**Personeel** (10 velden):
- WP totaal, Eigen personeel, Uitzendkrachten, Detachering, WSW
- Man, Vrouw, Voltijd, Deeltijd, % op locatie

**Vastgoed** (7 velden):
- Adres, Correspondentieadres (optioneel)
- Perceeloppervlakte, Winkeloppervlakte, Kantooroppervlakte, Bedrijfsvloeroppervlakte
- Uitbreidingsruimte (optioneel)

**Overig** (2 velden):
- Seizoensverschil (optioneel)
- Opmerking (optioneel)

### Veldweergave

Elk veld toont:
- Checkmark (✓) als ingevuld, open cirkel (○) als nog niet ingevuld
- Label (bijv. "WP totaal")
- Waarde in **vetgedrukt** als ingevuld, streepje (—) als null

### Pre-fill

Bij het laden van de chat worden bekende gegevens uit de sessie/verrijking al ingevuld:
- `adres` uit `company.adres`
- Eventueel `wp_totaal` uit `session.pre_fill_wp` (bij gerichte variant)

Deze pre-filled waarden tellen mee in de voortgang.

## Animatie

Wanneer een veld wordt ingevuld of gewijzigd, krijgt de rij een korte teal-glow animatie (Etil-huiskleur `#0d7377` / `bg-etil`). CSS keyframe: border/background glow die in ~1.5s uitfadet. Vergelijkbaar met Skilldemo's `pulse` animatie maar op rijniveau.

## Bevestigingsstap

De assistent verwijst aan het einde naar de sidebar:

> "Controleer het overzicht hiernaast. Klopt alles? Zo ja, dan sla ik het op."

Geen volledig overzicht meer in de chattekst. De gebruiker bevestigt op basis van de sidebar.

## Overzicht-formatting in chat

In de `_FORMAT_RULES` wordt de instructie voor scheidingstekens gewijzigd: waarden in het overzicht worden gescheiden door **komma's**, niet door vetgedrukte punten.

## Gerichte variant

De sidebar is altijd zichtbaar, ongeacht de chat-variant. Bij de gerichte variant zijn de meeste velden leeg (alleen WP + opmerking relevant), maar het panel toont alle groepen. Pre-filled gegevens (adres, wp_totaal) worden getoond. De voortgang wordt berekend op basis van de velden die relevant zijn voor die specifieke variant.

## Componenten (frontend)

Nieuwe componenten in `App.jsx`:

1. **`OverzichtPanel`** — container met voortgangsbalk + groepen
2. **`OverzichtGroep`** — header + lijst van velden
3. **`OverzichtVeld`** — individueel veld met checkmark, label, waarde
4. **`VoortgangsBalk`** — percentage + visuele balk

De bestaande `ChatForm` component wordt uitgebreid met:
- State voor `gegevens` (bijgewerkt na elke response)
- Twee-kolom grid layout
- Rendering van `OverzichtPanel`
