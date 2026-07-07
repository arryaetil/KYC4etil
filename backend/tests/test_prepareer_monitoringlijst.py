"""Tests voor organisatie-deduplicatie van het watchlist-prep-script."""
from scripts.prepareer_monitoringlijst import (
    dedupliceer_organisaties,
    organisaties_uit_organisatie_tabblad,
    organisaties_uit_vestiging_tabblad,
)


def test_groepeert_vestigingen_op_cbnr_en_kiest_cber_naam():
    rijen = [
        {"vestnr": "1", "naam": "Stichting Dichterbij", "cbnr": "001245", "cb-er": "Stichting Dichterbij"},
        {"vestnr": "2", "naam": "Stichting Dichterbij - Locatie A", "cbnr": "001245", "cb-er": ""},
        {"vestnr": "3", "naam": "Stichting Dichterbij - Locatie B", "cbnr": "001245", "cb-er": ""},
    ]

    organisaties = organisaties_uit_vestiging_tabblad(rijen)

    assert organisaties == [{"naam": "Stichting Dichterbij", "cb_er": "001245"}]


def test_losse_vestiging_wordt_eigen_organisatie():
    rijen = [
        {"vestnr": "1", "naam": "Deloitte Tax & Legal B.V.", "cbnr": "000000", "cb-er": ""},
    ]

    organisaties = organisaties_uit_vestiging_tabblad(rijen)

    assert organisaties == [{"naam": "Deloitte Tax & Legal B.V.", "cb_er": None}]


def test_fallback_naar_kortste_naam_zonder_ingevulde_cber():
    rijen = [
        {"vestnr": "1", "naam": "Voorbeeld Groep - Vestiging Noord", "cbnr": "002000", "cb-er": ""},
        {"vestnr": "2", "naam": "Voorbeeld Groep", "cbnr": "002000", "cb-er": ""},
    ]

    organisaties = organisaties_uit_vestiging_tabblad(rijen)

    assert organisaties == [{"naam": "Voorbeeld Groep", "cb_er": "002000"}]


def test_organisatie_tabblad_is_al_organisatie_niveau():
    rijen = [
        {"naam cb-er": "CEVA Logistics", "cbnr": "002441", "vestnr": ""},
        {"naam cb-er": "Losse Stichting X", "cbnr": "000000", "vestnr": ""},
    ]

    organisaties = organisaties_uit_organisatie_tabblad(rijen)

    assert organisaties == [
        {"naam": "CEVA Logistics", "cb_er": "002441"},
        {"naam": "Losse Stichting X", "cb_er": None},
    ]


def test_dedupliceert_over_meerdere_tabbladen_op_cb_er():
    tabblad_1 = [{"naam": "Stichting Dichterbij", "cb_er": "001245"}]
    tabblad_2 = [
        {"naam": "Stichting Dichterbij", "cb_er": "001245"},
        {"naam": "CEVA Logistics", "cb_er": "002441"},
    ]

    organisaties = dedupliceer_organisaties(tabblad_1, tabblad_2)

    assert organisaties == [
        {"naam": "Stichting Dichterbij", "cb_er": "001245"},
        {"naam": "CEVA Logistics", "cb_er": "002441"},
    ]


def test_dedupliceert_losse_vestigingen_op_naam():
    tabblad_1 = [{"naam": "Deloitte Tax & Legal B.V.", "cb_er": None}]
    tabblad_2 = [{"naam": "Deloitte Tax & Legal B.V.", "cb_er": None}]

    organisaties = dedupliceer_organisaties(tabblad_1, tabblad_2)

    assert organisaties == [{"naam": "Deloitte Tax & Legal B.V.", "cb_er": None}]
