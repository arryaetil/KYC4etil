# Datamodel, reconciliatie en confidence scoring

> **Actieve bronnenwerkbank:** `ResearchRun` en `BronKandidaat` zijn de actieve
> gegevensstroom. `ResearchRun.onderzoekspaden` bewaart het routeplan en de
> eindstatus per route. `BronKandidaat` bewaart naast bronreview ook
> `bron_relevant`, `bron_volledig_ingelezen`, `wp_oordeel`, `gecorrigeerd_wp`,
> `extractie_reason_code` en `extractie_toelichting`. De oorspronkelijke
> `wp_gevonden` wordt nooit overschreven.

## Datamodel (`backend/app/models.py`)

SQLAlchemy 2 (`Mapped`/`mapped_column`-stijl). Kolomwijzigingen lopen niet via Alembic
maar via `ensure_lightweight_migrations()` in `backend/app/database.py` — een lichtgewicht
"voeg kolom toe als hij nog niet bestaat"-mechanisme, praktisch voor een project met SQLite
lokaal en PostgreSQL op Railway.

| Tabel | Rol |
|---|---|
| **User** | Login-account. Velden: `naam`, `email`, `rol` (default `"reviewer"`), `password_hash`. Geen apart admin-model — rol is gewoon een string. |
| **Batch** | Eén CSV-upload. Status, voortgang, jaar. |
| **Company** | Eén rij uit de geüploade CSV (brondata: naam, adres, gemeente, etc.). |
| **Enrichment** | Verrijkte locatie-/contactdata per company (KvK/Places-resultaat, `website_url`, locatiecounts). |
| **AgentResult** | Eén gevonden bron-resultaat (website, jaarverslag, of extra_bron). Bevat het gevonden WP-getal, het citaat (`wp_context`), bron-URL/type, LLM-zekerheid, en — sinds de bronnen-first-uitbreiding — `identity_class`/`scope_class`. |
| **Candidate** | Het gereconcilieerde eindresultaat per company: `wp_kandidaat`, `confidence_score`, `confidence_label` (🟢/🟡/🔴), `score_breakdown` (JSON met de onderliggende factoren), reviewstatus. |
| **WPRecord** | Historische/definitieve WP-waarden per jaar, met `goedgekeurd_door` — het daadwerkelijke register-record zodra een reviewer heeft goedgekeurd. |
| **PipelineRun** | Logregel per pipelinestap per company (stap-naam, status, tijdsduur, foutmelding). |
| **ChatSession** | Token-based externe chat met een bedrijf (gericht of volledig), voor wanneer automatische verificatie niet lukt. |
| **ChatTemplate** | Herbruikbare vraagsets voor chat-sessies. |
| **CallListItem** | Eén bellijst-item — een bedrijf dat telefonisch benaderd moet worden. |
| **VastgoedRecord** | Vastgoedgegevens per company (aanvullend, niet-WP-gerelateerd). |
| **JaarverslagUpload / JaarverslagChatMessage / JaarverslagMonitoring** | Los subsysteem voor ad-hoc jaarverslaganalyse en doorlopende jaarverslag-monitoring, buiten de hoofdbatchpipeline om. |
| **ResearchRun** | Eén autonome bronnenresearch-opdracht voor een organisatie, met gevraagd jaar, status, zoekbudget, resultaatstatus en foutregistratie. |
| **BronKandidaat** | Gevalideerde en gerangschikte bron voor human review. Bevat identiteit/scope, bewijsfragment, score-uitleg, waarschuwingen en reviewaudit. Per researchrun kan maximaal één kandidaat primair geaccepteerd zijn. |

## Reconciliatie (welke bron wint bij verschil)

Regels, in volgorde:

1. **Eén bron gevonden** (alleen website óf alleen jaarverslag) → die waarde wint direct.
2. **Twee bronnen, verschil ≤10%** → de website-waarde wint (meest vestigingsspecifiek).
3. **Twee bronnen, verschil >10%, locatie-eenduidig** (`count_lb == count_nl`) → de
   website-waarde wint alsnog, maar het verschil wordt gelogd voor transparantie.
4. **Twee bronnen, verschil >10%, meerdere locaties** → het jaarverslag-cijfer gaat naar
   de multi-locatiestrategie (proportionele verdeling over vestigingen) — dit resultaat
   krijgt hoogstens het label 🟡, nooit 🟢, omdat het een schatting is.
5. **Geen van beide bronnen levert iets op** → doorsturen naar volledige chat of bellijst
   (telefonische verificatie).

Identity-/scope-classificatie (zie
[01-pipeline-en-agents.md](01-pipeline-en-agents.md)) speelt in deze reconciliatie geen
rol — het is uitsluitend informatie die de reviewer erbij te zien krijgt.

## Confidence scoring — de formule

Een gewogen som van zes factoren, elk genormaliseerd naar een waarde tussen 0 en 1:

| Factor | Gewicht |
|---|---|
| Locatie-eenduidigheid | 0,30 |
| Data-specificiteit | 0,25 |
| Bronkwaliteit | 0,20 |
| Bronnen-consensus | 0,10 |
| Adresvalidatie | 0,075 |
| Actualiteit | 0,075 |

Na de gewogen som volgen expliciete **penalties**:
- Fuzzy Google Places-match i.p.v. exacte KvK-match: −0,05.
- Proportionele schatting (multi-locatiestrategie): −0,10 tot −0,30.
- Alleen een FTE-cijfer beschikbaar (geen echte WP): −0,10.
- LLM-zekerheid "laag": **cap** op maximaal 0,49 — dit is een begrenzing, geen aftrek; de
  score kan hierdoor nooit hoger uitkomen dan 0,49, maar de cap kan de score ook nooit
  verhogen boven wat de rest van de formule al berekende.

**Labels:**
- 🟢 **hoog** (≥0,80) — automatisch verwerkt, geen reviewer-actie nodig.
- 🟡 **middel** (0,50–0,79) — gerichte chat (specifieke vraag aan het bedrijf).
- 🔴 **laag** (<0,50) — volledige chat of bellijst (telefonische verificatie).

**Absolute regel:** een proportionele schatting (`is_schatting=True`) mag nooit 🟢 krijgen,
ongeacht hoe hoog de rekenkundige score zou uitkomen — dit wordt expliciet afgedwongen,
niet alleen door de penalty-aftrek.

Alle gewichten en drempels staan in `backend/app/config.py`, nooit hardcoded verspreid
in de pipelinecode — en worden na elke validatieronde (`python -m scripts.validate`)
opnieuw tegen het licht gehouden.
