"""Per-run OpenAI-tokenverbruik bijhouden, correct over concurrente
asyncio-taken heen via contextvars (nodig sinds seed-stappen en
bronreview-calls parallel lopen — zie Task 2/3)."""
from contextvars import ContextVar
from dataclasses import dataclass

from ..config import get_settings


@dataclass
class _UsageTotalen:
    tokens_in: int = 0
    tokens_out: int = 0


_huidige_totalen: ContextVar["_UsageTotalen | None"] = ContextVar(
    "_huidige_totalen", default=None,
)


def start_usage_tracking() -> None:
    """Start (of reset) de teller voor de huidige asyncio-context."""
    _huidige_totalen.set(_UsageTotalen())


def record_response_usage(response) -> None:
    """Telt het tokenverbruik van één OpenAI Responses-call op bij de lopende
    tracking. Geen effect zonder actieve tracking (bv. losse scripts) of als
    de response geen bruikbaar usage-veld heeft."""
    totalen = _huidige_totalen.get()
    if totalen is None:
        return
    usage = getattr(response, "usage", None)
    if usage is None:
        return
    totalen.tokens_in += getattr(usage, "input_tokens", None) or 0
    totalen.tokens_out += getattr(usage, "output_tokens", None) or 0


def get_usage_totals() -> tuple[int, int]:
    totalen = _huidige_totalen.get()
    if totalen is None:
        return (0, 0)
    return (totalen.tokens_in, totalen.tokens_out)


def bereken_kosten_cents(tokens_in: int, tokens_out: int) -> int:
    settings = get_settings()
    cents = (
        tokens_in / 1000 * settings.openai_prijs_in_cent_per_1k
        + tokens_out / 1000 * settings.openai_prijs_out_cent_per_1k
    )
    return round(cents)
