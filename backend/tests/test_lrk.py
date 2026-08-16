"""LRK-koppeling: koppelt op vestigingsnummer/KvK/naam, nooit op capaciteit."""
import pytest

from app.research.lrk import (
    bouw_lrk_bron,
    lees_locaties,
    vind_locaties,
    vind_lrk_bron,
)
from app.research.query_planner import QueryContext


_KOP = (
    "lrk_id;type_oko;actuele_naam_oko;aantal_kindplaatsen;status;"
    "opvanglocatie_woonplaats;verantwoordelijke_gemeente;naam_houder;"
    "kvk_nummer_houder;vestigingsnummer_houder"
)


def _csv(*rijen: str) -> bytes:
    return ("\n".join([_KOP, *rijen])).encode("utf-8")


BESTAND = _csv(
    "1;KDV;Hoera Kessel;40;Ingeschreven;Kessel;Peel en Maas;Stichting Hoera kindercentra;11111111;000011112222",
    "2;BSO;Hoera Baarlo;30;Ingeschreven;Baarlo;Peel en Maas;Stichting Hoera kindercentra;11111111;000011112222",
    "3;KDV;Hoera Venlo;25;Ingeschreven;Venlo;Venlo;Stichting Hoera kindercentra;11111111;000011112222",
    # Gastouderopvang: een gastouder is geen medewerker van de houder.
    "4;VGO;Gastouder Jansen;6;Ingeschreven;Kessel;Peel en Maas;Stichting Hoera kindercentra;11111111;000011112222",
    # Uitgeschreven locatie telt niet mee.
    "5;KDV;Hoera Oud;20;Uitgeschreven;Kessel;Peel en Maas;Stichting Hoera kindercentra;11111111;000011112222",
    # Andere houder, deels overlappende naam.
    "6;KDV;Flow Sittard;35;Ingeschreven;Sittard;Sittard-Geleen;Stichting Flow Kinderopvang;22222222;000033334444",
    "7;KDV;Flow Zorgcentrum;15;Ingeschreven;Sittard;Sittard-Geleen;Flow Zorg B.V.;33333333;000055556666",
    # Twee houders met dezelfde eigennaam in verschillende gemeenten.
    "8;KDV;Nest Horst;50;Ingeschreven;Horst;Horst aan de Maas;B.V. 't Nest Kinderopvang Horst;44444444;000077778888",
    "9;KDV;Nest Venray;45;Ingeschreven;Venray;Venray;B.V. 't Nest Kinderopvang Venray;55555555;000099990000",
)


def _locaties():
    return lees_locaties(BESTAND)


def test_leest_alleen_ingeschreven_locaties():
    locaties = _locaties()
    assert len(locaties) == 8, "de uitgeschreven locatie hoort niet mee te tellen"
    assert all(item.status == "Ingeschreven" for item in locaties)


def test_gastouderopvang_telt_niet_mee_voor_de_houder():
    """Een gastouder is een zelfstandige aan huis, geen medewerker."""
    context = QueryContext(naam="Stichting Hoera kindercentra", gemeente="Peel en Maas")
    treffers = vind_locaties(context, _locaties())

    assert {item.type_oko for item in treffers} == {"KDV", "BSO"}
    assert len(treffers) == 3


def test_koppelt_bij_voorkeur_op_vestigingsnummer():
    """Een nummer is een identiteit, een naam een gelijkenis."""
    context = QueryContext(
        naam="Totaal Andere Schrijfwijze", vestigingsnummer="000011112222",
    )
    treffers = vind_locaties(context, _locaties())

    assert len(treffers) == 3
    assert {item.naam_houder for item in treffers} == {"Stichting Hoera kindercentra"}


def test_koppelt_op_kvk_als_vestigingsnummer_ontbreekt():
    context = QueryContext(naam="Onherkenbaar", kvk_nummer="22222222")
    treffers = vind_locaties(context, _locaties())

    assert {item.naam_houder for item in treffers} == {"Stichting Flow Kinderopvang"}


def test_naammatch_negeert_volgorde_en_sectorwoorden():
    """"Kinderopvang Flow" tegenover "Stichting Flow Kinderopvang".

    De monitoringlijst heeft geen KvK- of vestigingsnummers, dus dit pad draagt
    daar het hele register.
    """
    context = QueryContext(naam="Kinderopvang Flow", gemeente="Sittard-Geleen")
    treffers = vind_locaties(context, _locaties())

    assert {item.naam_houder for item in treffers} == {"Stichting Flow Kinderopvang"}


def test_naammatch_koppelt_geen_gedeeltelijke_gelijkenis():
    """"Flow Zorg B.V." is een andere organisatie dan "Flow Kinderopvang"."""
    context = QueryContext(naam="Flow", gemeente="Sittard-Geleen")

    # "flow" zit in twee verschillende houders → fail-closed.
    assert vind_locaties(context, _locaties()) == []


def test_gemeente_ontwart_twee_houders_met_dezelfde_eigennaam():
    context = QueryContext(
        naam="Stichting Kinderopvang 't Nest", gemeente="Horst aan de Maas",
    )
    treffers = vind_locaties(context, _locaties())

    assert {item.naam_houder for item in treffers} == {
        "B.V. 't Nest Kinderopvang Horst",
    }


def test_zonder_onderscheidende_gemeente_blijft_het_leeg():
    context = QueryContext(naam="Stichting Kinderopvang 't Nest", gemeente="Venlo")

    assert vind_locaties(context, _locaties()) == []


def test_bron_levert_nooit_een_wp_waarde():
    """Kindplaatsen zijn dagcapaciteit, geen werkzame personen.

    De omrekening loopt via de beroepskracht-kindratio en de deeltijdfactor en
    is niet gekalibreerd (geen kinderopvangorganisatie in de testset). Een
    proportionele schatting mag hier dus niet als WP-cijfer binnenkomen.
    """
    context = QueryContext(naam="Stichting Hoera kindercentra", gemeente="Peel en Maas")
    bron = bouw_lrk_bron(context, vind_locaties(context, _locaties()))

    assert bron is not None
    assert bron.wp_gevonden is None
    assert bron.eenheid is None
    assert "geen werkzame personen" in bron.bewijsfragment
    assert bron.raw_data["kindplaatsen_totaal"] == 95
    assert bron.raw_data["aantal_locaties"] == 3
    assert bron.raw_data["aantal_locaties_eigen_gemeente"] == 2


def test_scope_volgt_de_gemeenten_van_de_locaties():
    alle = _locaties()

    # Alleen in de eigen gemeente.
    enkel = QueryContext(naam="Stichting Flow Kinderopvang", gemeente="Sittard-Geleen")
    assert bouw_lrk_bron(enkel, vind_locaties(enkel, alle)).scope_class == "vestiging"

    # Meerdere Limburgse gemeenten.
    breed = QueryContext(naam="Stichting Hoera kindercentra", gemeente="Peel en Maas")
    assert bouw_lrk_bron(breed, vind_locaties(breed, alle)).scope_class == "limburg"


def test_bron_is_leeg_zonder_treffers():
    assert bouw_lrk_bron(QueryContext(naam="Bakkerij Voncken"), []) is None


@pytest.mark.asyncio
async def test_netwerkfout_levert_geen_exception(monkeypatch):
    """Een onbereikbaar register mag de researchrun niet laten mislukken."""
    async def _stuk():
        raise RuntimeError("LRK onbereikbaar")

    monkeypatch.setattr("app.research.lrk._laad_locaties", _stuk)
    assert await vind_lrk_bron(QueryContext(naam="Stichting Hoera")) is None
