"""Per-run tokenverbruik: contextvar-gebaseerde teller, ook over
gelijktijdige asyncio-taken heen."""
import asyncio
from types import SimpleNamespace

import pytest

from app.research import usage
from app.research.usage import (
    get_cost_summary,
    get_usage_totals,
    record_provider_call,
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


def test_tokenkosten_volgen_de_prijzen_uit_config():
    # 200.000 input- + 50.000 output-tokens tegen de standaardprijzen in
    # config.py (gpt-5.6-luna: 0,02 cent per 1k in, 0,12 cent per 1k uit).
    # 200 * 0,02 = 4,0 cent + 50 * 0,12 = 6,0 cent = 10 cent.
    start_usage_tracking()
    record_response_usage(_response(200_000, 50_000))

    assert get_cost_summary()["totaal_cents"] == 10


def test_kostenoverzicht_telt_tokens_en_alle_providercalls():
    start_usage_tracking()
    record_response_usage(_response(15_000, 400))
    record_provider_call("serper_search", kosten_micro_usd=1_000)
    record_provider_call("serper_search", kosten_micro_usd=1_000)
    record_provider_call("google_places_text_search", kosten_micro_usd=32_000)
    record_provider_call("duckduckgo_search")

    kosten = get_cost_summary()

    assert kosten["providers"]["openai_tokens"]["calls"] == 1
    assert kosten["providers"]["serper_search"] == {
        "calls": 2, "kosten_usd": 0.002,
    }
    assert kosten["providers"]["google_places_text_search"] == {
        "calls": 1, "kosten_usd": 0.032,
    }
    assert kosten["providers"]["duckduckgo_search"] == {
        "calls": 1, "kosten_usd": 0.0,
    }
    # 15.000 in * 0,02 + 400 uit * 0,12 = 0,348 cent (prijzen uit config.py)
    assert kosten["providers"]["openai_tokens"]["kosten_usd"] == 0.00348
    assert kosten["totaal_usd"] == 0.03748
    assert kosten["totaal_cents"] == 4


def test_openai_web_search_toolcall_wordt_apart_geregistreerd():
    start_usage_tracking()
    response = _response(100, 10)
    response.model_dump = lambda: {
        "output": [{"type": "web_search_call"}],
    }

    record_response_usage(response)

    kosten = get_cost_summary()
    assert kosten["providers"]["openai_web_search"] == {
        "calls": 1, "kosten_usd": 0.01,
    }


# --- tokenregistratie per pipeline-stap (pipeline_runs) ---

def test_token_delta_meet_alleen_verbruik_sinds_vorige_aanroep():
    start_usage_tracking()
    record_response_usage(_response(100, 20))

    eerste = usage.neem_token_delta()
    record_response_usage(_response(40, 5))
    tweede = usage.neem_token_delta()

    assert eerste == (100, 20)
    assert tweede == (40, 5)


def test_token_delta_zonder_nieuw_verbruik_is_nul():
    start_usage_tracking()
    record_response_usage(_response(100, 20))
    usage.neem_token_delta()

    assert usage.neem_token_delta() == (0, 0)


def test_start_usage_tracking_reset_ook_de_tokenmarkering():
    start_usage_tracking()
    record_response_usage(_response(100, 20))

    start_usage_tracking()

    assert usage.neem_token_delta() == (0, 0)
