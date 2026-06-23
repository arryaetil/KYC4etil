# Live Overzichtspanel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live-updating overview sidebar to the KYC4etil chat that shows collected data in real-time as the conversation progresses.

**Architecture:** The OpenAI system prompt is modified to return a `gegevens` JSON object with every response. The backend passes this through to the frontend, which renders a sidebar panel (left) next to the chat (right) with grouped fields, checkmarks, and a progress bar. A pulse animation highlights newly filled fields.

**Tech Stack:** Python/FastAPI backend, React/Tailwind frontend (single `App.jsx`), OpenAI GPT-4o-mini.

## Global Constraints

- Python 3.10+ compatible, SQLAlchemy 2 style
- Domain language is Dutch (variable names, labels, comments)
- Tailwind CSS with project palette: `etil: #0f766e`, `line: #d7dde5`, `panel: #f7f8fa`
- All existing tests must keep passing: `pytest tests/ -q`
- `max_tokens` for OpenAI chat stays at 600 (current value in `get_chat_reply`)
- The `ChatForm` component in `App.jsx` handles the public-facing chat UI (no auth)

---

### Task 1: Backend — system prompt + response parsing (`gegevens` bij elke beurt)

**Files:**
- Modify: `backend/app/chat_service.py` (full file, lines 1-186)
- Test: `backend/tests/test_chat_service.py` (create)

**Interfaces:**
- Consumes: `ChatSession`, `Company`, `Enrichment` models (unchanged)
- Produces: `get_chat_reply()` now returns `{"reply": str, "done": bool, "antwoorden": dict|None, "gegevens": dict|None}`

- [ ] **Step 1: Write test file for `_parse_response` with `gegevens`**

Create `backend/tests/test_chat_service.py`:

```python
"""Tests for chat_service response parsing and gegevens extraction."""
import json
import pytest
from app.chat_service import _parse_response


def test_parse_response_with_gegevens():
    raw = json.dumps({
        "reply": "Dank u. Hoeveel uitzendkrachten?",
        "done": False,
        "gegevens": {"wp_totaal": 25, "eigen_personeel": 20, "uitzend": None}
    })
    result = _parse_response(raw)
    assert result["reply"] == "Dank u. Hoeveel uitzendkrachten?"
    assert result["done"] is False
    assert result["gegevens"]["wp_totaal"] == 25
    assert result["gegevens"]["uitzend"] is None


def test_parse_response_without_gegevens():
    raw = json.dumps({"reply": "Hallo!", "done": False})
    result = _parse_response(raw)
    assert result["reply"] == "Hallo!"
    assert "gegevens" not in result


def test_parse_response_done_with_antwoorden_and_gegevens():
    raw = json.dumps({
        "reply": "Bedankt!",
        "done": True,
        "gegevens": {"wp_totaal": 25, "uitzend": 5},
        "antwoorden": {"wp_totaal": 25, "uitzend": 5}
    })
    result = _parse_response(raw)
    assert result["done"] is True
    assert result["gegevens"]["wp_totaal"] == 25
    assert result["antwoorden"]["wp_totaal"] == 25


def test_parse_response_code_fence_with_gegevens():
    raw = '```json\n' + json.dumps({
        "reply": "Test",
        "done": False,
        "gegevens": {"wp_totaal": 10}
    }) + '\n```'
    result = _parse_response(raw)
    assert result["gegevens"]["wp_totaal"] == 10


def test_parse_response_fallback_regex_no_gegevens():
    raw = '{"reply": "broken json", "done": false, extra'
    result = _parse_response(raw)
    assert "broken json" in result["reply"]
    assert result["done"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_chat_service.py -v`

Expected: `test_parse_response_with_gegevens` passes (JSON parsing already works, `gegevens` comes through as a dict key). The other tests should also pass since `_parse_response` already handles these cases — `gegevens` is just another JSON key. Verify all 5 pass.

- [ ] **Step 3: Update `_FORMAT_RULES` — komma-scheidingsteken + `gegevens` instructie**

In `backend/app/chat_service.py`, replace the `_FORMAT_RULES` string (lines 57-65) with:

```python
_FORMAT_RULES = """ANTWOORDFORMAAT:
- Antwoord ALTIJD als één geldig JSON-object: {"reply": "<uw bericht>", "done": false, "gegevens": {<alle tot nu toe bekende waarden>}}
- Het "gegevens" object bevat ALTIJD alle velden uit het schema, met null voor nog onbekende waarden. Werk het bij na elke beurt.
- Bij de LAATSTE beurt (als de gebruiker het overzicht heeft bevestigd): {"reply": "<afsluitend bericht>", "done": true, "gegevens": {<finale data>}, "antwoorden": {<finale data>}}
- GEEN code fences, GEEN emojis, GEEN tekst buiten het JSON-object.
- Je MAG **vetgedrukt** (dubbele sterretjes) gebruiken in de reply-waarde.
- Gebruik komma's als scheidingsteken tussen waarden wanneer je gegevens samenvat in de reply-tekst.
- Gebruik \\n voor nieuwe regels in de reply-waarde.
- Stel maximaal één groep gerelateerde vragen per beurt (max 3-4 vragen per groep).
- Spreek de gebruiker formeel maar vriendelijk aan (u).
- Houd berichten beknopt."""
```

- [ ] **Step 4: Update `_build_system_prompt` — gerichte variant**

Replace the gerichte variant block (lines 110-131) with:

```python
    if session.variant == "gericht":
        return f"""Je bent een vriendelijke data-assistent van Etil Research Group.

DOEL: Bevestig of corrigeer het aantal werkzame personen voor deze vestiging, en vraag een optionele toelichting.

{_PRIVACY_OPENING}

BEKENDE GEGEVENS:
{bekende_info}
Geschat aantal WP: {session.pre_fill_wp}

GESPREKSVERLOOP:
1. Begroeting + transparantie (wie, waarvoor, review). Vraag bevestiging bedrijfsnaam en rol invuller.
2. Presenteer de geschatte WP-waarde en vraag: "Klopt dit aantal, of wilt u het corrigeren?"
3. Vraag of de gebruiker nog een toelichting wil toevoegen.
4. BEVESTIGINGSSTAP: Verwijs naar het overzicht dat de gebruiker links in beeld ziet. Vraag: "Controleer het overzicht hiernaast. Klopt alles? Zo ja, dan sla ik het op."
5. Als de gebruiker "ja" zegt: bedank en sluit af met done: true. Als "nee": corrigeer en vraag opnieuw.

Bij de laatste beurt, voeg een "antwoorden" object toe met:
{{"wp_totaal": <bevestigd of gecorrigeerd getal>, "opmerking": <toelichting of null>}}

GEGEVENS-SCHEMA (gebruik dit voor het "gegevens" object in elke beurt):
{_ANTWOORDEN_SCHEMA}

{_FORMAT_RULES}"""
```

- [ ] **Step 5: Update `_build_system_prompt` — uitgebreide variant**

Replace the uitgebreide variant block (lines 133-158) with:

```python
    return f"""Je bent een vriendelijke data-assistent van Etil Research Group.

DOEL: Verzamel personeels- en vastgoedgegevens voor deze vestiging via een natuurlijk gesprek. Groepeer gerelateerde vragen. Bevestig wat al bekend is — vraag het niet opnieuw.

{_PRIVACY_OPENING}

BEKENDE GEGEVENS (bevestig, niet opnieuw vragen):
{bekende_info}

GESPREKSVERLOOP (groepeer in ~5-6 beurten):
1. Begroeting + transparantie. Bevestig bekende gegevens (adres, bedrijfsnaam). Vraag rol invuller.
2. WP totaal + uitsplitsing: eigen personeel, uitzendkrachten, detachering, WSW.
3. Man/vrouw, voltijd/deeltijd, percentage werkzaam op locatie (≥60% van de tijd).
4. Oppervlaktes: perceel, winkel, kantoor, bedrijfsvloer. Uitbreidingsruimte.
5. Seizoensverschillen en eventuele opmerkingen.
6. BEVESTIGINGSSTAP: Verwijs naar het overzicht dat de gebruiker links in beeld ziet. Vraag: "Controleer het overzicht hiernaast. Klopt alles? Zo ja, dan sla ik het op."
7. Als de gebruiker "ja" zegt: bedank en sluit af met done: true. Als "nee": corrigeer en vraag opnieuw.

BELANGRIJK:
- Als de gebruiker een veld niet weet of het is niet van toepassing, accepteer dat en ga door.
- Zet null voor onbekende velden in het gegevens/antwoorden-object.

GEGEVENS-SCHEMA (gebruik dit voor het "gegevens" object in elke beurt EN voor "antwoorden" bij de laatste beurt):
{_ANTWOORDEN_SCHEMA}

{_FORMAT_RULES}"""
```

- [ ] **Step 6: Update `get_chat_reply` to pass through `gegevens`**

Replace the return block in `get_chat_reply` (lines 181-185) with:

```python
    gegevens = parsed.get("gegevens")
    antwoorden = parsed.get("antwoorden")
    if not antwoorden and parsed.get("done") and gegevens:
        antwoorden = gegevens

    return {
        "reply": parsed.get("reply", raw),
        "done": bool(parsed.get("done", False)),
        "antwoorden": antwoorden,
        "gegevens": gegevens,
    }
```

- [ ] **Step 7: Update `max_tokens` to accommodate `gegevens` in every response**

The `gegevens` object adds ~200 tokens per response. In `get_chat_reply`, change `max_tokens=600` to `max_tokens=900`:

```python
    response = await client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=900,
        messages=[{"role": "system", "content": system_text}] + messages,
    )
```

- [ ] **Step 8: Run all tests**

Run: `cd backend && python -m pytest tests/ -q`

Expected: all existing tests pass, plus the 5 new tests in `test_chat_service.py`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/chat_service.py backend/tests/test_chat_service.py
git commit -m "feat(chat): add gegevens to every response + komma separator"
```

---

### Task 2: Backend — endpoint returns `gegevens` + pre-fill data

**Files:**
- Modify: `backend/app/routers/chat.py` (lines 86-113)
- Modify: `backend/app/routers/chat.py` (lines 33-51, `get_chat_session`)

**Interfaces:**
- Consumes: `get_chat_reply()` return dict (from Task 1) with `gegevens` key
- Produces: `POST /chat/{token}/message` response adds `"gegevens": dict|null`; `GET /chat/{token}` response adds `"adres": str|null`, `"pre_fill_wp": int|null`

- [ ] **Step 1: Update `chat_message` endpoint to return `gegevens`**

In `backend/app/routers/chat.py`, change the return statement on line 113 from:

```python
    return {"reply": result["reply"], "done": result["done"]}
```

to:

```python
    return {"reply": result["reply"], "done": result["done"], "gegevens": result.get("gegevens")}
```

- [ ] **Step 2: Update `get_chat_session` to return pre-fill data**

In `backend/app/routers/chat.py`, update the return dict in `get_chat_session` (lines 43-51). Replace:

```python
    return {
        "bedrijfsnaam": comp.naam if comp else "Onbekend bedrijf",
        "gemeente": comp.gemeente if comp else None,
        "variant": session.variant,
        "pre_fill_wp": session.pre_fill_wp,
        "status": session.status,
        "vragen": session.vragen if session.vragen else DEFAULT_VRAGEN,
        "messages": session.messages or [],
    }
```

with:

```python
    return {
        "bedrijfsnaam": comp.naam if comp else "Onbekend bedrijf",
        "gemeente": comp.gemeente if comp else None,
        "adres": comp.adres if comp else None,
        "variant": session.variant,
        "pre_fill_wp": session.pre_fill_wp,
        "status": session.status,
        "vragen": session.vragen if session.vragen else DEFAULT_VRAGEN,
        "messages": session.messages or [],
    }
```

- [ ] **Step 3: Run all tests**

Run: `cd backend && python -m pytest tests/ -q`

Expected: all tests pass (endpoint changes are additive, no breaking changes).

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/chat.py
git commit -m "feat(chat): return gegevens + adres from chat endpoints"
```

---

### Task 3: Frontend — OverzichtPanel component + pulse animatie

**Files:**
- Modify: `frontend/src/App.jsx` (add new components before `ChatForm`, ~line 1088)
- Modify: `frontend/src/index.css` (add pulse keyframe)

**Interfaces:**
- Consumes: `gegevens` object (dict with 19 keys, values are numbers/strings/null)
- Produces: `OverzichtPanel` React component; props: `gegevens: object, preFill: object, session: object`

- [ ] **Step 1: Add pulse animation CSS**

In `frontend/src/index.css`, add after the existing `.focus-ring` rule (end of file):

```css
@keyframes fieldPulse {
  0% { background-color: rgba(15, 118, 110, 0.15); }
  100% { background-color: transparent; }
}
.field-pulse {
  animation: fieldPulse 1.5s ease-out;
}
```

- [ ] **Step 2: Add field/group configuration constant**

In `frontend/src/App.jsx`, add after the `LABELS` constant (line 28), before `STRATEGIE_LABELS`:

```jsx
const OVERZICHT_GROEPEN = [
  {
    titel: "Personeel",
    velden: [
      {key: "wp_totaal", label: "WP totaal", verplicht: true},
      {key: "eigen_personeel", label: "Eigen personeel", verplicht: true},
      {key: "uitzend", label: "Uitzendkrachten", verplicht: true},
      {key: "detachering", label: "Detachering", verplicht: true},
      {key: "wsw", label: "WSW", verplicht: true},
      {key: "man", label: "Man", verplicht: true},
      {key: "vrouw", label: "Vrouw", verplicht: true},
      {key: "voltijd", label: "Voltijd", verplicht: true},
      {key: "deeltijd", label: "Deeltijd", verplicht: true},
      {key: "pct_op_locatie", label: "% op locatie", verplicht: true},
    ],
  },
  {
    titel: "Vastgoed",
    velden: [
      {key: "adres", label: "Adres", verplicht: true},
      {key: "correspondentieadres", label: "Correspondentieadres", verplicht: false},
      {key: "perceeloppervlakte", label: "Perceeloppervlakte", verplicht: true},
      {key: "winkeloppervlakte", label: "Winkeloppervlakte", verplicht: true},
      {key: "kantooroppervlakte", label: "Kantooroppervlakte", verplicht: true},
      {key: "bedrijfsvloeroppervlakte", label: "Bedrijfsvloeroppervlakte", verplicht: true},
      {key: "uitbreidingsruimte", label: "Uitbreidingsruimte", verplicht: false},
    ],
  },
  {
    titel: "Overig",
    velden: [
      {key: "seizoensverschil", label: "Seizoensverschil", verplicht: false},
      {key: "opmerking", label: "Opmerking", verplicht: false},
    ],
  },
];
```

- [ ] **Step 3: Add `OverzichtPanel` component**

In `frontend/src/App.jsx`, add before the `ChatForm` component (before line 1090):

```jsx
function OverzichtPanel({gegevens}) {
  const prevGegevensRef = useRef({});

  const merged = gegevens || {};
  const verplicht = OVERZICHT_GROEPEN.flatMap((g) => g.velden.filter((v) => v.verplicht));
  const ingevuld = verplicht.filter((v) => merged[v.key] != null).length;
  const totaal = verplicht.length;
  const pctVoortgang = totaal ? Math.round((ingevuld / totaal) * 100) : 0;

  const changedKeys = new Set();
  const prev = prevGegevensRef.current;
  for (const key of Object.keys(merged)) {
    if (merged[key] != null && prev[key] !== merged[key]) {
      changedKeys.add(key);
    }
  }

  useEffect(() => {
    prevGegevensRef.current = {...merged};
  }, [gegevens]);

  return (
    <div className="flex flex-col gap-4 overflow-y-auto rounded-lg border border-line bg-white p-4 shadow-sm" style={{maxHeight: "85vh"}}>
      <div>
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-semibold text-slate-700">Voortgang</span>
          <span className="font-bold text-etil">{pctVoortgang}%</span>
        </div>
        <div className="h-2 rounded-full bg-slate-200">
          <div
            className="h-2 rounded-full bg-etil transition-all duration-500"
            style={{width: `${pctVoortgang}%`}}
          />
        </div>
        <div className="mt-1 text-xs text-slate-400">{ingevuld} van {totaal} verplichte velden</div>
      </div>

      {OVERZICHT_GROEPEN.map((groep) => {
        const groepIngevuld = groep.velden.filter((v) => v.verplicht && merged[v.key] != null).length;
        const groepTotaal = groep.velden.filter((v) => v.verplicht).length;
        const groepKlaar = groepTotaal > 0 && groepIngevuld === groepTotaal;

        return (
          <div key={groep.titel}>
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
              {groepKlaar
                ? <span className="flex h-4 w-4 items-center justify-center rounded-full bg-etil text-[10px] text-white">✓</span>
                : <span className="flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 text-[10px] text-slate-400">○</span>
              }
              {groep.titel}
              <span className="ml-auto font-normal text-slate-400">{groepIngevuld}/{groepTotaal}</span>
            </div>
            <div className="space-y-0.5">
              {groep.velden.map((veld) => {
                const waarde = merged[veld.key];
                const heeftWaarde = waarde != null;
                const isChanged = changedKeys.has(veld.key);

                return (
                  <div
                    key={veld.key}
                    className={classNames(
                      "flex items-center gap-2 rounded px-2 py-1 text-sm",
                      isChanged && "field-pulse"
                    )}
                  >
                    {heeftWaarde
                      ? <span className="text-etil text-xs">✓</span>
                      : <span className="text-xs text-slate-300">○</span>
                    }
                    <span className={classNames("flex-1", heeftWaarde ? "text-slate-700" : "text-slate-400")}>
                      {veld.label}
                    </span>
                    <span className={classNames("text-right", heeftWaarde ? "font-semibold text-slate-900" : "text-slate-300")}>
                      {heeftWaarde ? String(waarde) : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run dev server and visually verify the component renders**

Run: `cd frontend && npm run dev`

Open the browser. The component will not be wired up to `ChatForm` yet — that's Task 4. Verify no build errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/index.css
git commit -m "feat(chat): add OverzichtPanel component with progress bar and pulse animation"
```

---

### Task 4: Frontend — wire OverzichtPanel into ChatForm + two-column layout

**Files:**
- Modify: `frontend/src/App.jsx` — `ChatForm` component (lines 1090-1260)

**Interfaces:**
- Consumes: `OverzichtPanel` component (from Task 3), `gegevens` from `POST /chat/{token}/message` response (from Task 2)
- Produces: Updated `ChatForm` with two-column layout, `gegevens` state, pre-fill from session data

- [ ] **Step 1: Add `gegevens` state and pre-fill logic to `ChatForm`**

In the `ChatForm` function, after the existing state declarations (line 1097, after `const scrollRef = useRef(null);`), add:

```jsx
  const [gegevens, setGegevens] = useState(null);
```

In the `useEffect` that fetches the session (lines 1100-1116), update the success handler to build the initial pre-fill. Replace:

```jsx
        } else {
          setSession(data);
          if (data.messages && data.messages.length > 0) {
            setMessages(data.messages);
          } else {
            fetchReply([]);
          }
        }
```

with:

```jsx
        } else {
          setSession(data);
          const preFill = {};
          if (data.adres) preFill.adres = data.adres;
          if (data.pre_fill_wp) preFill.wp_totaal = data.pre_fill_wp;
          if (Object.keys(preFill).length > 0) setGegevens(preFill);
          if (data.messages && data.messages.length > 0) {
            setMessages(data.messages);
          } else {
            fetchReply([]);
          }
        }
```

- [ ] **Step 2: Update `fetchReply` to capture `gegevens` from response**

In the `fetchReply` function (lines 1122-1140), after `if (data.done) setDone(true);` (line 1134), add:

```jsx
      if (data.gegevens) setGegevens(data.gegevens);
```

The full try-block becomes:

```jsx
    try {
      const r = await fetch(`${API_URL}/chat/${token}/message`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({messages: msgs}),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Fout in de chat.");
      const updated = [...msgs, {role: "assistant", content: data.reply}];
      setMessages(updated);
      if (data.done) setDone(true);
      if (data.gegevens) setGegevens(data.gegevens);
    } catch (err) {
```

- [ ] **Step 3: Update ChatForm layout to two-column with sidebar**

Replace the main return block (starting from `return (` at line 1179, the normal chat rendering) — the block starting with `<main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4 py-8">` through to the closing `</main>` — with:

```jsx
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4 py-8">
      <div className="grid w-full gap-4" style={{maxWidth: "1000px", gridTemplateColumns: "320px 1fr"}}>
        <OverzichtPanel gegevens={gegevens} />

        <div className="flex flex-col rounded-lg border border-line bg-white shadow-sm" style={{maxHeight: "90vh"}}>
          <div className="flex-shrink-0 rounded-t-lg bg-etil px-6 py-4">
            <div className="flex items-center gap-3">
              <ShieldCheck className="text-white/80" size={22} />
              <div>
                <div className="text-sm font-semibold text-white">Vestigingsregister AI</div>
                <div className="text-xs text-white/70">Etil Research Group — Provincie Limburg</div>
              </div>
            </div>
          </div>

          <div ref={scrollRef} className="flex flex-1 flex-col gap-3 overflow-y-auto p-4" style={{minHeight: "300px"}}>
            {messages.map((msg, i) => (
              <div key={i} className={classNames("flex gap-2", msg.role === "user" ? "flex-row-reverse" : "flex-row")}>
                <div className={classNames(
                  "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold",
                  msg.role === "user" ? "bg-slate-200 text-slate-600" : "bg-etil text-white"
                )}>
                  {msg.role === "user" ? "U" : "E"}
                </div>
                <div className={classNames(
                  "max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "rounded-br-sm bg-etil text-white"
                    : "rounded-bl-sm border border-line bg-panel text-slate-800"
                )} style={{whiteSpace: "pre-wrap"}}>
                  {msg.content.split(/(\*\*.*?\*\*)/).map((part, j) =>
                    part.startsWith("**") && part.endsWith("**")
                      ? <strong key={j}>{part.slice(2, -2)}</strong>
                      : part
                  )}
                </div>
              </div>
            ))}
            {typing && (
              <div className="flex gap-2">
                <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-etil text-xs font-bold text-white">E</div>
                <div className="flex items-center gap-1 rounded-xl rounded-bl-sm border border-line bg-panel px-4 py-3">
                  <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-etil" style={{animationDelay: "0ms"}} />
                  <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-etil" style={{animationDelay: "150ms"}} />
                  <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-etil" style={{animationDelay: "300ms"}} />
                </div>
              </div>
            )}
            {done && messages.length > 0 && (
              <div className="mx-auto my-4 flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700">
                <Check size={16} /> Gegevens ontvangen — bedankt!
              </div>
            )}
          </div>

          {!done && (
            <form onSubmit={send} className="flex flex-shrink-0 gap-2 border-t border-line p-3">
              <input
                className="focus-ring h-11 flex-1 rounded-md border border-line px-3 text-sm"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Typ uw antwoord..."
                disabled={typing}
                autoFocus
              />
              <button
                type="submit"
                disabled={typing || !input.trim()}
                className="focus-ring flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-md bg-etil text-white transition hover:opacity-90 disabled:opacity-40"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </form>
          )}

          <div className="flex-shrink-0 px-4 pb-3 text-center text-xs text-slate-400">
            Uw gegevens worden uitsluitend gebruikt voor het Vestigingsregister van Provincie Limburg.
          </div>
        </div>
      </div>
    </main>
  );
```

- [ ] **Step 4: Update error/loading/done-without-messages states for new layout**

The error, done-without-messages, and loading screens (lines 1152-1177) should remain full-screen centered (no sidebar needed). These are already correct — they render before the two-column layout and return early. No changes needed, but verify they still work by checking that each early-return still renders a `<main>` with centered content.

- [ ] **Step 5: Run dev server and test end-to-end**

Run: `cd frontend && npm run dev` (frontend) and `cd backend && uvicorn app.main:app --reload` (backend)

Test by opening a chat link. Verify:
1. Sidebar appears on the left with all three groups
2. Pre-filled values (adres, wp_totaal) appear immediately
3. As you chat, new values fill in with the pulse animation
4. Progress bar updates
5. Checkmarks appear for filled fields

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(chat): wire OverzichtPanel into ChatForm with two-column layout"
```

---

### Task 5: Mobile responsive — stackable layout

**Files:**
- Modify: `frontend/src/App.jsx` — `ChatForm` component (return block from Task 4)

**Interfaces:**
- Consumes: Two-column layout from Task 4
- Produces: Responsive layout that stacks on mobile (<768px)

- [ ] **Step 1: Make the grid responsive**

In the `ChatForm` return block (from Task 4), change the grid container from:

```jsx
      <div className="grid w-full gap-4" style={{maxWidth: "1000px", gridTemplateColumns: "320px 1fr"}}>
```

to:

```jsx
      <div className="mx-auto grid w-full max-w-[1000px] gap-4 md:grid-cols-[320px_1fr]">
```

This makes it single-column on mobile (stacked: sidebar on top, chat below) and two-column on md+ screens.

- [ ] **Step 2: Add mobile max-height constraint to OverzichtPanel**

In the `OverzichtPanel` component, change the outer div from:

```jsx
    <div className="flex flex-col gap-4 overflow-y-auto rounded-lg border border-line bg-white p-4 shadow-sm" style={{maxHeight: "85vh"}}>
```

to:

```jsx
    <div className="flex flex-col gap-4 overflow-y-auto rounded-lg border border-line bg-white p-4 shadow-sm max-h-[40vh] md:max-h-[85vh]">
```

On mobile the overview takes max 40% of viewport height so the chat remains visible.

- [ ] **Step 3: Test on mobile viewport**

Open browser DevTools, toggle device toolbar (Ctrl+Shift+M), test at 375px width:
- Overview should stack above chat
- Overview should be scrollable within 40vh
- Chat should still be usable below

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(chat): responsive mobile layout for overzicht + chat"
```
