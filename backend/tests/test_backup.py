"""Een back-up die je niet kunt terugzetten is er geen."""
import gzip
import json

import pytest

from app import backup
from app.config import get_settings


@pytest.fixture
def backupmap(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "backup_pad", str(tmp_path / "backups"))
    return tmp_path


def test_zonder_pad_wordt_er_niets_gemaakt(monkeypatch):
    """Naar een niet-gemonteerde map schrijven levert een bestand op dat bij de
    volgende deploy verdwijnt: geen back-up maar een geruststelling."""
    monkeypatch.setattr(get_settings(), "backup_pad", "")

    assert backup.backupmap() is None
    assert backup.maak_backup() is None
    assert backup.bestaande_backups() == []


def test_een_backup_bevat_de_rijen_en_een_sluitregel(backupmap):
    # Rechtstreeks via de engine die de back-up ook gebruikt: de testsessie
    # draait in een transactie die de back-up niet ziet, en dan test je de
    # sessieopzet in plaats van de back-up.
    from sqlalchemy import text

    from app.database import engine

    with engine.begin() as verbinding:
        verbinding.execute(
            text("INSERT INTO batches (id, naam, jaar, totaal, status, verwerkt,"
                 " is_monitoringlijst, created_at) VALUES ('bk-1',"
                 " 'back-uptest', 2026, 1, 'pending', 0, 0, '2026-08-26')"),
        )

    pad = backup.maak_backup()

    assert pad is not None
    assert backup.is_compleet(pad) is True
    regels = [
        json.loads(r) for r in
        gzip.open(pad, "rt", encoding="utf-8").read().splitlines() if r.strip()
    ]
    assert "_backup" in regels[0]
    assert regels[-1]["_klaar"] is True
    namen = [
        r["rij"]["naam"] for r in regels
        if r.get("_tabel") == "batches"
    ]
    assert "back-uptest" in namen


def test_een_afgebroken_bestand_geldt_niet_als_backup(backupmap):
    """Van buiten ziet dat er hetzelfde uit als een goede back-up.

    Dat verschil is precies het verschil tussen een herstelpunt en een vals
    gevoel van veiligheid.
    """
    map_pad = backup.backupmap()
    half = map_pad / "kyc-2026-01-01T0300.jsonl.gz"
    with gzip.open(half, "wt", encoding="utf-8") as bestand:
        bestand.write(json.dumps({"_backup": "half", "tabellen": []}) + "\n")
        bestand.write(json.dumps({"_tabel": "batches", "rij": {"id": "x"}}) + "\n")

    assert backup.is_compleet(half) is False


def test_er_blijven_hoogstens_veertien_herstelpunten_staan(backupmap, monkeypatch):
    map_pad = backup.backupmap()
    for dag in range(1, 21):
        (map_pad / f"kyc-2026-01-{dag:02d}T0300.jsonl.gz").write_bytes(b"x")

    backup._ruim_op(map_pad)

    assert len(list(map_pad.glob("kyc-*.jsonl.gz"))) == backup.MAX_BACKUPS
    # De nieuwste blijven staan, niet de oudste.
    namen = sorted(p.name for p in map_pad.glob("kyc-*.jsonl.gz"))
    assert namen[-1] == "kyc-2026-01-20T0300.jsonl.gz"
