"""De gegenereerde alinea beschrijft; ze oordeelt niet en ze blokkeert niets."""
import pytest

from app.research import bronsamenvatting
from app.research.bronsamenvatting import bronnen_als_tekst, schrijf_samenvatting


def _bron(**velden) -> dict:
    basis = {
        "brontype": "jaarverslag", "documenttype": "jaarverslag",
        "verslagjaar": 2025, "informatie_peilmoment": None,
        "wp_gevonden": 412, "eenheid": "werkzame_personen",
        "bewijsfragment": "Ultimo 2025 waren er 412 medewerkers in dienst.",
        "scope_class": "vestiging", "identity_class": "exact_entity",
    }
    basis.update(velden)
    return basis


def test_de_prompt_krijgt_de_feiten_die_een_verschil_verklaren():
    """Peilmoment en scope verklaren vaak meer dan een fout dat doet."""
    tekst = bronnen_als_tekst([
        _bron(),
        _bron(verslagjaar=2023, wp_gevonden=380, brontype="media",
              documenttype="nieuwsartikel", scope_class="concern"),
    ])

    assert "verslagjaar 2025" in tekst
    assert "412 WP" in tekst
    assert "verslagjaar 2023" in tekst
    assert "scope: concern" in tekst
    assert "412 medewerkers in dienst" in tekst


def test_een_bron_zonder_getal_zegt_dat_met_zoveel_woorden():
    tekst = bronnen_als_tekst([_bron(wp_gevonden=None, eenheid=None)])
    assert "geen getal uitgelezen" in tekst


def test_fte_wordt_niet_als_wp_gepresenteerd():
    """FTE is geen WP; dat mag ook in de prompt niet vervagen."""
    tekst = bronnen_als_tekst([_bron(wp_gevonden=312, eenheid="fte")])
    assert "312 FTE" in tekst
    assert "312 WP" not in tekst


def test_de_prompt_blijft_begrensd_bij_veel_bronnen():
    """Anders wordt de call duur zonder dat de reviewer er meer aan heeft."""
    tekst = bronnen_als_tekst([_bron() for _ in range(20)])
    # Eén regel per bron begint met "- "; het citaat staat ingesprongen eronder.
    bronregels = [regel for regel in tekst.splitlines() if regel.startswith("- ")]
    assert len(bronregels) == bronsamenvatting.MAX_BRONNEN_IN_PROMPT


@pytest.mark.asyncio
async def test_zonder_bronnen_wordt_er_niets_geschreven():
    assert await schrijf_samenvatting("Voorbeeld", 2025, []) is None


@pytest.mark.asyncio
async def test_een_mislukte_call_houdt_de_run_niet_tegen(monkeypatch):
    """Dit is de buitenste laag, niet het bewijs.

    Valt hij weg, dan valt de kaart terug op zijn vaste tekst — er hoort nooit
    een lege of half afgemaakte samenvatting te blijven staan.
    """
    monkeypatch.setattr(
        bronsamenvatting.get_settings(), "openai_api_key", "test-key",
    )

    async def kapotte_call(*args, **kwargs):
        raise RuntimeError("model onbereikbaar")

    from app.providers import llm
    monkeypatch.setattr(llm, "_create_response", kapotte_call)

    assert await schrijf_samenvatting("Voorbeeld", 2025, [_bron()]) is None


@pytest.mark.asyncio
async def test_een_lege_of_ongeldige_uitkomst_telt_niet_als_samenvatting(monkeypatch):
    monkeypatch.setattr(
        bronsamenvatting.get_settings(), "openai_api_key", "test-key",
    )

    class _Response:
        output_text = '{"toelichting": "   "}'

    async def fake_call(*args, **kwargs):
        return _Response()

    async def fake_parse(*args, **kwargs):
        return {"toelichting": "   "}

    from app.providers import llm
    monkeypatch.setattr(llm, "_create_response", fake_call)
    monkeypatch.setattr(llm, "_parse_json_met_herstel", fake_parse)

    assert await schrijf_samenvatting("Voorbeeld", 2025, [_bron()]) is None
