# Kickoff-prompt voor Claude Code — Fase 2 e.v.

Kopieer onderstaande prompt in Claude Code (gestart in de projectroot):

---

Lees eerst CLAUDE.md en docs/PLATFORM_DOCUMENTATIE_v2.md. Fase 1 (pipeline backend) is af en gevalideerd; bouw nu de volledige applicatie verder. Werk in deze volgorde en commit per afgeronde stap:

**Stap 1 — Auth (backend):**
JWT-login op de bestaande `users`-tabel (passlib/bcrypt), endpoints `/auth/login` en `/auth/me`, seed-script voor twee reviewers (Armina, Anita) en een admin. Beveilig alle bestaande endpoints behalve `/health`. `goedgekeurd_door` vullen vanuit de ingelogde gebruiker bij approve/correct.

**Stap 2 — Achtergrondverwerking:**
`POST /batches/{id}/run` ombouwen naar een achtergrondtaak (FastAPI BackgroundTasks volstaat voor demo-schaal) zodat de frontend voortgang kan pollen via `GET /batches/{id}` (verwerkt/totaal is er al).

**Stap 3 — Review-interface (frontend/, React + Vite + Tailwind):**
Volg documentatie §11. Schermen:
1. Login.
2. Dashboard: batches met voortgang + telling 🟢/🟡/🔴, upload-knop (CSV) en run-knop.
3. Batchoverzicht: tabel van vestigingen, filterbaar op label/strategie, klikbaar.
4. Detailpagina: vestigingsgegevens, gevonden WP + context-citaat, bronlink, score_breakdown visueel per factor (dit is essentieel — reviewers moeten zien wáárom een record 🟡 is), reconciliatie_reden, knoppen Goedkeuren / Corrigeren (met reden) / Bellijst.
5. Bulk: alle 🟢 goedkeuren (endpoint bestaat: `POST /batches/{id}/approve-all-green`), export-knoppen (export.csv, bellijst.csv).
Nederlandstalige UI. API-URL via `VITE_API_URL`. Houd het één SPA zonder zware state-libraries (React Query mag).

**Stap 4 — Railway-deploy:**
railway.toml voor backend (uvicorn, healthcheck /health) en frontend (static build), CORS beperken tot de frontend-origin via env-var, README-sectie met deploy-stappen. PostgreSQL via DATABASE_URL.

**Stap 5 — Live jaarverslag-discovery (backend):**
Implementeer Fase A van de jaarverslag-agent: zoek PDF's via de Brave Search API (key via env BRAVE_API_KEY; abstraheer achter een SearchProvider-protocol met mock, conform de bestaande provider-conventie), filter op recentste relevante PDF, koppel aan bestaande `run_with_pdf()`. Cache opgehaalde PDF's op URL-hash (CB-ers delen één verslag).

**Stap 6 — Chat-module (fase 3, alleen backend + minimale UI):**
Volg documentatie §12. Token-links (gehasht opslaan, 14 dagen geldig), variant 'gericht' (één bevestigingsvraag met pre-fill, pas ná verificatievraag) en 'volledig' (conversational intake van alle WP-velden). Antwoorden naar de review-wachtrij (candidate bijwerken, `verwerkt=TRUE`), nooit direct naar wp_records. Aparte lichtgewicht chat-pagina (mag in dezelfde frontend onder /chat/:token, zonder login).

**Randvoorwaarden:**
- Draai na elke stap `pytest backend/tests/ -q` en `python -m scripts.validate` (vanuit backend/); beide moeten groen blijven.
- Schrijf tests voor nieuwe backend-logica (auth, chat-flow, search-provider).
- Respecteer de domeinregels uit CLAUDE.md (schatting nooit 🟢, FTE ≠ WP, chat altijd via review).
- Vraag mij om input bij de open punten uit CLAUDE.md in plaats van aannames te doen.

Begin met stap 1 en laat me na elke stap kort zien wat er draait.

---
