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

_PRIVACY_OPENING = (
    "Open het gesprek met: u bent benaderd door Etil Research Group, in opdracht van "
    "Provincie Limburg, voor het jaarlijkse Vestigingsregister. De antwoorden worden "
    "door een medewerker gecontroleerd voordat ze worden verwerkt. "
    "Vraag eerst bevestiging van de bedrijfsnaam en de rol/functie van de invuller."
)


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
4. Bedank en sluit af met done: true.

Bij de laatste beurt, voeg een "antwoorden" object toe met:
{{"wp_totaal": <bevestigd of gecorrigeerd getal>, "opmerking": <toelichting of null>}}

{_FORMAT_RULES}"""

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
