"""Per-run providerverbruik bijhouden, correct over concurrente
asyncio-taken heen via contextvars (nodig sinds seed-stappen en
bronreview-calls parallel lopen — zie Task 2/3)."""
import asyncio
from copy import deepcopy
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

from ..config import get_settings


@dataclass
class _UsageTotalen:
    tokens_in: int = 0
    tokens_out: int = 0
    provider_calls: dict[str, int] = field(default_factory=dict)
    provider_kosten_micro_usd: dict[str, int] = field(default_factory=dict)
    provider_responses: dict[tuple, object] = field(default_factory=dict)
    provider_inflight: dict[tuple, asyncio.Task] = field(default_factory=dict)
    dienststoringen: dict[str, dict] = field(default_factory=dict)


_huidige_totalen: ContextVar["_UsageTotalen | None"] = ContextVar(
    "_huidige_totalen", default=None,
)

# Markering voor deltametingen per pipeline-stap: de tokenstand bij de vorige
# delta-aanroep. Ook een ContextVar, zodat gelijktijdig verwerkte organisaties
# elkaars meting niet vervuilen.
_vorige_tokenmarkering: ContextVar[tuple[int, int]] = ContextVar(
    "_vorige_tokenmarkering", default=(0, 0),
)


def start_usage_tracking() -> None:
    """Start (of reset) de teller voor de huidige asyncio-context."""
    _huidige_totalen.set(_UsageTotalen())
    _vorige_tokenmarkering.set((0, 0))


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


T = TypeVar("T")


async def cached_provider_call(
    provider: str,
    cache_key: tuple,
    call: Callable[[], Awaitable[T]],
) -> T:
    """Voer een identieke betaalde call hoogstens één keer per researchrun uit.

    Alleen geslaagde calls komen in de cache: exceptions blijven retrybaar. De
    cache leeft in dezelfde ContextVar als de kostenteller en kan dus nooit
    resultaten tussen afzonderlijke organisaties of researchruns vermengen.
    """
    totalen = _huidige_totalen.get()
    if totalen is None:
        return await call()

    key = (provider, *cache_key)
    if key in totalen.provider_responses:
        record_provider_call(f"{provider}_cache_hit")
        return deepcopy(totalen.provider_responses[key])

    taak = totalen.provider_inflight.get(key)
    is_eigenaar = taak is None
    if taak is None:
        taak = asyncio.create_task(call())
        totalen.provider_inflight[key] = taak
    else:
        record_provider_call(f"{provider}_cache_hit")

    try:
        resultaat = (
            await taak
            if is_eigenaar
            else await asyncio.shield(taak)
        )
        if is_eigenaar:
            totalen.provider_responses[key] = deepcopy(resultaat)
        return deepcopy(resultaat)
    finally:
        if is_eigenaar:
            totalen.provider_inflight.pop(key, None)


def record_dienststoring(dienst: str, reden: str, detail: str = "") -> None:
    """Leg vast dat een externe dienst onbruikbaar was tijdens deze run.

    Hetzelfde mechanisme als de kostenteller, want het is dezelfde vraag: wat is
    er tijdens déze run met de providers gebeurd. Tot nu toe verdween dit in een
    logregel op Railway, terwijl juist de reviewer het moet weten: een run
    zonder Serper levert "niets gevonden" op, en dat is geen conclusie maar een
    storing.

    Eén regel per dienst. De eerste vastlegging wint, met een teller erbij: de
    tiende time-out van dezelfde dienst zegt niets nieuws, maar hoe vaak het
    misging bepaalt wel hoe hard het signaal is.
    """
    totalen = _huidige_totalen.get()
    if totalen is None:
        return
    bestaand = totalen.dienststoringen.get(dienst)
    if bestaand is None:
        totalen.dienststoringen[dienst] = {
            "dienst": dienst,
            "reden": reden,
            "detail": detail[:200],
            "aantal": 1,
        }
    else:
        bestaand["aantal"] += 1


def get_dienststoringen() -> list[dict]:
    """De storingen van deze run, ernstigste soort eerst."""
    totalen = _huidige_totalen.get()
    if totalen is None:
        return []
    volgorde = {"tegoed_op": 0, "sleutel_ongeldig": 1, "onbereikbaar": 2}
    return sorted(
        totalen.dienststoringen.values(),
        key=lambda item: (volgorde.get(item["reden"], 9), item["dienst"]),
    )


def get_usage_totals() -> tuple[int, int]:
    totalen = _huidige_totalen.get()
    if totalen is None:
        return (0, 0)
    return (totalen.tokens_in, totalen.tokens_out)


def _provider_kosten_micro_usd(totalen: "_UsageTotalen") -> dict[str, int]:
    settings = get_settings()
    openai_micro_usd = round((
        totalen.tokens_in / 1000 * settings.openai_prijs_in_cent_per_1k
        + totalen.tokens_out / 1000 * settings.openai_prijs_out_cent_per_1k
    ) / 100 * 1_000_000)
    return {**totalen.provider_kosten_micro_usd, "openai_tokens": openai_micro_usd}


def neem_token_delta() -> tuple[int, int]:
    """Tokens sinds de vorige aanroep, en verzet meteen de markering.

    Per pipeline-stap loggen we tokens en niet kosten: kosten_cents is in hele
    centen en een losse stap kost doorgaans een fractie daarvan, dus zou elke
    stap naar 0 afronden. Tokens zijn exact en wijzen even goed aan welke stap
    duur is; het bedrag staat op de afsluitende totaalregel."""
    tokens_in, tokens_out = get_usage_totals()
    vorige_in, vorige_uit = _vorige_tokenmarkering.get()
    _vorige_tokenmarkering.set((tokens_in, tokens_out))
    return (tokens_in - vorige_in, tokens_out - vorige_uit)


def get_cost_summary() -> dict:
    totalen = _huidige_totalen.get() or _UsageTotalen()
    provider_kosten = _provider_kosten_micro_usd(totalen)
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
