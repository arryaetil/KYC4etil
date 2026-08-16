"""De registers bepalen zelf of een organisatie tot hun sector hoort.

Tussenoplossing zolang het Vestigingsregister geen SBI-codes aanlevert. Alle
205 monitoringorganisaties hebben nu een lege `sbi_code`, en de naamfallback
herkende daardoor maar 14 van de 32 zorgorganisaties.
"""
import pytest

from app.research import sector_probe
from app.research.query_planner import QueryContext, plan_routes
from app.research.sector_probe import verrijk_routeplan


def _routes(plan):
    return {item["route"] for item in plan}


@pytest.mark.asyncio
async def test_sbi_code_slaat_de_probe_over(monkeypatch):
    """Met een SBI-code is de planner betrouwbaar; dan geen extra verkeer.

    Zodra het Vestigingsregister SBI-codes levert, kost deze module niets.
    """
    async def _mag_niet(context):
        raise AssertionError("met een sbi_code hoort er niets bevraagd te worden")

    monkeypatch.setitem(sector_probe._PROBES, "digimv", (_mag_niet, "x"))
    monkeypatch.setitem(sector_probe._PROBES, "duo", (_mag_niet, "x"))
    monkeypatch.setitem(sector_probe._PROBES, "lrk", (_mag_niet, "x"))

    context = QueryContext(naam="Mondriaan", sbi_code="8622", gevraagd_jaar=2026)
    plan = plan_routes(context)

    assert await verrijk_routeplan(context, plan) == plan


@pytest.mark.asyncio
async def test_probe_vult_een_gemiste_zorgroute_aan(monkeypatch):
    """Merknamen als "Mondriaan" of "Envida" verraden de sector niet."""
    async def _ja(context):
        return True

    async def _nee(context):
        return False

    monkeypatch.setitem(sector_probe._PROBES, "digimv", (_ja, "DigiMV kent deze organisatie"))
    monkeypatch.setitem(sector_probe._PROBES, "duo", (_nee, "x"))
    monkeypatch.setitem(sector_probe._PROBES, "lrk", (_nee, "x"))

    context = QueryContext(naam="Mondriaan", gemeente="Heerlen", gevraagd_jaar=2026)
    plan = plan_routes(context)
    assert "digimv" not in _routes(plan), "voorwaarde: de naam verraadt niets"

    verrijkt = await verrijk_routeplan(context, plan)

    assert "digimv" in _routes(verrijkt)
    toegevoegd = [i for i in verrijkt if i.get("herkomst") == "sectorprobe"]
    assert len(toegevoegd) == 1
    # Een aanvulling op een plan zonder SBI-code is geen harde eis aan de run.
    assert toegevoegd[0]["verplicht"] is False


@pytest.mark.asyncio
async def test_media_blijft_achteraan_staan(monkeypatch):
    async def _ja(context):
        return True

    async def _nee(context):
        return False

    monkeypatch.setitem(sector_probe._PROBES, "digimv", (_ja, "x"))
    monkeypatch.setitem(sector_probe._PROBES, "duo", (_nee, "x"))
    monkeypatch.setitem(sector_probe._PROBES, "lrk", (_nee, "x"))

    context = QueryContext(naam="Mondriaan", gevraagd_jaar=2026)
    verrijkt = await verrijk_routeplan(context, plan_routes(context))

    assert verrijkt[-1]["route"] == "media"


@pytest.mark.asyncio
async def test_reeds_geplande_routes_worden_niet_bevraagd(monkeypatch):
    """Wat de planner al wist, hoeft geen HTTP-lookup."""
    bevraagd: list[str] = []

    def _teller(naam):
        async def _probe(context):
            bevraagd.append(naam)
            return False
        return _probe

    for route in ("digimv", "duo", "lrk"):
        monkeypatch.setitem(sector_probe._PROBES, route, (_teller(route), "x"))

    # "Zorggroep" wordt door de naamfallback al als zorg herkend.
    context = QueryContext(naam="Cicero Zorggroep", gevraagd_jaar=2026)
    await verrijk_routeplan(context, plan_routes(context))

    assert "digimv" not in bevraagd
    assert set(bevraagd) == {"duo", "lrk"}


@pytest.mark.asyncio
async def test_onbereikbaar_register_blokkeert_de_run_niet(monkeypatch):
    async def _stuk(context):
        raise RuntimeError("register onbereikbaar")

    for route in ("digimv", "duo", "lrk"):
        monkeypatch.setitem(sector_probe._PROBES, route, (_stuk, "x"))

    context = QueryContext(naam="Mondriaan", gevraagd_jaar=2026)
    plan = plan_routes(context)

    assert await verrijk_routeplan(context, plan) == plan


@pytest.mark.asyncio
async def test_duo_probe_eist_een_symmetrische_naammatch(monkeypatch):
    """"Mondriaan" is niet "ROC Mondriaan".

    De DUO-route gebruikt `_match_score`, die alleen vraagt of ónze naam in
    die van DUO zit. Voor de route is dat te overzien — `bouw_duo_bron` eist
    daarna instellingscodes. Voor een sectorprobe niet: één valse treffer
    voegt een hele route toe en verbruikt querybudget.
    """
    from app.research.duo import DuoVestiging

    roc = DuoVestiging(
        sector="mbo", instellingscode="30035", naam="ROC Mondriaan",
        plaats="'s-Gravenhage", gemeente="'s-Gravenhage",
    )
    yuverta = DuoVestiging(
        sector="mbo", instellingscode="30061", naam="Yuverta",
        plaats="Utrecht", gemeente="Utrecht",
    )

    monkeypatch.setattr(sector_probe, "_PROBES", dict(sector_probe._PROBES))
    monkeypatch.setattr(
        "app.research.duo._VESTIGING_CACHE",
        {"po": [], "vo": [], "mbo": [roc, yuverta]},
    )

    assert await sector_probe._staat_in_duo(
        QueryContext(naam="Mondriaan", gemeente="Heerlen"),
    ) is False
    assert await sector_probe._staat_in_duo(
        QueryContext(naam="Stichting Yuverta", gemeente="Utrecht"),
    ) is True
