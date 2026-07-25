"""Per-run tokenverbruik: contextvar-gebaseerde teller, ook over
gelijktijdige asyncio-taken heen."""
import asyncio
from types import SimpleNamespace

import pytest

from app.research import usage
from app.research.usage import (
    bereken_kosten_cents,
    get_usage_totals,
    record_response_usage,
    start_usage_tracking,
)


@pytest.fixture(autouse=True)
def _reset_usage_tracking():
    """Zorgt dat elke test start vanaf een schone, ongetrackte ContextVar-staat
    — zonder deze fixture leunt de testvolgorde stilzwijgend op wie het eerst
    draait, doordat de ContextVar globale procesbrede state is voor
    niet-task-gewrapte code."""
    usage._huidige_totalen.set(None)
    yield


def _response(input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=input_tokens, output_tokens=output_tokens,
        ),
    )


def test_zonder_actieve_tracking_blijft_totaal_op_nul():
    assert get_usage_totals() == (0, 0)
    record_response_usage(_response(100, 20))
    assert get_usage_totals() == (0, 0)


def test_telt_meerdere_responses_op():
    start_usage_tracking()
    record_response_usage(_response(100, 20))
    record_response_usage(_response(50, 10))
    assert get_usage_totals() == (150, 30)


def test_response_zonder_usage_veld_wordt_genegeerd():
    start_usage_tracking()
    record_response_usage(SimpleNamespace())
    assert get_usage_totals() == (0, 0)


@pytest.mark.asyncio
async def test_contextvar_isoleert_gelijktijdige_taken():
    async def taak(tokens_in: int) -> tuple[int, int]:
        start_usage_tracking()
        record_response_usage(_response(tokens_in, 5))
        await asyncio.sleep(0.01)
        return get_usage_totals()

    resultaten = await asyncio.gather(taak(100), taak(200), taak(300))

    assert resultaten == [(100, 5), (200, 5), (300, 5)]


@pytest.mark.asyncio
async def test_gelijktijdige_taken_tellen_op_bij_de_ouder():
    """Dekt de daadwerkelijke productievorm (Task 5): tracking start één keer
    in de ouder-context, kindtaken in asyncio.gather tellen mee op, en het
    totaal wordt uitgelezen in de ouder."""
    start_usage_tracking()

    async def taak(n):
        record_response_usage(_response(n, 1))

    await asyncio.gather(taak(100), taak(200), taak(300))

    assert get_usage_totals() == (600, 3)


def test_bereken_kosten_cents():
    # 200.000 input- + 50.000 output-tokens tegen de standaardprijzen in
    # config.py (gpt-4o-mini: 0,015 cent per 1k in, 0,06 cent per 1k uit).
    # 200 * 0,015 = 3,0 cent + 50 * 0,06 = 3,0 cent = 6 cent.
    cents = bereken_kosten_cents(200_000, 50_000)
    assert cents > 0
    assert cents == round(200_000 / 1000 * 0.015 + 50_000 / 1000 * 0.06)
    assert cents == 6
