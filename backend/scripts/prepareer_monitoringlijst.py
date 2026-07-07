"""Zet Testbatch Jaarverslagen.xls om naar een organisatie-niveau watchlist.

Gebruik vanuit backend/: python -m scripts.prepareer_monitoringlijst
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LEEG_CBNR = {"", "0", "000000"}


def _tekst(waarde) -> str:
    if waarde is None:
        return ""
    if isinstance(waarde, float) and waarde.is_integer():
        return str(int(waarde))
    return str(waarde).strip()


def _cbnr(waarde) -> str:
    tekst = _tekst(waarde)
    if tekst.endswith(".0") and tekst[:-2].isdigit():
        tekst = tekst[:-2]
    return tekst.zfill(6) if tekst.isdigit() else tekst


def organisaties_uit_vestiging_tabblad(rijen: list[dict]) -> list[dict]:
    """Groepeert vestigingen op cbnr en kiest de organisatie-/CB-er-naam."""
    groepen: dict[str, list[dict]] = {}
    organisaties: list[dict] = []

    for rij in rijen:
        cbnr = _cbnr(rij.get("cbnr", ""))
        naam = _tekst(rij.get("naam", ""))
        if not naam:
            continue
        if cbnr in LEEG_CBNR:
            organisaties.append({"naam": naam, "cb_er": None})
        else:
            groepen.setdefault(cbnr, []).append(rij)

    for cbnr, groep_rijen in groepen.items():
        cber_namen = [_tekst(r.get("cb-er", "")) for r in groep_rijen if _tekst(r.get("cb-er", ""))]
        if cber_namen:
            naam = cber_namen[0]
        else:
            naam = min((_tekst(r.get("naam", "")) for r in groep_rijen if _tekst(r.get("naam", ""))), key=len)
        organisaties.append({"naam": naam, "cb_er": cbnr})

    return organisaties


def organisaties_uit_organisatie_tabblad(rijen: list[dict]) -> list[dict]:
    """Leest een tabblad dat al op organisatie-niveau staat."""
    organisaties = []
    for rij in rijen:
        naam = _tekst(rij.get("naam cb-er", ""))
        if not naam:
            continue
        cbnr = _cbnr(rij.get("cbnr", ""))
        organisaties.append({"naam": naam, "cb_er": None if cbnr in LEEG_CBNR else cbnr})
    return organisaties


def dedupliceer_organisaties(*groepen: list[dict]) -> list[dict]:
    """Combineert en dedupliceert op cb_er, of op naam voor losse vestigingen."""
    gezien: set[tuple[str, str]] = set()
    resultaat = []
    for organisaties in groepen:
        for org in organisaties:
            naam = _tekst(org.get("naam", ""))
            cb_er = org.get("cb_er") or None
            if not naam:
                continue
            sleutel = ("cb_er", cb_er) if cb_er else ("naam", naam.casefold())
            if sleutel in gezien:
                continue
            gezien.add(sleutel)
            resultaat.append({"naam": naam, "cb_er": cb_er})
    return resultaat


def _lees_rijen(werkboek, sheetnaam: str) -> list[dict]:
    sheet = werkboek.sheet_by_name(sheetnaam)
    header = [_tekst(h).lower() for h in sheet.row_values(0)]
    rijen = []
    for row_index in range(1, sheet.nrows):
        waarden = sheet.row_values(row_index)
        if not any(_tekst(v) for v in waarden):
            continue
        rijen.append(dict(zip(header, waarden)))
    return rijen


def main() -> int:
    import xlrd

    bron_pad = Path(__file__).resolve().parents[2] / "Testbatch Jaarverslagen.xls"
    if not bron_pad.exists():
        print(f"Bronbestand niet gevonden: {bron_pad}")
        return 1

    werkboek = xlrd.open_workbook(str(bron_pad), encoding_override="latin-1")
    vestiging_orgs = organisaties_uit_vestiging_tabblad(_lees_rijen(werkboek, "Alles vorig jaar 16"))
    organisatie_orgs = organisaties_uit_organisatie_tabblad(_lees_rijen(werkboek, "Alles map Jaarverslagen"))
    organisaties = dedupliceer_organisaties(vestiging_orgs, organisatie_orgs)

    output_pad = Path(__file__).resolve().parents[1] / "data" / "jaarverslag_monitoringlijst.csv"
    output_pad.parent.mkdir(parents=True, exist_ok=True)
    with output_pad.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["naam", "cb_er"])
        writer.writeheader()
        writer.writerows(organisaties)

    print(f"{len(organisaties)} organisaties geschreven naar {output_pad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
