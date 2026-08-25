"""Brondocumenten bewaren, zodat het bewijs blijft bestaan als de bron verdwijnt."""
import pytest

from app import documenten
from app.config import get_settings


@pytest.fixture
def opslag(tmp_path, monkeypatch):
    monkeypatch.setattr(
        get_settings(), "brondocumenten_pad", str(tmp_path / "brondocumenten"),
    )
    return tmp_path


def test_zonder_pad_wordt_er_niets_bewaard(monkeypatch):
    """Leeg pad betekent uit.

    Zonder volume schrijven we naar een schijf die bij de volgende deploy weg
    is, en dan is "bewaard" een loze belofte.
    """
    monkeypatch.setattr(get_settings(), "brondocumenten_pad", "")

    assert documenten.opslagmap() is None
    assert documenten.bewaar("https://x.nl/jaarverslag.pdf", b"%PDF-1.4") is False
    assert documenten.lees("https://x.nl/jaarverslag.pdf") is None


def test_bewaren_en_teruglezen(opslag):
    url = "https://voorbeeld.nl/jaarverslag-2025.pdf"

    assert documenten.bewaar(url, b"%PDF-1.4 inhoud") is True
    assert documenten.lees(url) == b"%PDF-1.4 inhoud"
    assert documenten.aantal_bewaard() == 1


def test_dezelfde_bron_levert_een_bestand(opslag):
    """Trackingparameters en een trailing slash maken geen tweede document."""
    documenten.bewaar("https://voorbeeld.nl/jv.pdf", b"%PDF-1.4 een")
    documenten.bewaar("https://www.voorbeeld.nl/jv.pdf?utm_source=openai", b"%PDF-1.4 een")

    assert documenten.aantal_bewaard() == 1


def test_een_bestaand_document_wordt_niet_overschreven(opslag):
    """De eerste versie die we zagen is de versie waarop is beoordeeld.

    Vervangt een organisatie haar jaarverslag op dezelfde URL door de nieuwe
    editie, dan is juist de oude versie het bewijs.
    """
    url = "https://voorbeeld.nl/jaarverslag.pdf"
    documenten.bewaar(url, b"%PDF eerste versie")
    documenten.bewaar(url, b"%PDF nieuwe editie")

    assert documenten.lees(url) == b"%PDF eerste versie"


def test_een_leeg_of_te_groot_document_wordt_geweigerd(opslag):
    assert documenten.bewaar("https://voorbeeld.nl/leeg.pdf", b"") is False
    groot = b"x" * (documenten.MAX_DOCUMENT_BYTES + 1)
    assert documenten.bewaar("https://voorbeeld.nl/groot.pdf", groot) is False
    assert documenten.aantal_bewaard() == 0


def test_er_blijft_geen_half_bestand_achter(opslag):
    """Een half geschreven bestand mag nooit als geldig bewijs terugkomen."""
    url = "https://voorbeeld.nl/jv.pdf"
    documenten.bewaar(url, b"%PDF-1.4 compleet")

    map_pad = documenten.opslagmap()
    assert list(map_pad.glob("*.deel")) == []
    assert len(list(map_pad.glob("*.pdf"))) == 1
