# Automatische WP-uitsplitsing-extractie — design

## Aanleiding

Sinds de jaarverslag-monitoring-dashboard-feature (§ vorige spec) is er een
klikbare doorverwijzing van een gemonitorde organisatie naar het bestaande
detailscherm. Die doorverwijzing bestond al en werkt correct — geen wijziging
nodig. Wel viel op dat het detailscherm een "WP-uitsplitsing"-kaart toont
(man/vrouw, voltijd/deeltijd, type personeel, % op locatie — de
"Kerndata (WP)" uit `PLATFORM_DOCUMENTATIE_v2.md` §2) die vandaag **uitsluitend
handmatig** gevuld wordt: via de chat-correctieflow (`chat_admin.py`) waarbij
een CO'er zelf een chatformulier invult. Geen enkele agent probeert deze
uitsplitsing automatisch uit de brontekst te halen — alleen het WP-totaal
(`wp_gevonden`) wordt automatisch geëxtraheerd.

Dit document beschrijft hoe de jaarverslag-agent deze uitsplitsing voortaan
ook automatisch mag proberen te vinden, met behoud van de bestaande
kwaliteitswaarborgen (optioneel, nooit een gok, nooit stilzwijgend inconsistente
cijfers in het register).

## Scope

**Wel:**
- De jaarverslag-agent (`LiveJaarverslagAgent` + `MockJaarverslagAgent`)
  probeert voortaan ook de 8 uitsplitsingsvelden te vinden die al bestaan op
  `WPRecord`: `eigen_personeel`, `uitzend`, `detachering`, `wsw`, `man`,
  `vrouw`, `voltijd`, `deeltijd`, `pct_op_locatie`. Elk veld is optioneel —
  alleen invullen als het expliciet in de brontekst staat.
- Deze uitbreiding zit in de agent zelf, dus geldt zowel tijdens normale
  batch-verwerking (`runner.py`) als tijdens jaarverslag-monitoring
  (`monitoring.py`) — één implementatie, geen aparte logica per context.
- De gevonden uitsplitsing wordt zichtbaar in het detailscherm vóórdat een
  reviewer de WP-kandidaat goedkeurt, als niet-bindende context.
- Bij goedkeuren van de kandidaat wordt de uitsplitsing (mits intern
  consistent — zie Validatie) automatisch overgenomen in het nieuw
  aangemaakte `WPRecord`, in plaats van dat een reviewer die zelf via chat
  moet natypen.

**Niet:**
- De website-agent extraheert deze velden niet — alleen de jaarverslag-agent.
- Geen reconciliatie tussen bronnen voor de uitsplitsing: alleen de
  uitsplitsing van de uiteindelijk gekozen (`gekozen_agent_result`)
  AgentResult wordt ooit getoond of gebruikt. Als de jaarverslag-agent wel
  een uitsplitsing vond maar de website-agent de reconciliatie won, wordt de
  jaarverslag-uitsplitsing niet getoond.
- Geen nieuwe review-status specifiek voor de uitsplitsing — die deelt het
  bestaande goedkeurmoment van de WP-kandidaat.
- De chat-correctieflow (`chat_admin.py`) blijft ongewijzigd: nog steeds een
  volledig handmatig, onafhankelijk pad.
- Geen wijziging aan de confidence-formule (§9) — de uitsplitsing is zuiver
  aanvullende informatie en beïnvloedt de WP-confidence-score niet.

## Datamodel & extractie

`AgentFinding` (in `app/providers/base.py`, gedeeld door beide agents) krijgt
8 nieuwe optionele velden, met dezelfde naam en type als de al bestaande
`WPRecord`-kolommen: `eigen_personeel: int | None`, `uitzend: int | None`,
`detachering: int | None`, `wsw: int | None`, `man: int | None`,
`vrouw: int | None`, `voltijd: int | None`, `deeltijd: int | None`,
`pct_op_locatie: float | None`. Alle default `None`.

`AgentResult` (in `app/models.py`) krijgt dezelfde 8 kolommen, eveneens
nullable, zelfde types als op `WPRecord`.

Alleen `LiveJaarverslagAgent`'s extractieprompt wordt uitgebreid om deze
velden te proberen vinden (analoog aan hoe `wp_gevonden` nu al optioneel is:
"vul alleen in als het expliciet vermeld staat, anders `null`"). De
website-agent-prompt en -logica blijven ongewijzigd — deze velden blijven
`None` op elke `AgentFinding` die van de website-agent komt.

`MockJaarverslagAgent` krijgt voor een deel van de 20 testbedrijven
(`data/mock_data.json`) een ingevulde uitsplitsing, en voor de rest bewust
geen — zodat zowel het "gevonden"- als het "niet gevonden"-pad testbaar
blijven.

## Opslag- en validatieflow

Zowel `runner.py` (normale batch-verwerking, de gedeelde lus die
`AgentResult` bouwt uit `w_finding`/`j_finding`) als `monitoring.py`'s
`check_company_jaarverslag` krijgen dezelfde, additieve regel: de 8 nieuwe
velden worden 1-op-1 overgenomen van `finding` naar de nieuwe `AgentResult`,
ongefilterd — net zoals `raw_output` nu al de ruwe LLM-output bewaart zonder
validatie. Dit bewaart het signaal ook als het (nog) niet klopt, voor
debugging/audit.

Validatie gebeurt pas bij het promoveren naar een officieel `WPRecord`, dus
in `_maak_wp_record()` (`app/routers/review.py`), op het moment dat een
reviewer de WP-kandidaat goedkeurt. Een nieuwe, kleine module
`app/pipeline/wp_uitsplitsing.py` krijgt een functie
`valideer_wp_uitsplitsing(ar: AgentResult, wp: int) -> dict` die de drie
optelbare groepen los van elkaar beoordeelt:

- **Geslacht:** `man` + `vrouw`
- **Dienstverband:** `voltijd` + `deeltijd`
- **Type personeel:** `eigen_personeel` + `uitzend` + `detachering` + `wsw`

Een groep wordt alleen overgenomen als **alle** velden binnen die groep
ingevuld zijn (geen `None`) én de som exact gelijk is aan `wp` (het
goedgekeurde WP-totaal). Klopt de som niet, of ontbreekt een deel van de
groep, dan wordt de hele groep genegeerd (blijft `None` op het nieuwe
`WPRecord`) — de andere groepen worden onafhankelijk beoordeeld. `pct_op_locatie`
heeft geen som om te controleren en wordt 1-op-1 overgenomen als het aanwezig
is. Dit voorkomt dat een verkeerd gelezen jaarverslag stilzwijgend
inconsistente cijfers in het register zet, terwijl het wel toestaat dat losse,
correcte groepen alsnog automatisch worden overgenomen.

`_maak_wp_record()` roept deze functie aan met de `AgentResult` die bij
`cand.gekozen_agent_result` hoort (dezelfde die het al gebruikt voor
`bron_type`/`bron_url`) en vult het resultaat in op het nieuwe `WPRecord`, in
plaats van dat alle 8 velden standaard `None` blijven zoals nu.

## API & frontend

Geen nieuw endpoint. `GET /batches/{batch_id}/companies/{company_id}`
(`app/routers/batches.py`, `company_detail`) breidt de bestaande
`agent_results[]`-serialisatie uit met de 8 nieuwe velden.

`frontend/src/components/detail/WpUitsplitsing.jsx` breidt de bestaande
"nog geen WP-record"-tak uit: als er onder `agent_results` een
`agent_type: "jaarverslag"`-resultaat zit met minstens één ingevuld
uitsplitsingsveld, toont het scherm die waarden als niet-bindende
"agent-suggestie, nog niet bevestigd" (hergebruik van de bestaande
`WP_SPLITS_VELDEN`-labels), in plaats van alleen de huidige, kale
waarschuwing. Na goedkeuring is het `WPRecord` al voorgevuld met de
gevalideerde agent-data, dus de bestaande bewerk-/correctieflow in dit
component heeft geen wijziging nodig — een reviewer corrigeert daar simpelweg
als de agent iets verkeerd las of een groep is genegeerd wegens een
kloppende-som-mismatch.

## Domeinregels die van toepassing blijven

- FTE ≠ WP: blijft ongewijzigd, de uitsplitsing gaat over WP, niet over FTE.
- Chat-antwoorden gaan altijd via de review-wachtrij: niet van toepassing
  hier, dit raakt de chat-flow niet.
- LLM-zekerheid mag een confidence-score alleen begrenzen, nooit verhogen:
  niet van toepassing, de uitsplitsing beïnvloedt de confidence-score
  helemaal niet (zie Scope, "Niet").
