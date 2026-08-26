"""Een onverwachte fout moet in de browser leesbaar aankomen.

Bij het intrekken van een account weigerde Postgres de verwijdering, en de
interface zei "Failed to fetch". Dat leest als een netwerkstoring: de server
draait niet, het internet is weg. De server antwoordde gewoon — met een 500 —
maar dat antwoord kwam langs de CORS-laag heen en werd door de browser
weggegooid voordat de frontend het kon lezen.
"""
from fastapi import APIRouter

from app.config import get_settings
from app.main import app as fastapi_app

_router = APIRouter()


@_router.get("/_test/klapt-eruit")
def _klapt_eruit():
    raise RuntimeError("iets wat niemand had voorzien")


fastapi_app.include_router(_router)


def test_een_onverwachte_fout_wordt_een_leesbaar_antwoord(client):
    origin = get_settings().cors_origins[0]

    response = client.get("/_test/klapt-eruit", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.json()["detail"]
    # Zonder deze header gooit de browser het antwoord weg en meldt de
    # frontend "Failed to fetch" in plaats van wat er staat.
    assert response.headers["access-control-allow-origin"] == origin
