"""Niet elk model accepteert de temperature-parameter.

gpt-5.6-luna — het hoofdmodel in productie — antwoordt op elke andere waarde
dan zijn eigen default met HTTP 400. Omdat `openai_temperature` op 0.0 staat,
faalde daardoor élke call door `_create_response`: de volledige WP-extractie
en de scope-classificatie. Stil, want de aanroepers vangen de fout af en
leveren `None` — niet te onderscheiden van "niets gevonden".
"""
import pytest

from app.providers import llm


class _Response:
    output_text = "{}"
    usage = None


class _Client:
    """Bootst een model na dat temperature weigert, zoals gpt-5.6-luna."""

    def __init__(self, weigert: bool):
        self.weigert = weigert
        self.aanroepen: list[dict] = []
        self.responses = self

    async def create(self, **kwargs):
        self.aanroepen.append(dict(kwargs))
        if self.weigert and "temperature" in kwargs:
            raise RuntimeError(
                "Error code: 400 - {'error': {'message': \"Unsupported "
                "parameter: 'temperature' is not supported with this model.\"}}"
            )
        return _Response()


@pytest.fixture(autouse=True)
def _schone_cache():
    llm._ZONDER_TEMPERATURE.clear()
    yield
    llm._ZONDER_TEMPERATURE.clear()


@pytest.mark.asyncio
async def test_model_dat_temperature_weigert_krijgt_de_call_alsnog():
    client = _Client(weigert=True)

    await llm._create_response(client, model="gpt-5.6-luna", input="x")

    assert len(client.aanroepen) == 2, "eerst mét, daarna zonder temperature"
    assert "temperature" in client.aanroepen[0]
    assert "temperature" not in client.aanroepen[1]


@pytest.mark.asyncio
async def test_de_weigering_wordt_per_model_onthouden():
    """Hooguit één mislukte call per model per proces."""
    client = _Client(weigert=True)

    await llm._create_response(client, model="gpt-5.6-luna", input="x")
    await llm._create_response(client, model="gpt-5.6-luna", input="y")

    assert "gpt-5.6-luna" in llm._ZONDER_TEMPERATURE
    assert len(client.aanroepen) == 3, "de tweede call probeert het niet opnieuw"
    assert "temperature" not in client.aanroepen[2]


@pytest.mark.asyncio
async def test_model_dat_temperature_wel_accepteert_houdt_determinisme():
    """Waar het mag, blijft 0.0 staan: dezelfde bron hoort hetzelfde oordeel
    te krijgen tussen twee runs."""
    client = _Client(weigert=False)

    await llm._create_response(client, model="gpt-5.2", input="x")

    assert len(client.aanroepen) == 1
    assert client.aanroepen[0]["temperature"] == llm.settings.openai_temperature


@pytest.mark.asyncio
async def test_expliciete_temperature_blijft_gerespecteerd():
    client = _Client(weigert=False)

    await llm._create_response(client, model="gpt-5.2", input="x", temperature=0.7)

    assert client.aanroepen[0]["temperature"] == 0.7


@pytest.mark.asyncio
async def test_andere_fouten_worden_niet_verdoezeld():
    """Alleen een expliciete temperature-weigering mag een retry uitlokken."""
    class _StukkeClient(_Client):
        async def create(self, **kwargs):
            self.aanroepen.append(dict(kwargs))
            raise RuntimeError("Error code: 429 - rate limit exceeded")

    client = _StukkeClient(weigert=True)
    with pytest.raises(RuntimeError, match="429"):
        await llm._create_response(client, model="gpt-5.6-luna", input="x")
    assert len(client.aanroepen) == 1
