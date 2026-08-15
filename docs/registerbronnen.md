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

**Vindplaats.** `duo.nl/open_onderwijsdata`. De actieve koppeling leest de
officiële maandelijkse adresbestanden en jaarlijkse personeelsbestanden voor
PO, VO en MBO rechtstreeks in, zonder API-sleutel.

**Wat er in zit.** Onderwijspersoneel per bevoegd gezag en per instellingscode
(BRIN), zowel in fte als in **aantal personen**. De bronnenwerkbank gebruikt
uitsluitend het personenbestand. Peildatum 1 oktober, publicatie in april
daarna. Historie 2011–2025. Voor po ook man/vrouw, leeftijd en vast/tijdelijk.
Let op: de totalen tussen tabbladen verschillen door weegfactoren die corrigeren
voor instellingen die niet volledig aanleveren.

**Wat er níet in zit.** Geen uitsplitsing per vestiging — alleen bevoegd gezag en
instelling.

**Mismatch met ons register.** DUO-personen zijn niet automatisch hetzelfde als
WP: onder meer gastdocenten, stagiairs, uitzendkrachten en vervangers kunnen
buiten de DUO-definitie vallen. Bovendien is instelling/bestuur niet altijd een
vestiging. Daarom bewaart de koppeling de eenheid als
`onderwijspersoneel_personen` en toont de UI een expliciete waarschuwing.

**Actieve toepassing.** Naam, gemeente en adres worden aan de DUO-adresrij en
instellingscode gekoppeld. Bij één instelling wordt het personengetal als
controleerbare bron voorgesteld. Bij een groep met meerdere instellingscodes
worden de deelwaarden getoond maar niet opgeteld, omdat dezelfde persoon bij
meerdere instellingen kan voorkomen. Hoger onderwijs heeft in deze eerste
versie geen vergelijkbaar direct personeelsbestand.

## Openstaand

- Of een structurele BRIN/RIO-code aan de aangeleverde registerdata kan worden
  toegevoegd. Dat zou de huidige conservatieve naam-/gemeente-/adresmatch verder
  versterken.
- Of de niet-openbare personeelsaantallen uit DigiMV op aanvraag beschikbaar zijn.
  Eén bron meldde dat personeelsinformatie alleen na toetsing door
  brancheorganisaties vrijkomt; dat is niet op de primaire pagina's bevestigd.
