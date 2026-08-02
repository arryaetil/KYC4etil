# Registerbronnen naast websearch

Onderzocht op 2026-08-02. Twee sectorregisters die WP-achtige data publiceren
zonder zoekopdrachten. Beide zijn **geen vervanging** voor de jaarverslagagent,
maar ze lossen elk een ander deelprobleem op.

## Jaarverantwoording Zorg (DigiMV, CIBG)

Zorgaanbieders zijn onder de WTZa verplicht jaarlijks verantwoording af te leggen.
De openbare dataset is te downloaden zonder sleutel of account.

**Vindplaats.** `jaarverantwoordingzorg.nl/gegevens-bekijken/verantwoordingsgegevens-per-verslagjaar-datasets`
verwijst per verslagjaar naar documentpagina's; het feitelijke bestand staat onder
`/site/binaries/site-content/collections/documents/<jaar>/<maand>/<dag>/dataset-<jaar>---deel-<n>/`.
Verslagjaar 2024 staat in **vier .ods-bestanden** van elk ±24 MB (uitgepakt ±1,5 GB
XML per deel), gepubliceerd 23 maart 2026.

**Actualiteit.** 2024 is het nieuwste beschikbare verslagjaar. Er komt pas rond
maart 2027 een dataset over 2025. Voor zorginstellingen is een bron met
verslagjaar 2024 dus correct het meest recente dat bestaat — geen misser.

**Wat er in zit.** 14.658 variabelen per organisatie. Relevant voor ons:

| Variabele | Waarom bruikbaar |
|---|---|
| `KvkNummer` | directe koppelsleutel op `companies.kvk_nummer` |
| `Vestigingnummers (zoals geregistreerd)` | koppelsleutel op vestigingsniveau |
| `Naam van de organisatie` | identiteitscontrole |
| Straatnaam, postcode, plaatsnaam | adresvalidatie |

**Wat er níet in zit.** Personeel staat uitsluitend als **kosten in euro's**
(lonen, sociale lasten, pensioenpremies, inhuur), niet als aantal personen of fte.
Ook ontbreekt een link naar het jaarverslag-PDF. De dataset levert dus **geen
WP-getal en geen bron-URL**.

**Conclusie.** Waardevol als identiteits- en vestigingskoppeling — het is de enige
bron die we tegenkwamen met KvK-nummer én vestigingsnummers naast elkaar — maar
het vervangt de jaarverslagagent niet.

## DUO Open Onderwijsdata

**Vindplaats.** `duo.nl/open_onderwijsdata`, plus een open REST/JSON-LD API op
`api.duo.nl` zonder sleutel, doorzoekbaar op onder meer `brin`, `bevoegd_gezag`,
`instellingsnaam`, `vestigingsnaam`, `vestigingsnummer` en `gemeentenaam`.

**Wat er in zit.** Onderwijspersoneel per bevoegd gezag en per instellingscode
(BRIN), in **fte** — nooit in aantal personen. Peildatum 1 oktober, publicatie in
april daarna. Historie 2011–2025. Voor po ook man/vrouw, leeftijd en vast/tijdelijk.
Let op: de totalen tussen tabbladen verschillen door weegfactoren die corrigeren
voor instellingen die niet volledig aanleveren.

**Wat er níet in zit.** Geen uitsplitsing per vestiging — alleen bevoegd gezag en
instelling.

**Twee mismatches met ons register.** fte is geen WP (harde domeinregel: nooit
stilzwijgend omrekenen), en instelling/bestuur is geen vestiging. Van "fte bij
bestuur X" naar "wp bij vestiging Y" vergt zowel omrekenen als proportioneel
verdelen — twee lagen benadering op elkaar, en dat mag volgens de domeinregels
nooit 🟢 worden.

**Conclusie.** Als bron om aan een reviewer te tónen is DUO prima: gezaghebbend,
gratis en zonder sleutel. Als automatische WP-bron niet. De sterkste toepassing is
de **vestigingstelling voor onderwijs**: via de API is exact vast te stellen welke
vestigingen onder een bestuur vallen en hoeveel daarvan in Limburg liggen — precies
waar `locations()` nu 3,2 ct per organisatie voor betaalt aan Google Places, met
een telling die op 20 wordt afgekapt.

## Openstaand

- Of DUO's `vestigingsnummer` (RIO) hetzelfde is als het vestigingsnummer in ons
  register. Zo niet, dan moet de koppeling via adres/postcode en is die
  foutgevoelig.
- Of de niet-openbare personeelsaantallen uit DigiMV op aanvraag beschikbaar zijn.
  Eén bron meldde dat personeelsinformatie alleen na toetsing door
  brancheorganisaties vrijkomt; dat is niet op de primaire pagina's bevestigd.
