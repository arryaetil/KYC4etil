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

    # Truncated JSON: extraheer reply-veld via regex (ook zonder sluitende })
    m = re.search(r'"reply"\s*:\s*"(.*?)(?<!\\)"', raw, re.DOTALL)
    if m:
        reply = m.group(1).replace('\\n', '\n').replace('\\"', '"')
        done = bool(re.search(r'"done"\s*:\s*true', raw))
        return {"reply": reply, "done": done}

    # Laatste redmiddel: toon generieke foutmelding i.p.v. rauwe JSON
    return {"reply": "Er ging iets mis. Probeer het opnieuw.", "done": False}


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

# Standaard veldconfiguratie — True = aan, False = uit
_DEFAULT_VELD_CONFIG: dict[str, bool] = {
    "wp_totaal": True,
    "eigen_personeel": True,
    "uitzend": True,
    "detachering": True,
    "wsw": True,
    "man": True,
    "vrouw": True,
    "voltijd": True,
    "deeltijd": True,
    "pct_op_locatie": True,
    "adres": True,
    "correspondentieadres": True,
    "perceeloppervlakte": True,
    "winkeloppervlakte": True,
    "kantooroppervlakte": True,
    "bedrijfsvloeroppervlakte": True,
    "uitbreidingsruimte": True,
    "seizoensverschil": True,
    "opmerking": True,
}

_VELD_LABELS: dict[str, str] = {
    "wp_totaal": "wp_totaal (totaal werkzame personen, headcount)",
    "eigen_personeel": "eigen_personeel (eigen personeel in loondienst)",
    "uitzend": "uitzend (uitzendkrachten)",
    "detachering": "detachering (gedetacheerden)",
    "wsw": "wsw (WSW-personeel)",
    "man": "man (aantal mannen)",
    "vrouw": "vrouw (aantal vrouwen)",
    "voltijd": "voltijd (voltijdwerkers)",
    "deeltijd": "deeltijd (deeltijdwerkers)",
    "pct_op_locatie": "pct_op_locatie (% werkzaam op dit vestigingsadres)",
    "adres": "adres (vestigingsadres inclusief huisnummer)",
    "correspondentieadres": "correspondentieadres",
    "perceeloppervlakte": "perceeloppervlakte in m²",
    "winkeloppervlakte": "winkeloppervlakte in m²",
    "kantooroppervlakte": "kantooroppervlakte in m²",
    "bedrijfsvloeroppervlakte": "bedrijfsvloeroppervlakte in m²",
    "uitbreidingsruimte": "uitbreidingsruimte (ja/nee/niet van toepassing)",
    "seizoensverschil": "seizoensverschil (ja/nee — pieken/dalen in personeelsbezetting)",
    "opmerking": "opmerking (vrije toelichting)",
}


def _effective_veld_config(template_config: dict | None) -> dict[str, bool]:
    """Samenvoegen van standaard config met eventuele template-overrides."""
    cfg = dict(_DEFAULT_VELD_CONFIG)
    if template_config and isinstance(template_config.get("veld_config"), dict):
        for k, v in template_config["veld_config"].items():
            if k in cfg:
                if isinstance(v, bool):
                    cfg[k] = v
                elif v == "skip":
                    cfg[k] = False
                else:
                    cfg[k] = True  # "verplicht" of "optioneel" (oud formaat)
    return cfg


def _build_system_prompt(session: ChatSession, company: Company,
                         enrichment: Enrichment | None,
                         template_config: dict | None = None) -> str:
    veld_cfg = _effective_veld_config(template_config)
    actief = [k for k in _DEFAULT_VELD_CONFIG if veld_cfg.get(k)]

    extra_vragen: list[str] = (template_config or {}).get("extra_vragen") or []
    intro_tekst: str = (template_config or {}).get("intro_tekst") or ""

    def veld_str(keys: list[str]) -> str:
        return "\n".join(f"- {_VELD_LABELS.get(k, k)}" for k in keys)

    actief_str = veld_str(actief) if actief else "— geen velden actief —"

    extra_vragen_blok = ""
    if extra_vragen:
        regels = "\n".join(f"- {v} (sla op als extra_{i})" for i, v in enumerate(extra_vragen, 1))
        extra_vragen_blok = f"\nEXTRA VRAGEN (stel deze in BEURT 5, aanvullend op de standaardvragen):\n{regels}\n"

    # Dynamisch antwoorden-schema — alleen actieve velden
    schema_lines = [f'  "{k}": <getal of null>' if k not in (
        "adres", "correspondentieadres", "uitbreidingsruimte", "seizoensverschil", "opmerking"
    ) else f'  "{k}": <tekst of null>' for k in actief]
    for i, _ in enumerate(extra_vragen, 1):
        schema_lines.append(f'  "extra_{i}": <tekst of null>')
    schema = "{\n" + ",\n".join(schema_lines) + "\n}"

    # Rekenregels — alleen als relevante velden actief zijn
    rekenregels: list[str] = []
    if "wp_totaal" in actief:
        if all(k in actief for k in ["eigen_personeel", "uitzend", "detachering", "wsw"]):
            rekenregels.append("- eigen_personeel + uitzend + detachering + wsw MOET gelijk zijn aan wp_totaal.")
        if "man" in actief and "vrouw" in actief:
            rekenregels.append("- man + vrouw MOET gelijk zijn aan wp_totaal.")
        if "voltijd" in actief and "deeltijd" in actief:
            rekenregels.append("- voltijd + deeltijd MOET gelijk zijn aan wp_totaal.")
    rekenregels_str = "\n".join(rekenregels) if rekenregels else "Geen rekencontroles van toepassing."

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

    opening = intro_tekst if intro_tekst else (
        "u bent benaderd door Etil Research Group, in opdracht van Provincie Limburg, voor het "
        "jaarlijkse Vestigingsregister. De antwoorden worden door een medewerker gecontroleerd "
        "voordat ze worden verwerkt. Vraag eerst bevestiging van de bedrijfsnaam."
    )

    heeft_vastgoed = any(k in actief for k in [
        "perceeloppervlakte", "winkeloppervlakte", "kantooroppervlakte", "bedrijfsvloeroppervlakte",
    ])
    beurt4 = (
        "BEURT 4: Meld dat de gebruiker het formulier kan gebruiken om de oppervlaktes in te vullen "
        "(perceel, winkel, kantoor, bedrijfsvloer in m², voor zover van toepassing) en of er "
        "uitbreidingsruimte is. Wacht op het antwoord via het formulier."
        if heeft_vastgoed else
        "BEURT 4: Sla deze beurt over (geen vastgoedvelden actief in dit template)."
    )

    return f"""Je bent een vriendelijke data-assistent van Etil Research Group.

DOEL: Verzamel de gevraagde gegevens voor deze vestiging via een natuurlijk gesprek. Groepeer gerelateerde vragen. Bevestig wat al bekend is — vraag het niet opnieuw.

Open het gesprek met: {opening}

BEKENDE GEGEVENS (bevestig, niet opnieuw vragen):
{bekende_info}{pre_fill_wp}

UIT TE VRAGEN VELDEN:
{actief_str}
{extra_vragen_blok}
GESPREKSVERLOOP (volg deze beurten EXACT in deze volgorde):
BEURT 1: Begroeting + transparantie (wie, waarvoor, review). Bevestig ALLE bekende gegevens met de gebruiker (bedrijfsnaam, adres, eventueel geschat WP-getal). Vraag bevestiging.
BEURT 2: Vraag het totaal aantal werkzame personen (wp_totaal). Meld dat de gebruiker het invoerformulier kan gebruiken om de uitsplitsingen in te vullen (dienstverband, geslacht, arbeidsduur, % op locatie). Wacht op de antwoorden van de gebruiker — deze komen via het formulier per groep.
BEURT 3: Vraag ALLEEN of het correspondentieadres hetzelfde is als het vestigingsadres. Stel GEEN andere vragen in deze beurt. De gebruiker beantwoordt dit via knoppen. Wacht op het antwoord.
{beurt4}
BEURT 5: Vraag naar seizoensverschillen en eventuele opmerkingen.{" Stel daarna ook de extra vragen." if extra_vragen else ""}
BEURT 6: BEVESTIGINGSSTAP — Toon GEEN overzicht van gegevens in de chat. Verwijs alleen naar het overzichtspaneel: "Controleer het overzicht hiernaast. Klopt alles? Zo ja, dan sla ik het op."
BEURT 7: Als de gebruiker "ja" zegt: bedank en sluit af met done: true. Als "nee": corrigeer en vraag opnieuw.

REKENREGELS PERSONEEL:
{rekenregels_str}
Als de som niet klopt, wijs de gebruiker hierop en vraag om correctie. Als de som WEL klopt, accepteer de verdeling altijd — ook als de verhouding ongewoon lijkt (bijv. 100 voltijds op 1400 deeltijds). Geef nooit commentaar op de verdeling zolang de som overeenkomt.

BELANGRIJK:
- Sla geen veld over. Als de gebruiker een veld niet weet, noteer null en ga door.
- Als er een geschat WP-getal is, presenteer dit en vraag of het klopt.
- Zet null voor onbekende velden in het gegevens/antwoorden-object.
- Als de gebruiker zegt dat iets niet van toepassing is, of "nee" antwoordt (bijv. geen uitbreidingsruimte, geen seizoensverschil), zet dan "/" als waarde — NIET null. Null = nog niet gevraagd, "/" = niet van toepassing.
- Als het correspondentieadres hetzelfde is als het vestigingsadres, zet dan "Zelfde als vestigingsadres" als waarde.

GEGEVENS-SCHEMA (gebruik dit voor "gegevens" in elke beurt EN voor "antwoorden" bij de laatste beurt):
{schema}

{_FORMAT_RULES}"""


async def get_chat_reply(messages: list[dict], session: ChatSession,
                         company: Company,
                         enrichment: Enrichment | None) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        return {"reply": "De chatservice is momenteel niet beschikbaar. "
                         "Neem contact op met Etil Research Group.", "done": False}

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    template_config = session.vragen if isinstance(session.vragen, dict) else None
    system_text = _build_system_prompt(session, company, enrichment, template_config)

    response = await client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=1500,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system_text}] + messages,
    )

    raw = response.choices[0].message.content.strip()
    parsed = _parse_response(raw)

    gegevens = parsed.get("gegevens")
    antwoorden = parsed.get("antwoorden")
    if not antwoorden and parsed.get("done") and gegevens:
        antwoorden = gegevens

    reply = parsed.get("reply") or ""
    if not reply.strip() or reply.strip() in ("{}", "null"):
        reply = "Bedankt voor uw antwoord. We gaan verder."

    return {
        "reply": reply,
        "done": bool(parsed.get("done", False)),
        "antwoorden": antwoorden,
        "gegevens": gegevens,
    }
