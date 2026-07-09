# Kostenoverzicht AI-pipeline

Dit document legt uit **waar de externe-API-kosten van het platform vandaan komen**,
wat de recente wijzigingen (Serper i.p.v. OpenAI `web_search`, extra bronnen,
altijd jaarverslag-agent) daaraan hebben veranderd, en wat een batch-run en de
wekelijkse jaarverslag-monitoring ongeveer kosten.

**Belangrijk voorbehoud:** de bedragen hieronder zijn **modelmatige schattingen**
op basis van huidige prijslijsten (juli 2026) en de code zoals die nu werkt —
géén gemeten telemetrie. `pipeline_runs` logt nu al duur per stap (`duur_ms`),
maar nog geen kosten per stap. Zie [Methodologie & vervolgstappen](#methodologie--vervolgstappen)
voor hoe dit later met echte cijfers te onderbouwen is.

## Welk model draait waar

- **WP-extractie (alle stappen):** `gpt-4o-mini` — $0,15 / 1M input-tokens,
  $0,60 / 1M output-tokens. Dit staat zo op Railway (`OPENAI_MODEL=gpt-4o-mini`)
  en is ruim voldoende voor deze taak (getal + citaat uit tekst halen, JSON
  teruggeven) — een zwaarder model voegt hier weinig toe.
- **Zoeken (website/jaarverslag/contact vinden):** DuckDuckGo (gratis, eerste
  poging) → Serper (~$0,001/query) als DuckDuckGo niets oplevert. Vervangt de
  voorheen gebruikte OpenAI `web_search`-tool ($10/1.000 calls + tokens).
- **Contact/locatie (website, telefoon):** Serper Places (~$0,001/query) als
  primaire bron; Google Places ($32-35/1.000 calls) alleen nog als noodgreep
  voor de landelijke locatie-telling (zie [Waarom Google Places nog gedeeltelijk blijft](#waarom-google-places-nog-gedeeltelijk-blijft)).

## Kosten per pipeline-stap (per bedrijf)

| Stap | Wat gebeurt er | Oud (vóór Serper) | Nieuw (nu) |
|---|---|---|---|
| Verrijking (contact) | Website/telefoon opzoeken | Google Places: $0,032-0,035/call | Serper Places: ~$0,001/call |
| Website-agent | Website doorzoeken + evt. media-fallback | Zoeken via OpenAI `web_search`: ~$0,011/call, plus LLM-extractie ~$0,001-0,003 | Zoeken via Serper: ~$0,001/call, plus LLM-extractie ~$0,001-0,003 |
| Jaarverslag-agent | PDF vinden + WP eruit halen | Draaide alleen als website geen hoog-zekerheid vond; PDF-zoeken via OpenAI `web_search`: ~$0,011-0,022/call (1-2 pogingen) | **Draait nu altijd** (zie hieronder); PDF-zoeken via Serper: ~$0,001-0,002/call |
| PDF-extractie | WP-getal + paginanummer uit PDF | ~$0,001-0,003/call | Ongewijzigd qua kosten; extraheert nu ook het paginanummer voor directe navigatie |
| Extra bronnen (nieuw) | 2 aanvullende publieke bronnen (LinkedIn, KvK, nieuws) | Bestond niet | Zoeken ~$0,001/call + tot 2× extractie ~$0,001-0,003/stuk ≈ **~$0,005/bedrijf** |

**Waarom "altijd jaarverslag-agent" geen doorslaggevende meerkosten geeft:**
de zoekstap is nu bijna gratis (Serper i.p.v. OpenAI `web_search`), dus het
vaker draaien van deze stap kost vooral een beetje extra zoek-tijd, niet veel
extra geld. De grootste kostenpost blijft de LLM-extractie zelf, en die vond al
plaats zodra er een PDF gevonden werd.

## Een batch-run van 20 bedrijven

Uitgaande van een gemiddeld bedrijf dat door de meeste stappen heen loopt
(contact + website + jaarverslag + 2 extra bronnen):

| | Oud (vóór alle wijzigingen) | Nieuw (huidige code) |
|---|---|---|
| Per bedrijf | ~$0,03-0,06 | ~$0,01-0,02 |
| Per batch van 20 | ~$0,60-1,20 | ~$0,20-0,40 |

De besparing zit vooral in de **zoeklaag** (Serper i.p.v. Google Places /
OpenAI `web_search`, ~90%+ goedkoper per call); de LLM-extractiekosten zelf
zijn door de "extra bronnen"-toevoeging licht gestegen, maar dat wordt ruim
overschaduwd door de zoekbesparing.

## Jaarverslag-monitoring (wekelijkse achtergrondtaak)

De monitoring draait automatisch **elke maandag 06:00** (`app/scheduler.py`)
en controleert op dit moment **205 organisaties** (`GET /monitoring`,
peildatum juli 2026) — elk met één `jaarverslag_agent.run()`-aanroep: PDF
zoeken (huidig jaar, zo nodig jaar-1) en, als een PDF gevonden wordt, één
LLM-extractie voor het WP-getal.

| | Oud (OpenAI `web_search`) | Nieuw (Serper) |
|---|---|---|
| Per organisatie | ~$0,012-0,024 (zoeken) + ~$0,0025 (extractie indien PDF gevonden) | ~$0,001-0,002 (zoeken) + ~$0,0025 (extractie indien PDF gevonden) |
| **Per week (205 org.)** | **~$3,00-3,50** | **~$0,60-1,00** |
| **Per maand (~4,3 runs)** | **~$13-15** | **~$2,50-4,50** |
| **Per jaar (52 runs)** | **~$155-180** | **~$30-50** |

Dit is dus een besparing van **ruwweg 75-85% op de jaarlijkse
monitoring-kosten**, en het gaat hier al om een terugkerende taak — elke
extra week die verstrijkt is extra bevestigde besparing.

## Waarom Google Places nog gedeeltelijk blijft

Serper Places is getest tegen de landelijke locatie-telling
(`LivePlacesProvider.locations()`, telt vestigingen NL vs. Limburg voor de
locatie-eenduidigheidsregel) en gaf **0 resultaten** zonder specifieke
plaatsnaam in de zoekopdracht — het gedraagt zich als een lokaal
"in de buurt"-resultaat, niet als een landelijke tekst-zoekopdracht. Voor déze
specifieke stap blijft daarom Google Places nodig ($32-35/1.000 calls), tot de
KvK-koppeling er is (staat al op de openstaande-lijst in `CLAUDE.md` — dat is
sowieso de juiste langetermijnoplossing voor locatietelling, niet Places of
Serper).

Alle overige locatie/contact-opzoekingen (website, telefoon) gebruiken al
Serper Places.

## Methodologie & vervolgstappen

Deze cijfers zijn berekend op basis van:
- Officiële prijslijsten: [OpenAI API pricing](https://platform.openai.com/docs/pricing),
  [Serper pricing](https://serper.dev/), Google Maps Platform pricing.
- Aannames over gemiddelde tekstlengte per LLM-call (~15.000 input-tokens,
  ~400 output-tokens voor een extractiecall — gebaseerd op de
  `tekst[:60000]`-truncatie in `_llm_extract`).
- Aannames over hoe vaak fallback-lagen daadwerkelijk worden aangeroepen
  (DuckDuckGo-slagingspercentage is niet gemeten).

**Om dit later met echte cijfers te onderbouwen:**
1. `pipeline_runs` logt al `duur_ms` per stap — een `kosten_schatting`-kolom
   toevoegen (bijv. op basis van response-tokens uit de OpenAI-respons) zou
   directe, gemeten kosten per stap opleveren i.p.v. een schatting.
2. OpenAI's dashboard (platform.openai.com/usage) en Serper's dashboard geven
   na een paar weken draaien de echte verbruikscijfers — die kunnen dit
   document vervangen door gemeten waarden.

_Laatst bijgewerkt: 9 juli 2026, na de Serper-migratie en de introductie van
extra publieke bronnen voor human-in-the-loop-review._
