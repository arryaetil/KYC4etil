"""Herkent waaróm een externe dienst weigert, in dezelfde woorden voor elke dienst.

Serper, OpenAI en Google Places melden een leeg tegoed alle drie anders — de een
met HTTP 400 en een tekst in de body, de ander met 429, de derde met een
`status`-veld in de JSON. Zonder één plek hiervoor krijgt elke dienst zijn eigen
halve variant, en dat is precies hoe "niets gevonden" jarenlang een storing kon
verbergen.
"""
import logging

from ..research.usage import record_dienststoring

logger = logging.getLogger(__name__)

# 400 hoort erbij: Serper meldt een leeg tegoed met
# {"message":"Not enough credits","statusCode":400}, niet met 401/402/403. Een
# guard op statuscodes alléén mist daarom precies het geval waar hij voor is.
_SLEUTEL_OF_TEGOED_STATUS = {400, 401, 402, 403, 429}
_TEGOED_MARKERS = ("credit", "quota", "insufficient", "limit exceeded",
                   "over_query_limit", "billing", "exceeded your current quota")
_SLEUTEL_MARKERS = ("invalid api key", "api key not valid", "request_denied",
                    "unauthorized", "invalid_api_key", "permission denied")

# Voor de reviewer, niet voor de logs: "serper" zegt hem niets.
DIENSTNAMEN = {
    "serper": "Serper (zoekopdrachten)",
    "openai": "OpenAI (tekst lezen en beoordelen)",
    "google_places": "Google Places (websites en vestigingen)",
}


def _body_van(fout: Exception) -> str:
    """Statuscode én body, want alleen samen zeggen ze wat er aan de hand is.

    De statuscode hoort er zichtbaar in te blijven: die is het eerste wat je
    opzoekt als je de melding in de logs terugvindt.
    """
    respons = getattr(fout, "response", None)
    if respons is None:
        return str(fout)
    status = getattr(respons, "status_code", None)
    try:
        body = respons.text[:300]
    except Exception:
        body = ""
    return f"HTTP {status}: {body or fout}".strip()


def classificeer(fout: Exception) -> tuple[str, str]:
    """(reden, detail) — reden is 'tegoed_op', 'sleutel_ongeldig' of 'onbereikbaar'."""
    respons = getattr(fout, "response", None)
    status = getattr(respons, "status_code", None)
    body = _body_van(fout).lower()

    if any(marker in body for marker in _TEGOED_MARKERS):
        return "tegoed_op", _body_van(fout)
    if any(marker in body for marker in _SLEUTEL_MARKERS):
        return "sleutel_ongeldig", _body_van(fout)
    if status in _SLEUTEL_OF_TEGOED_STATUS:
        # Geen herkenbare tekst, wel een status die alleen over sleutel of
        # tegoed gaat. Beter te ruim melden dan stil terugvallen.
        return "sleutel_ongeldig", _body_van(fout)
    return "onbereikbaar", _body_van(fout)


def meld_storing(dienst: str, fout: Exception) -> str:
    """Registreer de storing voor deze run en log hem. Geeft de reden terug."""
    reden, detail = classificeer(fout)
    record_dienststoring(dienst, reden, detail)
    if reden == "onbereikbaar":
        logger.info("%s onbereikbaar: %s", dienst, detail[:200])
    else:
        logger.warning(
            "%s onbruikbaar (%s): %s", dienst, reden, detail[:200],
        )
    return reden
