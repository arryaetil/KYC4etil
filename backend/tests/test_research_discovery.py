"""Discoverytests: queryplanning, URL-normalisatie en providerfusie."""
from types import SimpleNamespace

import pytest

from app.research.query_planner import (
    QueryContext,
    plan_queries,
    vereenvoudigde_zoeknaam,
)
from app.research.service import _dedupliceer_kandidaten
from app.research.types import SearchResult
from app.research.urls import canonicaliseer_url


def test_queryplanner_dekt_website_documenten_en_recente_media():
    queries = plan_queries(QueryContext(
        naam="Voorbeeld Zorg",
        gevraagd_jaar=2025,
        website_url="https://www.voorbeeldzorg.nl",
        gemeente="Heerlen",
    ))

    assert any(q.pad == "website" and "site:voorbeeldzorg.nl" in q.query for q in queries)
    assert any(q.pad == "document" and "jaarverslag 2025" in q.query for q in queries)
    assert any(q.pad == "document" and "2026" in q.query for q in queries)
    assert any(q.pad == "media" and "nieuws" in q.query for q in queries)
    site_document_index = next(
        index for index, query in enumerate(queries)
        if query.pad == "document" and "site:voorbeeldzorg.nl" in query.query
    )
    open_document_index = next(
        index for index, query in enumerate(queries)
        if query.pad == "document" and "site:" not in query.query
    )
    assert site_document_index < open_document_index
    assert len({q.query for q in queries}) == len(queries)


def test_administratieve_subwoning_krijgt_zoekalias_op_eigennaam():
    assert vereenvoudigde_zoeknaam("Groepswoning Piushof B 2") == "Piushof"

    queries = plan_queries(QueryContext(
        naam="Groepswoning Piushof B 2",
        gemeente="Venlo",
        gevraagd_jaar=2025,
    ))

    # Eén gerichte aliasquery op de eigennaam; de eerdere variant met
    # aanhalingstekens is vervallen omdat exacte-frasezoeken de trefkans juist
    # verlaagt (gemeten 2/10 tegenover 8/10).
    assert any(
        query.pad == "website"
        and query.query.startswith("Piushof ")
        and '"' not in query.query
        and query.doel.startswith("openbare bronnen")
        for query in queries
    )


def test_normale_bedrijfsnaam_wordt_niet_onnodig_vereenvoudigd():
    assert vereenvoudigde_zoeknaam("Mondriaan") is None


def test_canonicaliseer_url_verwijdert_tracking_fragment_en_www():
    assert canonicaliseer_url(
        "HTTPS://WWW.Example.nl/team/?utm_source=test&id=12#medewerkers"
    ) == "https://example.nl/team?id=12"


def test_canonicaliseer_url_dedupliceert_http_en_https_als_dezelfde_webbron():
    assert canonicaliseer_url(
        "http://www.dezorggroep.nl/"
    ) == canonicaliseer_url(
        "https://dezorggroep.nl"
    )


def test_canonicaliseer_url_verwijdert_srsltid_tracking_parameter():
    """
    Regressie: Poulissen Audio Video Center leverde in de VR-testbatch
    (batch f575fc9c) dezelfde teampagina en homepage elk 2x op, uitsluitend
    door een wisselend Google-Shopping-trackingparameter.
    """
    assert canonicaliseer_url(
        "https://www.poulissen.nl/pages/ons-team"
        "?srsltid=AfmBOor_zF8C7v1ti24dIIr3XjeO13ZfCQKOGaaUmKICzkk28bpMT2h7"
    ) == canonicaliseer_url(
        "https://www.poulissen.nl/pages/ons-team"
        "?srsltid=AfmBOorFbsBUZdwOsQ7mAJfjB9zBkreyO4e-JoMvMUJ6BH-N_L3ljLAt"
    )
    assert canonicaliseer_url(
        "https://www.poulissen.nl/?srsltid=AfmBOoogJXaJVF-4kYOxe07S_6PbPTW5sF9OdNPBJbYi15zqKZIcRsjh"
    ) == canonicaliseer_url("https://www.poulissen.nl/")


def test_canonicaliseer_url_dedupliceert_taalvarianten_van_dezelfde_pagina():
    """
    Regressie: DSM-Firmenich en Koninklijke BAM leverden in dezelfde testbatch
    een Engelse en Nederlandse variant van precies dezelfde pagina als twee
    losse kandidaten op (zie docs/OPENSTAANDE_OBSERVATIES_RESEARCH_EN_UI.md §4).
    """
    assert canonicaliseer_url(
        "https://our-company.dsm-firmenich.com/en/our-company/ventures/team.html"
    ) == canonicaliseer_url(
        "https://our-company.dsm-firmenich.com/nl-nl/our-company/ventures/team.html"
    )
    assert canonicaliseer_url("https://www.bam.com/") == canonicaliseer_url(
        "https://www.bam.com/nl"
    )


def test_canonicaliseer_url_laat_landenpad_dat_geen_taalcode_is_ongemoeid():
    """Een pad als "/us/..." is een landensectie, geen taalvariant-prefix."""
    assert canonicaliseer_url(
        "https://example.com/us/investor-relations"
    ) != canonicaliseer_url("https://example.com/investor-relations")


def test_parallelle_paden_worden_voor_opslag_canoniek_gededupliceerd():
    specialist = SimpleNamespace(document=SimpleNamespace(
        url="https://www.mondriaan.eu/jaarverslag-2024.pdf",
    ))
    breed_zoekpad = SimpleNamespace(document=SimpleNamespace(
        url="https://mondriaan.eu/jaarverslag-2024.pdf?utm_source=search",
    ))

    uniek = _dedupliceer_kandidaten([specialist, breed_zoekpad])

    assert uniek == [
        (specialist, "https://mondriaan.eu/jaarverslag-2024.pdf"),
    ]




# --- zoekopdrachten mogen niet verwateren ---

def test_geplande_queries_stapelen_geen_synoniemen():
    """Gemeten op de jaarverslagzoeker: een query met de naam tussen
    aanhalingstekens plus een stapel synoniemen scoorde 2/10, een beknopte
    variant 8/10. De index matcht dan op de trefwoorden in plaats van op de
    organisatie. query_planner bouwde queries met hetzelfde patroon."""
    from app.research.query_planner import QueryContext, plan_queries

    queries = plan_queries(QueryContext(
        naam="Stichting Pergamijn", gevraagd_jaar=2025,
        website_url="https://www.pergamijn.org/", gemeente="Sittard",
    ))

    synoniemgroepen = (
        {"medewerkers", "personeel", "werknemers"},
        {"jaarverslag", "jaarrekening", "bestuursverslag", "jaarverantwoording"},
        {"reorganisatie", "overname", "ontslag", "uitbreiding"},
    )
    for q in queries:
        woorden = set(q.query.lower().replace('"', " ").split())
        for groep in synoniemgroepen:
            overlap = woorden & groep
            assert len(overlap) <= 2, f"{q.query!r} stapelt {sorted(overlap)}"


def test_geplande_queries_zetten_de_naam_niet_tussen_aanhalingstekens():
    from app.research.query_planner import QueryContext, plan_queries

    queries = plan_queries(QueryContext(
        naam="Stichting Pergamijn", gevraagd_jaar=2025, gemeente="Sittard",
    ))
    for q in queries:
        assert '"' not in q.query, f"exacte-frasezoekopdracht: {q.query!r}"


def test_geplande_queries_herhalen_het_jaartal_niet():
    from app.research.query_planner import QueryContext, plan_queries

    queries = plan_queries(QueryContext(
        naam="Gemeente Maastricht", gevraagd_jaar=2025,
        website_url="https://www.gemeentemaastricht.nl/",
    ))
    for q in queries:
        assert q.query.count("2025") <= 1, f"jaartal herhaald: {q.query!r}"


def test_documentqueries_kennen_ook_jaarstukken():
    """Gemeenten en provincies publiceren jaarstukken, geen jaarverslag."""
    from app.research.query_planner import QueryContext, plan_queries

    queries = plan_queries(QueryContext(naam="Gemeente Venlo", gevraagd_jaar=2025))
    documenten = " ".join(q.query.lower() for q in queries if q.pad == "document")
    assert "jaarstukken" in documenten
