"""Eén gegenereerde alinea die zegt wat de gevonden bronnen inhouden.

De werkbank bepaalt zélf hoe hard het bewijs is: de kop en de kleur boven de
bronnenlijst komen uit vaste regels (`onderzoeksadvies` in de frontend). Dat
blijft zo, en met opzet — een model dat "sterk bewijs" schrijft boven één bron
zonder citaat maakt precies de fout die niemand opmerkt tot hij gecontroleerd
wordt, en dat is wat het kaartje moest besparen.

Wat het model hier wél doet is beschrijven: welke bron zegt wat, en waar een
verschil vandaan komt. Dat is het stuk waar regels slecht in zijn. "412 en 380
WP" wordt "het jaarverslag over 2024 noemt 412 medewerkers; een nieuwsbericht
uit 2023 noemt er 380" — dezelfde feiten, maar leesbaar.

De prompt verbiedt uitspraken over hardheid, zodat de tekst nooit iets anders
beweert dan de kop erboven.
"""
import logging

from ..config import get_settings
from .usage import record_provider_call

logger = logging.getLogger(__name__)

# Zonder bronnen valt er niets samen te vatten, en met heel veel bronnen wordt
# de prompt duur zonder dat de reviewer er meer aan heeft: hij leest de eerste
# kaarten. De rest staat gewoon in de lijst.
MAX_BRONNEN_IN_PROMPT = 8


def _regel_per_bron(kandidaat: dict) -> str:
    """Eén bron als platte tekst, met alleen de feiten die ertoe doen."""
    delen = [kandidaat.get("brontype") or "bron"]
    if kandidaat.get("documenttype"):
        delen.append(f"({kandidaat['documenttype']})")
    if kandidaat.get("verslagjaar"):
        delen.append(f"verslagjaar {kandidaat['verslagjaar']}")
    if kandidaat.get("informatie_peilmoment"):
        delen.append(f"peilmoment {kandidaat['informatie_peilmoment']}")
    if kandidaat.get("wp_gevonden") is not None:
        eenheid = {
            "werkzame_personen": "WP",
            "fte": "FTE",
            "onderwijspersoneel_personen": "onderwijspersoneel",
        }.get(kandidaat.get("eenheid"), "personen")
        delen.append(f"— {kandidaat['wp_gevonden']} {eenheid}")
    else:
        delen.append("— geen getal uitgelezen")
    if kandidaat.get("scope_class"):
        delen.append(f"[scope: {kandidaat['scope_class']}]")
    if kandidaat.get("identity_class"):
        delen.append(f"[identiteit: {kandidaat['identity_class']}]")
    regel = " ".join(delen)
    citaat = (kandidaat.get("bewijsfragment") or "").strip()
    if citaat:
        regel += f'\n    citaat: "{citaat[:300]}"'
    return f"- {regel}"


def bronnen_als_tekst(kandidaten: list[dict]) -> str:
    return "\n".join(
        _regel_per_bron(kandidaat)
        for kandidaat in kandidaten[:MAX_BRONNEN_IN_PROMPT]
    )


async def schrijf_samenvatting(
    naam: str,
    peiljaar: int | None,
    kandidaten: list[dict],
) -> str | None:
    """De alinea, of None als er niets te schrijven valt of het misging.

    None is een geldige uitkomst: de frontend valt dan terug op de vaste tekst.
    Een mislukte samenvatting mag een onderzoeksrun nooit tegenhouden — het is
    de buitenste laag, niet het bewijs.
    """
    settings = get_settings()
    if not kandidaten or not settings.openai_api_key:
        return None


    from ..providers import llm
    from ..providers.prompts import BRONSAMENVATTING_PROMPT

    prompt = BRONSAMENVATTING_PROMPT.format(
        naam=naam,
        peiljaar=peiljaar if peiljaar is not None else "onbekend",
        bronnen=bronnen_als_tekst(kandidaten),
    )
    try:
        from ..providers.llm import maak_client

        client = maak_client()
        response = await llm._create_response(
            client,
            model=llm._extraction_model(),
            input=prompt,
            max_output_tokens=400,
            text={"format": {"type": "json_object"}},
        )
        record_provider_call("openai_bronsamenvatting")
        data = await llm._parse_json_met_herstel(
            client, llm._extraction_model(), response.output_text,
        )
    except Exception as exc:
        logger.info("bronsamenvatting mislukt: %s", type(exc).__name__)
        return None

    toelichting = (data or {}).get("toelichting")
    if not isinstance(toelichting, str) or not toelichting.strip():
        return None
    return toelichting.strip()
