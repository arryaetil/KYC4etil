from io import BytesIO
import csv
from pathlib import Path

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from app.research.duo import (
    DuoPersoneelswaarde,
    DuoVestiging,
    bouw_duo_bron,
    lees_personeelswaarden,
    vind_vestigingen,
)
from app.research.query_planner import QueryContext
from app.research.ranking import rank_bronnen
from app.research.validation import valideer_bron
from app.research.source_reviewer import IntelligentSourceReviewer


def _vestiging(**overrides) -> DuoVestiging:
    basis = {
        "sector": "vo",
        "instellingscode": "01MO",
        "vestigingscode": "01MO00",
        "naam": "Atheneum van de Trevianum Scholengroep",
        "straat": "Bradleystraat",
        "plaats": "Sittard",
        "gemeente": "Sittard-Geleen",
        "provincie": "Limburg",
        "bevoegd_gezag": "42576",
    }
    basis.update(overrides)
    return DuoVestiging(**basis)


def _personeelsbestand(rijen: list[tuple[str, object, object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "owtype-best-instelling"
    sheet.append([
        "ONDERWIJSTYPE", "BEVOEGD GEZAG", "INSTELLINGSCODE",
        "PERSONEN 2024", "PERSONEN 2025",
    ])
    for code, waarde_2024, waarde_2025 in rijen:
        sheet.append(["VO", 42576, code, waarde_2024, waarde_2025])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_duo_vestiging_valideert_externe_rij():
    with pytest.raises(ValidationError):
        _vestiging(instellingscode="")


def test_vindt_alle_codes_van_een_onderwijsgroep():
    vestigingen = [
        _vestiging(),
        _vestiging(
            instellingscode="04DS",
            vestigingscode="04DS00",
            naam="Gymnasium van de Trevianum Scholengroep",
        ),
        _vestiging(
            instellingscode="07BQ",
            vestigingscode="07BQ00",
            naam="HAVO van de Trevianum Scholengroep",
        ),
        _vestiging(
            instellingscode="99XX",
            vestigingscode="99XX00",
            naam="Andere Scholengroep",
        ),
    ]

    matches = vind_vestigingen(
        QueryContext(
            naam="Trevianum Scholengroep",
            gemeente="Sittard-Geleen",
            sbi_code="85202",
        ),
        vestigingen,
    )

    assert {item.instellingscode for item in matches} == {
        "01MO", "04DS", "07BQ",
    }


def test_leest_gevraagd_jaar_en_statistische_markering():
    waarden = lees_personeelswaarden(
        _personeelsbestand([
            ("01MO", 219, 225),
            ("04DS", "*", "**"),
        ]),
        {"01MO", "04DS"},
        gevraagd_jaar=2024,
    )

    assert waarden["01MO"].aantal_personen == 219
    assert waarden["01MO"].jaar == 2024
    assert waarden["04DS"].aantal_personen is None
    assert waarden["04DS"].statistische_markering == "*"


def test_een_instelling_wordt_direct_duo_bewijs():
    vestiging = _vestiging(
        instellingscode="23HH",
        vestigingscode="23HH00",
        naam="Praktijkonderwijs Roermond",
        straat="Heinsbergerweg",
        plaats="Roermond",
        gemeente="Roermond",
    )
    context = QueryContext(
        naam="Praktijkonderwijs Roermond",
        gemeente="Roermond",
        gevraagd_jaar=2025,
        sbi_code="85311",
    )

    bron = bouw_duo_bron(
        context,
        [vestiging],
        [vestiging],
        lees_personeelswaarden(
            _personeelsbestand([("23HH", 33, 35)]),
            {"23HH"},
            2025,
        ),
        "https://duo.nl/personeel-vo.xlsx",
    )

    assert bron is not None
    assert bron.wp_gevonden == 35
    assert bron.eenheid == "onderwijspersoneel_personen"
    assert bron.scope_class == "vestiging"
    assert bron.research_route == "duo"
    assert bron.raw_data["instellingscodes"] == ["23HH"]


def test_duo_mag_een_jaar_achterlopen_maar_niet_twee():
    """DUO meet op 1 oktober en publiceert met vertraging.

    Voor het lopende peiljaar bestaat er dus per definitie nog geen DUO-cijfer.
    De harde afwijzing op "verkeerd verslagjaar" liet zo'n bron helemaal niet op
    de kaart komen, terwijl het cijfer beoordeelbaar is. Twee jaar achter blijft
    wel een afwijzing: dan is er inmiddels nieuwere DUO-data.
    """
    vestiging = _vestiging(
        instellingscode="23HH", vestigingscode="23HH00",
        naam="Praktijkonderwijs Roermond", plaats="Roermond", gemeente="Roermond",
    )

    def bron_voor(duo_jaar: int):
        context = QueryContext(
            naam="Praktijkonderwijs Roermond", gemeente="Roermond",
            gevraagd_jaar=2025, sbi_code="85311",
        )
        document = bouw_duo_bron(
            context, [vestiging], [vestiging],
            {"23HH": DuoPersoneelswaarde(
                instellingscode="23HH", jaar=duo_jaar, aantal_personen=35,
            )},
            "https://duo.nl/personeel-vo.xlsx",
        )
        return valideer_bron(document)

    gelijk = bron_voor(2025)
    assert gelijk.is_afgewezen is False
    assert "duo_jaar_achter" not in gelijk.waarschuwingen

    een_jaar = bron_voor(2024)
    assert een_jaar.is_afgewezen is False
    assert "duo_jaar_achter" in een_jaar.waarschuwingen

    twee_jaar = bron_voor(2023)
    assert twee_jaar.is_afgewezen is True
    assert "verkeerd verslagjaar" in twee_jaar.afwijsredenen


def test_duo_van_het_gevraagde_jaar_scoort_hoger_dan_een_jaar_ouder():
    """"Liefst het gevraagde jaar" hoort in de rangschikking te zitten, niet in
    een afwijzing: een ouder cijfer mag getoond worden, maar zakt wel."""
    vestiging = _vestiging(
        instellingscode="23HH", vestigingscode="23HH00",
        naam="Praktijkonderwijs Roermond", plaats="Roermond", gemeente="Roermond",
    )
    context = QueryContext(
        naam="Praktijkonderwijs Roermond", gemeente="Roermond",
        gevraagd_jaar=2025, sbi_code="85311",
    )
    scores = []
    for duo_jaar in (2025, 2024):
        document = bouw_duo_bron(
            context, [vestiging], [vestiging],
            {"23HH": DuoPersoneelswaarde(
                instellingscode="23HH", jaar=duo_jaar, aantal_personen=35,
            )},
            "https://duo.nl/personeel-vo.xlsx",
        )
        scores.append(rank_bronnen([valideer_bron(document)])[0].ranking_score)

    assert scores[0] > scores[1]


def test_meerdere_instellingscodes_worden_niet_opgeteld():
    matches = [
        _vestiging(),
        _vestiging(
            instellingscode="04DS",
            vestigingscode="04DS00",
            naam="Gymnasium van de Trevianum Scholengroep",
        ),
    ]
    waarden = lees_personeelswaarden(
        _personeelsbestand([("01MO", 219, 225), ("04DS", 70, 72)]),
        {"01MO", "04DS"},
        2025,
    )

    bron = bouw_duo_bron(
        QueryContext(
            naam="Trevianum Scholengroep",
            gemeente="Sittard-Geleen",
            gevraagd_jaar=2025,
            sbi_code="85202",
        ),
        matches,
        matches,
        waarden,
        "https://duo.nl/personeel-vo.xlsx",
    )

    assert bron is not None
    assert bron.wp_gevonden is None
    assert bron.scope_class == "limburg"
    assert "niet opgeteld" in bron.bewijsfragment
    assert bron.raw_data["waarden_per_instelling"] == {
        "01MO": 225,
        "04DS": 72,
    }


@pytest.mark.asyncio
async def test_gestructureerde_duo_bron_heeft_geen_llm_review_nodig():
    vestiging = _vestiging(
        instellingscode="23HH",
        naam="Praktijkonderwijs Roermond",
        gemeente="Roermond",
        plaats="Roermond",
    )
    bron = bouw_duo_bron(
        QueryContext(
            naam="Praktijkonderwijs Roermond",
            gemeente="Roermond",
            gevraagd_jaar=2025,
        ),
        [vestiging],
        [vestiging],
        lees_personeelswaarden(
            _personeelsbestand([("23HH", 33, 35)]), {"23HH"}, 2025,
        ),
        "https://duo.nl/personeel-vo.xlsx",
    )

    validatie = await IntelligentSourceReviewer().review(
        QueryContext(naam="Praktijkonderwijs Roermond"), bron,
    )

    assert validatie.is_afgewezen is False
    assert validatie.is_officieel is True
    assert validatie.validaties["gestructureerde_duo_bron"] is True
    assert "duo_definitie_wijkt_af_van_wp" in validatie.waarschuwingen


def test_onderwijsgroepen_testset_bevat_alle_belangrijke_scopegevallen():
    pad = Path(__file__).resolve().parents[1] / "data" / "onderwijsgroepen_testset.csv"
    with pad.open(encoding="utf-8") as bestand:
        cases = list(csv.DictReader(bestand))

    assert len(cases) >= 7
    assert {case["verwachte_scope"] for case in cases} >= {
        "vestiging", "limburg", "instelling", "onbekend",
    }
    assert any(
        case["verwachte_uitkomst"] == "context_meerdere_instellingen"
        for case in cases
    )
