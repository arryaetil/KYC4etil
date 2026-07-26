"""Per-run OpenAI-tokenverbruik bijhouden, correct over concurrente
asyncio-taken heen via contextvars (nodig sinds seed-stappen en
bronreview-calls parallel lopen — zie Task 2/3)."""
from contextvars import ContextVar
from dataclasses import dataclass, field

from ..config import get_settings


@dataclass
class _UsageTotalen:
    tokens_in: int = 0
    tokens_out: int = 0
    provider_calls: dict[str, int] = field(default_factory=dict)
    provider_kosten_micro_usd: dict[str, int] = field(default_factory=dict)


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
    record_provider_call("openai_tokens")
    usage = getattr(response, "usage", None)
    if usage is not None:
        totalen.tokens_in += getattr(usage, "input_tokens", None) or 0
        totalen.tokens_out += getattr(usage, "output_tokens", None) or 0
    dump = getattr(response, "model_dump", None)
    if callable(dump):
        output = dump().get("output") or []
        for item in output:
            if item.get("type") == "web_search_call":
                record_provider_call(
                    "openai_web_search", kosten_micro_usd=10_000,
                )


def record_provider_call(
    provider: str,
    *,
    kosten_micro_usd: int = 0,
) -> None:
    """Registreer één externe call; microdollars voorkomen afrondingsverlies."""
    totalen = _huidige_totalen.get()
    if totalen is None:
        return
    totalen.provider_calls[provider] = totalen.provider_calls.get(provider, 0) + 1
    totalen.provider_kosten_micro_usd[provider] = (
        totalen.provider_kosten_micro_usd.get(provider, 0)
        + kosten_micro_usd
    )


def get_usage_totals() -> tuple[int, int]:
    totalen = _huidige_totalen.get()
    if totalen is None:
        return (0, 0)
    return (totalen.tokens_in, totalen.tokens_out)


def get_cost_summary() -> dict:
    totalen = _huidige_totalen.get() or _UsageTotalen()
    settings = get_settings()
    openai_micro_usd = round((
        totalen.tokens_in / 1000 * settings.openai_prijs_in_cent_per_1k
        + totalen.tokens_out / 1000 * settings.openai_prijs_out_cent_per_1k
    ) / 100 * 1_000_000)
    provider_kosten = {
        **totalen.provider_kosten_micro_usd,
        "openai_tokens": openai_micro_usd,
    }
    totaal_micro_usd = sum(provider_kosten.values())
    providers = {
        naam: {
            "calls": totalen.provider_calls.get(naam, 0),
            "kosten_usd": round(kosten / 1_000_000, 6),
        }
        for naam, kosten in sorted(provider_kosten.items())
    }
    return {
        "currency": "USD",
        "tokens_in": totalen.tokens_in,
        "tokens_out": totalen.tokens_out,
        "providers": providers,
        "totaal_usd": round(totaal_micro_usd / 1_000_000, 6),
        "totaal_cents": round(totaal_micro_usd / 10_000),
    }


def bereken_kosten_cents(tokens_in: int, tokens_out: int) -> int:
    settings = get_settings()
    cents = (
        tokens_in / 1000 * settings.openai_prijs_in_cent_per_1k
        + tokens_out / 1000 * settings.openai_prijs_out_cent_per_1k
    )
    return round(cents)
