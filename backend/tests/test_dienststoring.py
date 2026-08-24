"""Een uitgevallen dienst mag niet als "niets gevonden" bij de reviewer landen."""
import httpx

from app.providers.dienststatus import classificeer, meld_storing
from app.research.usage import get_dienststoringen, start_usage_tracking


def _http_fout(status: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://voorbeeld.test/api")
    response = httpx.Response(status, request=request, text=body)
    return httpx.HTTPStatusError("fout", request=request, response=response)


def test_serper_leeg_tegoed_wordt_herkend_aan_de_body():
    """Serper meldt een leeg tegoed met HTTP 400, niet met 401 of 402.

    Een guard op statuscodes alléén mist daarom precies het geval waarvoor hij
    bedoeld is; de body is hier de betrouwbaardere bron.
    """
    reden, detail = classificeer(
        _http_fout(400, '{"message":"Not enough credits","statusCode":400}'),
    )
    assert reden == "tegoed_op"
    assert "400" in detail


def test_openai_quota_wordt_herkend():
    reden, _ = classificeer(
        _http_fout(429, "You exceeded your current quota, please check your plan"),
    )
    assert reden == "tegoed_op"


def test_google_places_geweigerde_sleutel_wordt_herkend():
    reden, _ = classificeer(_http_fout(403, '{"status":"REQUEST_DENIED"}'))
    assert reden == "sleutel_ongeldig"


def test_een_time_out_is_geen_tegoedprobleem():
    """Anders staat er bij elke haperende verbinding "geen tegoed meer"."""
    reden, _ = classificeer(httpx.ConnectTimeout("te traag"))
    assert reden == "onbereikbaar"


def test_storingen_worden_per_dienst_geteld_en_gesorteerd():
    start_usage_tracking()
    meld_storing("google_places", httpx.ConnectTimeout("traag"))
    meld_storing("google_places", httpx.ConnectTimeout("traag"))
    meld_storing("serper", _http_fout(400, "Not enough credits"))

    storingen = get_dienststoringen()

    # Tegoed op staat vooraan: dat is het probleem dat iemand moet oplossen.
    assert [item["dienst"] for item in storingen] == ["serper", "google_places"]
    assert storingen[0]["reden"] == "tegoed_op"
    assert storingen[1]["aantal"] == 2


def test_zonder_lopende_run_wordt_er_niets_vastgelegd():
    """Buiten een run is er geen teller; dat mag geen fout geven."""
    import app.research.usage as usage

    usage._huidige_totalen.set(None)
    meld_storing("serper", _http_fout(429))
    assert get_dienststoringen() == []
