"""OpenAI-powered chat service for WP data collection."""
import json
import re

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
- Antwoord ALTIJD als één geldig JSON-object: {"reply": "<uw bericht>", "done": false, "gegevens": {<alle tot nu toe bekende waarden>}}
- Het "gegevens" object bevat ALTIJD alle velden uit het schema, met null voor nog onbekende waarden. Werk het bij na elke beurt.
- Bij de LAATSTE beurt (als de gebruiker het overzicht heeft bevestigd): {"reply": "<afsluitend bericht>", "done": true, "gegevens": {<finale data>}, "antwoorden": {<finale data>}}
- GEEN code fences, GEEN emojis, GEEN tekst buiten het JSON-object.
- Gebruik \\n voor nieuwe regels in de reply-waarde.
- Stel maximaal één groep gerelateerde vragen per beurt (max 3-4 vragen per groep).
- Spreek de gebruiker formeel maar vriendelijk aan (u).
- Houd berichten beknopt.

OPMAAK VAN REPLY-TEKST:
- Herhaal NOOIT een opsomming van de zojuist ingevulde gegevens in je reply. De gebruiker ziet deze al in het overzichtspaneel links. Ga direct door naar de volgende vragen.
- Wanneer je vragen stelt, nummer ze (1. 2. 3.) met elk een eigen regel via \\n.
- Gebruik komma's als scheidingsteken wanneer je meerdere waarden op één regel samenvat."""

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

    pre_fill_wp = ""
    if session.pre_fill_wp:
        pre_fill_wp = f"\nGeschat aantal WP: {session.pre_fill_wp} (bevestig of corrigeer dit met de gebruiker)"

    return f"""Je bent een vriendelijke data-assistent van Etil Research Group.

DOEL: Verzamel personeels- en vastgoedgegevens voor deze vestiging via een natuurlijk gesprek. Groepeer gerelateerde vragen. Bevestig wat al bekend is — vraag het niet opnieuw.

Open het gesprek met: u bent benaderd door Etil Research Group, in opdracht van Provincie Limburg, voor het jaarlijkse Vestigingsregister. De antwoorden worden door een medewerker gecontroleerd voordat ze worden verwerkt. Vraag eerst bevestiging van de bedrijfsnaam.

BEKENDE GEGEVENS (bevestig, niet opnieuw vragen):
{bekende_info}{pre_fill_wp}

VERPLICHTE VELDEN (deze MOETEN allemaal worden uitgevraagd):
- Personeel: wp_totaal, eigen_personeel, uitzend, detachering, wsw, man, vrouw, voltijd, deeltijd, pct_op_locatie
- Vastgoed: adres, perceeloppervlakte, winkeloppervlakte, kantooroppervlakte, bedrijfsvloeroppervlakte

OPTIONELE VELDEN (vraag ernaar maar accepteer als de gebruiker het niet weet):
- correspondentieadres, uitbreidingsruimte, seizoensverschil, opmerking

GESPREKSVERLOOP (groepeer in ~5-6 beurten):
1. Begroeting + transparantie (wie, waarvoor, review). Bevestig bekende gegevens (adres, bedrijfsnaam).
2. WP totaal + uitsplitsing: eigen personeel, uitzendkrachten, detachering, WSW.
3. Man/vrouw, voltijd/deeltijd, percentage werkzaam op locatie (≥60% van de tijd).
4. Oppervlaktes: perceel, winkel, kantoor, bedrijfsvloer. Uitbreidingsruimte. Vraag of het correspondentieadres hetzelfde is als het vestigingsadres; zo niet, vraag het correspondentieadres.
5. Seizoensverschillen en eventuele opmerkingen.
6. BEVESTIGINGSSTAP: Toon GEEN overzicht van gegevens in de chat. Verwijs alleen naar het overzichtspaneel links: "Controleer het overzicht hiernaast. Klopt alles? Zo ja, dan sla ik het op."
7. Als de gebruiker "ja" zegt: bedank en sluit af met done: true. Als "nee": corrigeer en vraag opnieuw.

BELANGRIJK:
- Sla geen verplicht veld over. Als de gebruiker een veld niet weet, noteer null en ga door.
- Als er een geschat WP-getal is, presenteer dit en vraag of het klopt.
- Zet null voor onbekende velden in het gegevens/antwoorden-object.
- Als de gebruiker zegt dat iets niet van toepassing is, er geen is, of "nee" antwoordt (bijv. geen uitbreidingsruimte, geen seizoensverschil, geen opmerkingen), zet dan "/" als waarde in het gegevens-object — NIET null. Null betekent "nog niet gevraagd", "/" betekent "niet van toepassing".
- Als het correspondentieadres hetzelfde is als het vestigingsadres, zet dan "Zelfde als vestigingsadres" als waarde.

GEGEVENS-SCHEMA (gebruik dit voor het "gegevens" object in elke beurt EN voor "antwoorden" bij de laatste beurt):
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
        max_tokens=900,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_text}] + messages,
    )

    raw = response.choices[0].message.content.strip()
    parsed = _parse_response(raw)

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
