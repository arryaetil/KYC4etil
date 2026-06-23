# Chat Module (Fase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static ChatForm with an OpenAI-powered conversational chatbot that collects WP-data (and vastgoeddata in the volledig variant) through grouped questions in a natural dialogue.

**Architecture:** Cloudcast-pattern — stateless per request. Frontend sends full message history each turn to `POST /chat/{token}/message`. Backend builds a dynamic system prompt from the ChatSession context (variant, company, enrichment), sends it to OpenAI, parses the JSON response, persists messages on the session, and returns the reply. The existing `GET /chat/{token}` and `POST /chat/{token}/submit` endpoints stay untouched as fallback.

**Tech Stack:** Python 3.10+ / FastAPI / SQLAlchemy 2 / OpenAI (`gpt-4o-mini`) / React + Tailwind (existing KYC frontend)

## Global Constraints

- All code lives in `C:\Etil\KYC4etil` — the KYC Vestigingsregister project
- Python 3.10+ compatible, SQLAlchemy 2 with `Mapped`/`mapped_column`
- Domain language is Dutch (wp_kandidaat, antwoorden, etc.)
- Weights/thresholds in `app/config.py`, never hardcoded
- `openai` package already in `requirements.txt` (>=2.0)
- No new frontend dependencies — use existing Tailwind classes
- Existing tests: `pytest tests/ -q` must keep passing
- Existing validation: `python -m scripts.validate` must stay green

---

### Task 1: Add `messages` field to ChatSession model

**Files:**
- Modify: `backend/app/models.py:147-160` (ChatSession class)

**Interfaces:**
- Produces: `ChatSession.messages` — `Mapped[list | None]` backed by `JSON`, stores `[{"role": "user"|"assistant", "content": "..."}]`

- [ ] **Step 1: Add the messages column to ChatSession**

In `backend/app/models.py`, add the `messages` field after line 156 (`antwoorden`):

```python
# In class ChatSession, after the antwoorden field:
    messages: Mapped[list | None] = mapped_column(JSON)
```

The full ChatSession class should now have these fields in order:
```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    token_hash: Mapped[str] = mapped_column(String(255), unique=True)
    variant: Mapped[str] = mapped_column(String(10))  # gericht|volledig
    status: Mapped[str] = mapped_column(String(50), default="created")
    pre_fill_wp: Mapped[int | None] = mapped_column(Integer)
    vragen: Mapped[dict | None] = mapped_column(JSON)
    antwoorden: Mapped[dict | None] = mapped_column(JSON)
    messages: Mapped[list | None] = mapped_column(JSON)
    verwerkt: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
```

- [ ] **Step 2: Verify the app starts and tables migrate**

Run (from `backend/`):
```bash
python -c "from app.models import ChatSession; print('messages' in [c.name for c in ChatSession.__table__.columns])"
```
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models.py
git commit -m "feat(chat): add messages JSON field to ChatSession for conversation history"
```

---

### Task 2: Token hashing

**Files:**
- Create: `backend/app/chat_utils.py`
- Modify: `backend/app/routers/review.py:92-126` (create_chat_session)
- Modify: `backend/app/routers/chat.py:31-77` (get_chat_session, submit_chat)

**Interfaces:**
- Produces: `hash_token(plain: str) -> str` — sha256 hex digest
- Produces: `lookup_session(token: str, db: Session) -> ChatSession` — hashes then queries

- [ ] **Step 1: Create chat_utils.py with hash and lookup helpers**

Create `backend/app/chat_utils.py`:

```python
"""Shared utilities for chat token handling."""
import hashlib
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import ChatSession


def hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def lookup_session(token: str, db: Session) -> ChatSession:
    hashed = hash_token(token)
    session = db.query(ChatSession).filter_by(token_hash=hashed).first()
    if not session:
        raise HTTPException(404, "Chat-sessie niet gevonden of verlopen")
    if session.expires_at and session.expires_at < datetime.now(timezone.utc):
        raise HTTPException(410, "Deze chat-link is verlopen")
    return session
```

- [ ] **Step 2: Update create_chat_session in review.py to hash the token**

In `backend/app/routers/review.py`, add the import at the top (after existing imports):

```python
from ..chat_utils import hash_token
```

Then change lines 102-104 from:

```python
    token = secrets.token_urlsafe(32)
    session = ChatSession(company_id=cand.company_id, token_hash=token,
                          variant="gericht", pre_fill_wp=cand.wp_kandidaat, vragen=vragen)
```

to:

```python
    token = secrets.token_urlsafe(32)
    session = ChatSession(company_id=cand.company_id, token_hash=hash_token(token),
                          variant="gericht", pre_fill_wp=cand.wp_kandidaat, vragen=vragen,
                          expires_at=datetime.utcnow() + timedelta(days=14))
```

Also add `from datetime import datetime, timedelta` to the imports at the top of the file if not already present.

- [ ] **Step 3: Update chat.py to use lookup_session**

In `backend/app/routers/chat.py`, add the import:

```python
from ..chat_utils import lookup_session
```

Replace the lookup in `get_chat_session` (line 34):

```python
# Old:
    session = db.query(ChatSession).filter_by(token_hash=token).first()
    if not session:
        raise HTTPException(404, "Chat-sessie niet gevonden of verlopen")
# New:
    session = lookup_session(token, db)
```

Replace the lookup in `submit_chat` (line 57):

```python
# Old:
    session = db.query(ChatSession).filter_by(token_hash=token).first()
    if not session:
        raise HTTPException(404, "Chat-sessie niet gevonden of verlopen")
# New:
    session = lookup_session(token, db)
```

- [ ] **Step 4: Update get_chat_session to set status to "opened" and return messages**

In `get_chat_session`, after the lookup, add status tracking and messages to the response:

```python
@router.get("/{token}")
def get_chat_session(token: str, db: Session = Depends(get_db)):
    """Haalt chat-sessie op op basis van token. Geen auth vereist."""
    session = lookup_session(token, db)
    if session.status == "completed":
        return {"status": "completed"}
    if session.status in ("created", "sent"):
        session.status = "opened"
        db.commit()
    comp = db.get(Company, session.company_id)
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

- [ ] **Step 5: Verify manually**

Run (from `backend/`):
```bash
python -c "from app.chat_utils import hash_token; print(len(hash_token('test')) == 64)"
```
Expected: `True`

- [ ] **Step 6: Commit**

```bash
git add backend/app/chat_utils.py backend/app/routers/review.py backend/app/routers/chat.py
git commit -m "feat(chat): add token hashing with sha256 and 14-day expiry"
```

---

### Task 3: OpenAI chat service with system prompts

**Files:**
- Create: `backend/app/chat_service.py`

**Interfaces:**
- Consumes: `app.config.get_settings()` for `openai_api_key`, `openai_model`
- Produces: `async def get_chat_reply(messages: list[dict], session: ChatSession, company: Company, enrichment: Enrichment | None) -> dict` — returns `{"reply": str, "done": bool, "antwoorden": dict | None}`

- [ ] **Step 1: Create chat_service.py with prompt builder and OpenAI call**

Create `backend/app/chat_service.py`:

```python
"""OpenAI-powered chat service for WP data collection."""
import json
import re
from typing import Any

import openai

from .config import get_settings
from .models import ChatSession, Company, Enrichment


def _escape_newlines_in_strings(s: str) -> str:
    result: list[str] = []
    in_string = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\' and in_string and i + 1 < len(s):
            result.extend([c, s[i + 1]])
            i += 2
            continue
        if c == '"':
            in_string = not in_string
        if c in ('\n', '\r') and in_string:
            result.append('\\n')
        else:
            result.append(c)
        i += 1
    return ''.join(result)


def _parse_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    try:
        return json.loads(_escape_newlines_in_strings(raw))
    except json.JSONDecodeError:
        pass

    m = re.search(r'"reply"\s*:\s*"(.*?)",?\s*"done"', raw, re.DOTALL)
    if m:
        reply = m.group(1).replace('\\n', '\n').replace('\\"', '"')
        done = bool(re.search(r'"done"\s*:\s*true', raw))
        return {"reply": reply, "done": done}

    return {"reply": raw, "done": False}


_FORMAT_RULES = """ANTWOORDFORMAAT:
- Antwoord ALTIJD als één geldig JSON-object: {"reply": "<uw bericht>", "done": false}
- Bij de LAATSTE beurt (als u alle benodigde informatie heeft): {"reply": "<afsluitend bericht>", "done": true, "antwoorden": {<alle verzamelde data>}}
- GEEN code fences, GEEN markdown, GEEN emojis, GEEN tekst buiten het JSON-object.
- Gebruik \\n voor nieuwe regels in de reply-waarde.
- Stel maximaal één groep gerelateerde vragen per beurt (max 3-4 vragen per groep).
- Spreek de gebruiker formeel maar vriendelijk aan (u).
- Houd berichten beknopt."""

_ANTWOORDEN_SCHEMA = """{
  "wp_totaal": <getal of null>,
  "eigen_personeel": <getal of null>,
  "uitzend": <getal of null>,
  "detachering": <getal of null>,
  "wsw": <getal of null>,
  "man": <getal of null>,
  "vrouw": <getal of null>,
  "voltijd": <getal of null>,
  "deeltijd": <getal of null>,
  "pct_op_locatie": <getal of null>,
  "adres": <tekst of null>,
  "correspondentieadres": <tekst of null>,
  "perceeloppervlakte": <getal of null>,
  "winkeloppervlakte": <getal of null>,
  "kantooroppervlakte": <getal of null>,
  "bedrijfsvloeroppervlakte": <getal of null>,
  "uitbreidingsruimte": <tekst of null>,
  "seizoensverschil": <tekst of null>,
  "opmerking": <tekst of null>
}"""


def _build_system_prompt(session: ChatSession, company: Company,
                         enrichment: Enrichment | None) -> str:
    bekende_info = f"Bedrijfsnaam: {company.naam}"
    if company.gemeente:
        bekende_info += f"\nGemeente: {company.gemeente}"
    if company.adres:
        bekende_info += f"\nAdres: {company.adres}"
    if enrichment:
        if enrichment.website_url:
            bekende_info += f"\nWebsite: {enrichment.website_url}"
        if enrichment.telefoonnummer:
            bekende_info += f"\nTelefoon: {enrichment.telefoonnummer}"

    privacy_opening = (
        "Open het gesprek met: u bent benaderd door Etil Research Group, in opdracht van "
        "Provincie Limburg, voor het jaarlijkse Vestigingsregister. De antwoorden worden "
        "door een medewerker gecontroleerd voordat ze worden verwerkt. "
        "Vraag eerst bevestiging van de bedrijfsnaam en de rol/functie van de invuller."
    )

    if session.variant == "gericht":
        return f"""Je bent een vriendelijke data-assistent van Etil Research Group.

DOEL: Bevestig of corrigeer het aantal werkzame personen voor deze vestiging, en vraag een optionele toelichting.

{privacy_opening}

BEKENDE GEGEVENS:
{bekende_info}
Geschat aantal WP: {session.pre_fill_wp}

GESPREKSVERLOOP:
1. Begroeting + transparantie (wie, waarvoor, review). Vraag bevestiging bedrijfsnaam en rol invuller.
2. Presenteer de geschatte WP-waarde en vraag: "Klopt dit aantal, of wilt u het corrigeren?"
3. Vraag of de gebruiker nog een toelichting wil toevoegen.
4. Bedank en sluit af met done: true.

Bij de laatste beurt, voeg een "antwoorden" object toe met:
{{"wp_totaal": <bevestigd of gecorrigeerd getal>, "opmerking": <toelichting of null>}}

{_FORMAT_RULES}"""

    else:  # volledig
        return f"""Je bent een vriendelijke data-assistent van Etil Research Group.

DOEL: Verzamel personeels- en vastgoedgegevens voor deze vestiging via een natuurlijk gesprek. Groepeer gerelateerde vragen. Bevestig wat al bekend is — vraag het niet opnieuw.

{privacy_opening}

BEKENDE GEGEVENS (bevestig, niet opnieuw vragen):
{bekende_info}

GESPREKSVERLOOP (groepeer in ~5-6 beurten):
1. Begroeting + transparantie. Bevestig bekende gegevens (adres, bedrijfsnaam). Vraag rol invuller.
2. WP totaal + uitsplitsing: eigen personeel, uitzendkrachten, detachering, WSW.
3. Man/vrouw, voltijd/deeltijd, percentage werkzaam op locatie (≥60% van de tijd).
4. Oppervlaktes: perceel, winkel, kantoor, bedrijfsvloer. Uitbreidingsruimte.
5. Seizoensverschillen en eventuele opmerkingen.
6. Samenvatting en afsluiting.

BELANGRIJK:
- Als de gebruiker een veld niet weet of het is niet van toepassing, accepteer dat en ga door.
- Zet null voor onbekende velden in het antwoorden-object.

Bij de laatste beurt, voeg een "antwoorden" object toe met dit schema:
{_ANTWOORDEN_SCHEMA}

{_FORMAT_RULES}"""


async def get_chat_reply(messages: list[dict], session: ChatSession,
                         company: Company,
                         enrichment: Enrichment | None) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        return {"reply": "De chatservice is momenteel niet beschikbaar. "
                         "Neem contact op met Etil Research Group.", "done": False}

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    system_text = _build_system_prompt(session, company, enrichment)

    response = await client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=600,
        messages=[{"role": "system", "content": system_text}] + messages,
    )

    raw = response.choices[0].message.content.strip()
    parsed = _parse_response(raw)

    return {
        "reply": parsed.get("reply", raw),
        "done": bool(parsed.get("done", False)),
        "antwoorden": parsed.get("antwoorden"),
    }
```

- [ ] **Step 2: Verify the module imports cleanly**

Run (from `backend/`):
```bash
python -c "from app.chat_service import get_chat_reply, _build_system_prompt; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/chat_service.py
git commit -m "feat(chat): add OpenAI chat service with dynamic system prompts"
```

---

### Task 4: Message endpoint

**Files:**
- Modify: `backend/app/routers/chat.py` (add `/chat/{token}/message` POST endpoint)

**Interfaces:**
- Consumes: `chat_utils.lookup_session(token, db)` from Task 2
- Consumes: `chat_service.get_chat_reply(messages, session, company, enrichment)` from Task 3
- Produces: `POST /chat/{token}/message` — `{"reply": str, "done": bool}`

- [ ] **Step 1: Add the message endpoint to chat.py**

In `backend/app/routers/chat.py`, add the import at the top:

```python
from ..chat_service import get_chat_reply
```

Then add the new endpoint after the existing `submit_chat` function (after line 77):

```python
class ChatMessageRequest(BaseModel):
    messages: list[dict]


@router.post("/{token}/message")
async def chat_message(token: str, body: ChatMessageRequest,
                       db: Session = Depends(get_db)):
    """Conversational chat endpoint — stuurt berichtgeschiedenis naar OpenAI."""
    session = lookup_session(token, db)
    if session.status == "completed":
        raise HTTPException(409, "Deze chat-sessie is al afgerond")

    if session.status in ("created", "sent"):
        session.status = "opened"

    comp = db.get(Company, session.company_id)
    enrichment = comp.enrichment if comp else None

    result = await get_chat_reply(body.messages, session, comp, enrichment)

    all_messages = list(body.messages)
    all_messages.append({"role": "assistant", "content": result["reply"]})
    session.messages = all_messages

    if result["done"]:
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        if result.get("antwoorden"):
            session.antwoorden = result["antwoorden"]

    db.commit()
    return {"reply": result["reply"], "done": result["done"]}
```

Make sure all required imports are at the top of `chat.py`:

```python
from datetime import datetime
from ..chat_utils import lookup_session
from ..chat_service import get_chat_reply
from ..models import ChatSession, Company
```

- [ ] **Step 2: Verify the server starts**

Run (from `backend/`):
```bash
python -c "from app.main import app; print([r.path for r in app.routes if 'message' in r.path])"
```
Expected: output includes `/chat/{token}/message`

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/chat.py
git commit -m "feat(chat): add POST /chat/{token}/message conversational endpoint"
```

---

### Task 5: Conversational ChatForm frontend

**Files:**
- Modify: `frontend/src/App.jsx:1090-1259` (replace ChatForm component)

**Interfaces:**
- Consumes: `GET /chat/{token}` (existing, now also returns `messages`)
- Consumes: `POST /chat/{token}/message` (new, from Task 4)

- [ ] **Step 1: Replace the ChatForm component**

In `frontend/src/App.jsx`, replace the entire `ChatForm` function (lines 1090-1259) with:

```jsx
function ChatForm({token}) {
  const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    fetch(`${API_URL}/chat/${token}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "completed") {
          setDone(true);
        } else {
          setSession(data);
          if (data.messages && data.messages.length > 0) {
            setMessages(data.messages);
          } else {
            fetchReply([]);
          }
        }
      })
      .catch(() => setError("Chat-sessie niet gevonden of verlopen."));
  }, [token]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, typing]);

  async function fetchReply(msgs) {
    setTyping(true);
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
    } catch (err) {
      setMessages((prev) => [...prev, {role: "assistant", content: "Er is een fout opgetreden. Probeer het opnieuw."}]);
    } finally {
      setTyping(false);
    }
  }

  async function send(e) {
    if (e) e.preventDefault();
    const text = input.trim();
    if (!text || typing || done) return;
    setInput("");
    const updated = [...messages, {role: "user", content: text}];
    setMessages(updated);
    await fetchReply(updated);
  }

  if (error && !session) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4">
      <div className="w-full max-w-md rounded-lg border border-red-200 bg-white p-8 text-center shadow-sm">
        <X className="mx-auto mb-3 text-red-500" size={32} />
        <p className="font-medium text-red-800">{error}</p>
      </div>
    </main>
  );

  if (done && !messages.length) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4">
      <div className="w-full max-w-md rounded-lg border border-line bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100">
          <Check className="text-emerald-600" size={28} />
        </div>
        <h2 className="mb-2 text-xl font-semibold">Bedankt!</h2>
        <p className="text-slate-600">Uw gegevens zijn ontvangen. U kunt dit venster sluiten.</p>
      </div>
    </main>
  );

  if (!session && !done) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5]">
      <div className="text-slate-500">Laden…</div>
    </main>
  );

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4 py-8">
      <div className="flex w-full max-w-lg flex-col rounded-lg border border-line bg-white shadow-sm" style={{maxHeight: "90vh"}}>
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
              )}>
                {msg.content}
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
    </main>
  );
}
```

- [ ] **Step 2: Verify the frontend builds**

Run (from `frontend/`):
```bash
npm run build
```
Expected: build succeeds with no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(chat): replace static ChatForm with conversational chat UI"
```

---

### Task 6: End-to-end manual test

**Files:** none (verification only)

- [ ] **Step 1: Start the backend**

Run (from `backend/`):
```bash
PROVIDER_MODE=mock OPENAI_API_KEY=sk-test python -m uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Create a test chat session via the API**

```bash
curl -s http://localhost:8000/health | python -m json.tool
```
Expected: `{"status": "ok", "provider_mode": "mock"}`

Use the login + create-chat flow to get a chat token (or insert a test session directly via Python).

- [ ] **Step 3: Start the frontend**

Run (from `frontend/`):
```bash
npm run dev
```

- [ ] **Step 4: Open the chat in a browser**

Navigate to `http://localhost:5173/?chat={token}` and verify:
- The header shows "Vestigingsregister AI" in teal
- The bot sends an opening message automatically
- User messages appear right-aligned in teal
- Bot messages appear left-aligned in light gray
- Typing indicator shows while waiting for response
- After the conversation completes, a green "Gegevens ontvangen" banner appears
- The privacy footer is visible at the bottom

- [ ] **Step 5: Verify the session was updated**

Check in the database or via the admin API that:
- `ChatSession.status` is `"completed"`
- `ChatSession.antwoorden` contains the collected data
- `ChatSession.messages` contains the full conversation history

- [ ] **Step 6: Run existing tests**

Run (from `backend/`):
```bash
python -m pytest tests/ -q
```
Expected: all existing tests pass.

- [ ] **Step 7: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "chore: post-integration cleanup after chat module manual test"
```
