"""Valideert agent-gevonden WP-uitsplitsingen vóór vastlegging als WPRecord."""
from ..models import AgentResult

_GROEPEN = {
    "geslacht": ("man", "vrouw"),
    "dienstverband": ("voltijd", "deeltijd"),
    "type_personeel": ("eigen_personeel", "uitzend", "detachering", "wsw"),
}


def valideer_wp_uitsplitsing(ar: AgentResult | None, wp: int) -> dict:
    """Neem alleen complete groepen over waarvan de som exact gelijk is aan wp."""
    resultaat: dict = {}
    if ar is None:
        return resultaat

    for velden in _GROEPEN.values():
        waarden = [getattr(ar, veld) for veld in velden]
        if any(waarde is None for waarde in waarden):
            continue
        if sum(waarden) != wp:
            continue
        for veld, waarde in zip(velden, waarden):
            resultaat[veld] = waarde

    if ar.pct_op_locatie is not None:
        resultaat["pct_op_locatie"] = ar.pct_op_locatie

    return resultaat
