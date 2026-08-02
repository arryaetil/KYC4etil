"""Unit tests voor de kernlogica: strategie, schatting, reconciliatie, confidence."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline.confidence import bereken_confidence
from app.pipeline.reconcile import (Strategie, bepaal_strategie,
                                    proportionele_schatting, reconcilieer,
                                    signaleer_afwijkende_extra_bronnen)
from app.providers.base import AgentFinding


def finding(wp=10, bron="website", zekerheid="hoog", limburg=True, fte=False,
            totaal_meerdere=False, peilmoment="2026", context=None, url="https://x"):
    return AgentFinding(wp_gevonden=wp, context=context or f"{wp} medewerkers",
                        zekerheid=zekerheid, reden="t",
                        bron_url=url, bron_type=bron,
                        is_totaal_meerdere_vestigingen=totaal_meerdere,
                        is_limburg_specifiek=limburg, is_fte=fte, peilmoment=peilmoment)


# --- strategie ---

def test_strategie_single_locatie():
    assert bepaal_strategie(False, 1, 1) == Strategie.DIRECT_VERWERKEN

def test_strategie_alles_in_limburg():
    assert bepaal_strategie(False, 25, 25) == Strategie.DIRECT_VERWERKEN

def test_strategie_klein_multi():
    assert bepaal_strategie(False, 3, 1) == Strategie.GERICHTE_CHAT

def test_strategie_groot_multi():
    assert bepaal_strategie(False, 60, 4) == Strategie.VOLLEDIGE_CHAT_OF_BELLIJST

def test_strategie_lookup_failed():
    assert bepaal_strategie(True, None, None) == Strategie.VOLLEDIGE_CHAT_OF_BELLIJST


# --- proportionele schatting (v1.0-bug: crash op None) ---

def test_schatting_none_crasht_niet():
    assert proportionele_schatting(None, 5, 2) == (None, 0.0)

def test_schatting_berekening():
    schatting, penalty = proportionele_schatting(17000, 400, 15)
    assert schatting == 638
    assert penalty == 0.30  # gemaximeerd

def test_schatting_kleine_n():
    _, penalty = proportionele_schatting(100, 2, 1)
    assert penalty == pytest.approx(0.10)


# --- reconciliatie ---

def test_reconciliatie_geen_bronnen():
    r = reconcilieer(None, None, 1, 1)
    assert r.wp_kandidaat is None and r.n_bronnen == 0

def test_reconciliatie_bronnen_bevestigen():
    r = reconcilieer(finding(wp=100), finding(wp=105, bron="jaarverslag"), 1, 1)
    assert r.bronnen_consistent and r.wp_kandidaat == 100

def test_reconciliatie_conflict_single_locatie_website_wint():
    r = reconcilieer(finding(wp=10), finding(wp=500, bron="jaarverslag"), 1, 1)
    assert r.wp_kandidaat == 10 and not r.bronnen_consistent

def test_reconciliatie_multi_locatie_schatting():
    r = reconcilieer(None, finding(wp=17000, bron="jaarverslag", limburg=False), 400, 15)
    assert r.is_schatting and r.wp_kandidaat == 638

def test_reconciliatie_landelijk_totaal_zonder_vestigingscount_geen_kandidaat():
    r = reconcilieer(None, finding(wp=6158, bron="jaarverslag", limburg=False), None, None)
    assert r.finding is None
    assert r.wp_kandidaat is None
    assert not r.is_schatting

def test_reconciliatie_weigert_vacaturepagina_als_wp_kandidaat():
    r = reconcilieer(
        finding(wp=4, bron="media", url="https://jobs.ikea.com/nl/plaats/heerlen-jobs/4",
                context="Heerlen: 4"),
        None, 1, 1,
    )
    assert r.finding is None
    assert r.wp_kandidaat is None
    assert "vacature/jobs-pagina" in r.reden

def test_reconciliatie_weigert_context_die_wp_getal_niet_ondersteunt():
    r = reconcilieer(
        finding(wp=6500, bron="media", context="650 voltijdsbanen bij BAM"),
        None, 1, 1,
    )
    assert r.finding is None
    assert r.wp_kandidaat is None
    assert "context ondersteunt gekozen WP-getal" in r.reden

def test_reconciliatie_accepteert_website_zonder_gepersistenteerde_context():
    r = reconcilieer(
        AgentFinding(
            wp_gevonden=5, context=None, zekerheid="hoog", reden="team-pagina",
            bron_url="https://example.test/over-ons", bron_type="website",
            is_limburg_specifiek=True,
        ),
        None, 1, 1,
    )
    assert r.wp_kandidaat == 5

def test_reconciliatie_weigert_website_context_die_enkel_de_vraag_herhaalt():
    """Regressie: BAM/Zuyderland gaven een 'context' die feitelijk gewoon de
    extractievraag herhaalde ("Aantal werkzame personen bij X"), zonder citaat of
    getal — dat mag niet als kandidaat doorglippen, ook al is bron_type website."""
    r = reconcilieer(
        AgentFinding(
            wp_gevonden=13200, context="Aantal werkzame personen bij Koninklijke BAM Groep N.V.",
            zekerheid="hoog", reden="t",
            bron_url="https://www.bam.com/nl/contact/informatie-over-bam-locaties",
            bron_type="website", is_limburg_specifiek=True,
        ),
        None, None, None,
    )
    assert r.wp_kandidaat is None
    assert "context ondersteunt gekozen WP-getal" in r.reden

def test_reconciliatie_accepteert_website_context_zonder_letterlijk_getal():
    """Een naamlijst (bv. 'Anne, Maral, Heidi, Monique') noemt het aantal niet
    letterlijk, maar is wél een echt citaat -- mag niet worden afgestraft."""
    r = reconcilieer(
        AgentFinding(
            wp_gevonden=4, context="Medewerkers in deze vestiging: Anne, Maral, Heidi, Monique",
            zekerheid="hoog", reden="team-pagina",
            bron_url="https://hallux.nl/vestigingen/limburg/roermond/",
            bron_type="website", is_limburg_specifiek=True,
        ),
        None, None, None,
    )
    assert r.wp_kandidaat == 4

def test_reconciliatie_weigert_media_zonder_gepersistenteerde_context():
    r = reconcilieer(
        AgentFinding(
            wp_gevonden=5, context=None, zekerheid="hoog", reden="zoekresultaat",
            bron_url="https://example.test/over-ons", bron_type="media",
            is_limburg_specifiek=True,
        ),
        None, 1, 1,
    )
    assert r.wp_kandidaat is None

def test_reconciliatie_weigert_onwaarschijnlijk_jaarverslag_documenttype():
    r = reconcilieer(
        finding(
            wp=5, bron="jaarverslag",
            url="https://example.test/uploads/AVG-verklaring-2025.pdf",
            context="5 medewerkers",
        ),
        None, 1, 1,
    )
    assert r.wp_kandidaat is None
    assert "ander documenttype" in r.reden

def test_reconciliatie_weigert_juridische_holding_shell_als_vestiging():
    r = reconcilieer(
        finding(
            wp=2, bron="jaarverslag", fte=True,
            url="https://example.test/holding-bv-annual-report-fy25.pdf",
            context="The average number of staff employed by the Company, converted into full-time equivalents, amounted to 2, of which 0 were employed outside the Netherlands.",
        ),
        None, 1, 1,
    )
    assert r.wp_kandidaat is None
    assert "holding/shell" in r.reden

def test_reconciliatie_accepteert_context_met_aantoonbare_optelsom():
    r = reconcilieer(
        finding(wp=13, context="Ons team: 3 huisartsen, 6 assistentes, 2 praktijkondersteuners en 2 POH-GGZ."),
        None, 1, 1,
    )
    assert r.wp_kandidaat == 13


# --- confidence ---

def kwargs(**over):
    base = dict(n_bronnen=1, bronnen_consistent=False, peiljaar=2026)
    base.update(over)
    return base

def test_confidence_single_locatie_website_is_groen():
    s = bereken_confidence(finding(), **kwargs())
    assert s.label == "hoog" and s.score >= 0.80

def test_confidence_media_bron_wordt_niet_groen():
    s = bereken_confidence(finding(bron="media", zekerheid="hoog"), **kwargs())
    assert s.label != "hoog"
    assert s.score < 0.80

def test_confidence_schatting_nooit_groen():
    s = bereken_confidence(finding(bron="jaarverslag", limburg=False), **kwargs(),
                           is_schatting=True, schatting_penalty=0.30)
    assert s.label != "hoog" and s.score < 0.50

def test_confidence_llm_laag_is_rood():
    s = bereken_confidence(finding(zekerheid="laag"), **kwargs())
    assert s.label == "laag"

def test_confidence_llm_middel_is_geel():
    s = bereken_confidence(finding(zekerheid="middel"), **kwargs())
    assert s.label == "middel"

def test_confidence_fte_penalty():
    met = bereken_confidence(finding(fte=True), **kwargs())
    zonder = bereken_confidence(finding(fte=False), **kwargs())
    assert zonder.score > met.score

def test_confidence_breakdown_aanwezig():
    s = bereken_confidence(finding(), **kwargs())
    assert set(s.breakdown) >= {"zekerheid_llm", "base_score", "penalties", "bonuses"}


# --- reviewer-signaal (informatief, verandert nooit de score) ---

def test_signaal_geeft_niets_bij_geen_afwijkende_bronnen():
    extra = [finding(wp=21, url="https://a"), finding(wp=20, url="https://b")]
    assert signaleer_afwijkende_extra_bronnen(21, extra) is None


def test_signaal_markeert_sterk_afwijkende_bron():
    extra = [finding(wp=13, url="https://andere-praktijk.test")]
    signaal = signaleer_afwijkende_extra_bronnen(21, extra)
    assert signaal is not None
    assert "andere-praktijk.test" in signaal
    assert "13" in signaal


def test_signaal_geeft_niets_zonder_kandidaat_of_extra_bronnen():
    assert signaleer_afwijkende_extra_bronnen(None, [finding(wp=13)]) is None
    assert signaleer_afwijkende_extra_bronnen(21, []) is None


# --- identity/scope-classificatie wordt opgeslagen op AgentResult ---

@pytest.mark.asyncio
async def test_verwerk_company_slaat_identity_en_scope_classificatie_op():
    from app.models import AgentResult
    from app.pipeline.runner import verwerk_company
    from app.providers.base import AgentFinding

    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    batch = MagicMock(); batch.id = "batch-1"; batch.jaar = 2025
    company = MagicMock()
    company.id = "comp-1"; company.naam = "Salon Handmade"
    company.adres = "Langstraat 8"; company.gemeente = "Weert"

    w_finding = AgentFinding(
        wp_gevonden=3, context="Boek bij een van onze 3 medewerkers.", zekerheid="hoog",
        reden="mock", bron_url="https://www.salonhandmade.nl/afspraak", bron_type="website",
        is_limburg_specifiek=True,
    )
    mock_lookup = MagicMock(); mock_lookup.lookup = AsyncMock(return_value=None)
    mock_lookup.locations = AsyncMock(return_value=MagicMock(count_nl=1, count_lb=1, bron="mock"))
    mock_lookup.scrape_email = AsyncMock(return_value=None)
    mock_website = MagicMock()
    mock_website.run = AsyncMock(return_value=w_finding)
    mock_website.extra_bronnen = AsyncMock(return_value=[])
    mock_jaarverslag = MagicMock(); mock_jaarverslag.run = AsyncMock(return_value=None)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(return_value=("exact_entity", "vestiging"))

    with patch(
        "app.pipeline.runner.get_providers",
        return_value=(mock_lookup, mock_website, mock_jaarverslag, mock_classifier),
    ):
        await verwerk_company(db, company, batch)

    website_ar = next(
        call.args[0] for call in db.add.call_args_list
        if isinstance(call.args[0], AgentResult) and call.args[0].agent_type == "website"
    )
    assert website_ar.identity_class == "exact_entity"
    assert website_ar.scope_class == "vestiging"
    mock_classifier.classify.assert_awaited()


@pytest.mark.asyncio
async def test_verwerk_company_geeft_mismatch_door_voor_cross_company_website():
    from app.models import AgentResult
    from app.pipeline.runner import verwerk_company
    from app.providers.base import AgentFinding

    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    batch = MagicMock(); batch.id = "batch-2"; batch.jaar = 2025
    company = MagicMock()
    company.id = "comp-2"; company.naam = "Salon Handmade"
    company.adres = "Langstraat 8"; company.gemeente = "Weert"

    w_finding = AgentFinding(
        wp_gevonden=25, context="Wij hebben 25 medewerkers in dienst.", zekerheid="hoog",
        reden="mock", bron_url="https://www.andere-onderneming.nl/over-ons", bron_type="website",
        is_limburg_specifiek=True,
    )
    mock_lookup = MagicMock(); mock_lookup.lookup = AsyncMock(return_value=None)
    mock_lookup.locations = AsyncMock(return_value=MagicMock(count_nl=1, count_lb=1, bron="mock"))
    mock_lookup.scrape_email = AsyncMock(return_value=None)
    mock_website = MagicMock()
    mock_website.run = AsyncMock(return_value=w_finding)
    mock_website.extra_bronnen = AsyncMock(return_value=[])
    mock_jaarverslag = MagicMock(); mock_jaarverslag.run = AsyncMock(return_value=None)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(return_value=("mismatch", "unknown"))

    with patch(
        "app.pipeline.runner.get_providers",
        return_value=(mock_lookup, mock_website, mock_jaarverslag, mock_classifier),
    ):
        await verwerk_company(db, company, batch)

    website_ar = next(
        call.args[0] for call in db.add.call_args_list
        if isinstance(call.args[0], AgentResult) and call.args[0].agent_type == "website"
    )
    assert website_ar.identity_class == "mismatch"


@pytest.mark.asyncio
async def test_verwerk_company_geeft_same_brand_or_group_door_voor_filiaal_jaarverslag():
    from app.models import AgentResult
    from app.pipeline.runner import verwerk_company
    from app.providers.base import AgentFinding

    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    batch = MagicMock(); batch.id = "batch-3"; batch.jaar = 2025
    company = MagicMock()
    company.id = "comp-3"; company.naam = "Jumbo Sittard"
    company.adres = "Markt 1"; company.gemeente = "Sittard"

    j_finding = AgentFinding(
        wp_gevonden=1200, context="Jumbo Supermarkten telt landelijk 1200 medewerkers.",
        zekerheid="middel", reden="mock",
        bron_url="https://www.jumbo.com/jaarverslag", bron_type="jaarverslag",
        is_limburg_specifiek=False,
    )
    mock_lookup = MagicMock(); mock_lookup.lookup = AsyncMock(return_value=None)
    mock_lookup.locations = AsyncMock(return_value=MagicMock(count_nl=1, count_lb=1, bron="mock"))
    mock_lookup.scrape_email = AsyncMock(return_value=None)
    mock_website = MagicMock()
    mock_website.run = AsyncMock(return_value=None)
    mock_website.extra_bronnen = AsyncMock(return_value=[])
    mock_jaarverslag = MagicMock(); mock_jaarverslag.run = AsyncMock(return_value=j_finding)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(return_value=("same_brand_or_group", "concern"))

    with patch(
        "app.pipeline.runner.get_providers",
        return_value=(mock_lookup, mock_website, mock_jaarverslag, mock_classifier),
    ):
        await verwerk_company(db, company, batch)

    jaarverslag_ar = next(
        call.args[0] for call in db.add.call_args_list
        if isinstance(call.args[0], AgentResult) and call.args[0].agent_type == "jaarverslag"
    )
    assert jaarverslag_ar.identity_class == "same_brand_or_group"


@pytest.mark.asyncio
async def test_verwerk_company_classificatie_fout_valt_terug_op_unknown_en_faalt_niet():
    """Finding 1: een falende classify() (bv. transiente LLM-fout in live-modus) mag de
    hele bedrijfsverwerking niet laten crashen — informatief-only, nooit een harde gate."""
    from app.models import AgentResult, PipelineRun
    from app.pipeline.runner import verwerk_company
    from app.providers.base import AgentFinding

    db = MagicMock()
    db.add = MagicMock()
    db.flush = MagicMock()
    batch = MagicMock(); batch.id = "batch-4"; batch.jaar = 2025
    company = MagicMock()
    company.id = "comp-4"; company.naam = "Salon Handmade"
    company.adres = "Langstraat 8"; company.gemeente = "Weert"

    w_finding = AgentFinding(
        wp_gevonden=3, context="Boek bij een van onze 3 medewerkers.", zekerheid="hoog",
        reden="mock", bron_url="https://www.salonhandmade.nl/afspraak", bron_type="website",
        is_limburg_specifiek=True,
    )
    mock_lookup = MagicMock(); mock_lookup.lookup = AsyncMock(return_value=None)
    mock_lookup.locations = AsyncMock(return_value=MagicMock(count_nl=1, count_lb=1, bron="mock"))
    mock_lookup.scrape_email = AsyncMock(return_value=None)
    mock_website = MagicMock()
    mock_website.run = AsyncMock(return_value=w_finding)
    mock_website.extra_bronnen = AsyncMock(return_value=[])
    mock_jaarverslag = MagicMock(); mock_jaarverslag.run = AsyncMock(return_value=None)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(side_effect=RuntimeError("LLM timeout"))

    with patch(
        "app.pipeline.runner.get_providers",
        return_value=(mock_lookup, mock_website, mock_jaarverslag, mock_classifier),
    ):
        # Mag niet raisen — anders zou verwerk_company() de hele company-verwerking
        # (reconciliatie/confidence/candidate) verliezen, precies wat Finding 1 verbiedt.
        candidate = await verwerk_company(db, company, batch)

    assert candidate is not None
    website_ar = next(
        call.args[0] for call in db.add.call_args_list
        if isinstance(call.args[0], AgentResult) and call.args[0].agent_type == "website"
    )
    assert website_ar.identity_class == "unknown"
    assert website_ar.scope_class == "unknown"

    classificatie_runs = [
        call.args[0] for call in db.add.call_args_list
        if isinstance(call.args[0], PipelineRun)
        and call.args[0].stap == "identity_scope_classificatie"
    ]
    assert len(classificatie_runs) == 1
    assert classificatie_runs[0].status == "error"


# --- kosten- en tokenregistratie in pipeline_runs ---

@pytest.mark.asyncio
async def test_verwerk_company_logt_kosten_en_tokens_op_een_totaalregel():
    """pipeline_runs.kosten_cents/tokens_* bestonden al als kolom maar werden
    nooit gevuld; alleen research_runs hield kosten bij."""
    from app.models import PipelineRun
    from app.pipeline.runner import verwerk_company
    from app.research.usage import record_provider_call, record_response_usage

    db = MagicMock()
    batch = MagicMock(); batch.id = "batch-kosten"; batch.jaar = 2026
    company = MagicMock()
    company.id = "comp-kosten"; company.naam = "Testbedrijf"
    company.adres = "Straat 1"; company.gemeente = "Weert"

    async def _website_run(*args, **kwargs):
        # Simuleer een agent die een OpenAI-call doet tijdens zijn stap.
        record_response_usage(SimpleNamespace(usage=SimpleNamespace(
            input_tokens=200_000, output_tokens=50_000)))
        return finding()

    mock_lookup = MagicMock()
    mock_lookup.lookup = AsyncMock(return_value=None)
    mock_lookup.locations = AsyncMock(return_value=MagicMock(count_nl=1, count_lb=1, bron="mock"))
    mock_lookup.scrape_email = AsyncMock(return_value=None)
    mock_website = MagicMock()
    mock_website.run = AsyncMock(side_effect=_website_run)
    mock_website.extra_bronnen = AsyncMock(return_value=[])
    mock_jaarverslag = MagicMock(); mock_jaarverslag.run = AsyncMock(return_value=None)
    mock_classifier = MagicMock()
    mock_classifier.classify = AsyncMock(return_value=("exact_entity", "vestiging"))

    with patch(
        "app.pipeline.runner.get_providers",
        return_value=(mock_lookup, mock_website, mock_jaarverslag, mock_classifier),
    ):
        await verwerk_company(db, company, batch)

    runs = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], PipelineRun)]
    totaal = next(r for r in runs if r.stap == "totaal")

    # 200k in * 0,015 + 50k uit * 0,06 = 6 cent (prijzen uit config.py)
    assert totaal.kosten_cents == 6
    assert (totaal.tokens_in, totaal.tokens_out) == (200_000, 50_000)

    # De website-stap krijgt zijn eigen tokens toegewezen, de verrijkingsstap niet.
    website_stap = next(r for r in runs if r.stap == "website_agent")
    verrijking = next(r for r in runs if r.stap == "verrijking")
    assert (website_stap.tokens_in, website_stap.tokens_out) == (200_000, 50_000)
    assert (verrijking.tokens_in, verrijking.tokens_out) == (0, 0)


@pytest.mark.asyncio
async def test_verwerk_company_telt_kosten_niet_door_van_vorige_organisatie():
    from app.models import PipelineRun
    from app.pipeline.runner import verwerk_company
    from app.research.usage import record_response_usage

    def _mocks():
        lookup = MagicMock()
        lookup.lookup = AsyncMock(return_value=None)
        lookup.locations = AsyncMock(return_value=MagicMock(count_nl=1, count_lb=1, bron="mock"))
        lookup.scrape_email = AsyncMock(return_value=None)
        website = MagicMock()
        website.extra_bronnen = AsyncMock(return_value=[])
        jaarverslag = MagicMock(); jaarverslag.run = AsyncMock(return_value=None)
        classifier = MagicMock()
        classifier.classify = AsyncMock(return_value=("exact_entity", "vestiging"))
        return lookup, website, jaarverslag, classifier

    async def _run_met_verbruik(tokens):
        async def _run(*args, **kwargs):
            record_response_usage(SimpleNamespace(usage=SimpleNamespace(
                input_tokens=tokens, output_tokens=0)))
            return finding()
        return _run

    totalen = []
    for tokens in (200_000, 400_000):
        db = MagicMock()
        batch = MagicMock(); batch.id = "b"; batch.jaar = 2026
        company = MagicMock()
        company.id = f"c-{tokens}"; company.naam = "Testbedrijf"
        company.adres = "Straat 1"; company.gemeente = "Weert"
        lookup, website, jaarverslag, classifier = _mocks()
        website.run = AsyncMock(side_effect=await _run_met_verbruik(tokens))
        with patch("app.pipeline.runner.get_providers",
                   return_value=(lookup, website, jaarverslag, classifier)):
            await verwerk_company(db, company, batch)
        runs = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], PipelineRun)]
        totalen.append(next(r for r in runs if r.stap == "totaal").tokens_in)

    assert totalen == [200_000, 400_000]


# --- actualiteit: peiljaar telt mee in de confidence ---

def test_confidence_recent_peilmoment_krijgt_geen_actualiteitspenalty():
    s = bereken_confidence(finding(peilmoment="2026"), **kwargs(peiljaar=2026))
    assert "verouderd_peilmoment" not in s.breakdown["penalties"]


def test_confidence_jaarverslag_van_vorig_jaar_wordt_niet_gestraft():
    """Een jaarverslag over jaar X verschijnt pas in X+1; één jaar verschil is
    normaal en mag de score niet drukken."""
    s = bereken_confidence(finding(peilmoment="2025"), **kwargs(peiljaar=2026))
    assert "verouderd_peilmoment" not in s.breakdown["penalties"]


def test_confidence_verouderd_peilmoment_verlaagt_de_score():
    recent = bereken_confidence(finding(peilmoment="2025"), **kwargs(peiljaar=2026))
    oud = bereken_confidence(finding(peilmoment="2019"), **kwargs(peiljaar=2026))

    assert oud.score < recent.score
    assert oud.breakdown["penalties"]["verouderd_peilmoment"] > 0


def test_confidence_onbekend_peilmoment_krijgt_geen_penalty():
    """Onbekend is niet hetzelfde als oud; daar straffen we niet op."""
    s = bereken_confidence(finding(peilmoment=None), **kwargs(peiljaar=2026))
    assert "verouderd_peilmoment" not in s.breakdown["penalties"]


def test_confidence_breakdown_toont_peilmoment_en_peiljaar():
    s = bereken_confidence(finding(peilmoment="2019"), **kwargs(peiljaar=2026))
    assert s.breakdown["peilmoment"] == "2019"
    assert s.breakdown["peiljaar"] == 2026


# --- afgekapte locatiecount van Google Places ---

def test_places_locatiecount_op_de_paginalimiet_is_een_ondergrens():
    """Google Places Text Search geeft maximaal pageSize resultaten terug. Bij
    precies dat aantal is de telling een ondergrens, geen telling — een concern
    met 400 vestigingen is niet te onderscheiden van één met 20."""
    from app.providers.base import LocationInfo

    afgekapt = LocationInfo(count_nl=20, count_lb=20, bron="places",
                            count_nl_is_ondergrens=True)
    assert afgekapt.count_nl_is_ondergrens is True
    assert LocationInfo(count_nl=3, count_lb=1, bron="places").count_nl_is_ondergrens is False


def test_strategie_nooit_direct_verwerken_bij_afgekapte_count():
    """count_lb == count_nl betekent normaal 'alles in Limburg' en dus
    auto-verwerken. Bij een afgekapte telling kan dat toeval zijn: de eerste 20
    resultaten van een landelijk concern kunnen allemaal Limburgs zijn. Dat mag
    nooit tot een groen label leiden."""
    assert bepaal_strategie(False, 20, 20) == Strategie.DIRECT_VERWERKEN
    assert bepaal_strategie(False, 20, 20, count_is_ondergrens=True) != Strategie.DIRECT_VERWERKEN


def test_strategie_afgekapte_count_gaat_naar_volledige_route():
    assert bepaal_strategie(False, 20, 3, count_is_ondergrens=True) == \
        Strategie.VOLLEDIGE_CHAT_OF_BELLIJST


def test_schatting_bij_afgekapte_count_krijgt_maximale_penalty():
    """De verhouding n_lb/n_nl is bij afkapping systematisch te hoog: de noemer
    is begrensd, de teller niet. De schatting blijft, maar met de zwaarste
    penalty zodat hij nooit als betrouwbaar leest."""
    _, gewoon = proportionele_schatting(17000, 400, 15)
    schatting, afgekapt = proportionele_schatting(17000, 20, 15, count_is_ondergrens=True)

    assert afgekapt >= gewoon
    assert afgekapt == 0.30
    assert schatting is not None


def test_reden_toont_dat_de_vestigingscount_een_ondergrens_is():
    r = reconcilieer(None, finding(wp=17000, bron="jaarverslag", limburg=False),
                     20, 15, count_is_ondergrens=True)
    assert "minstens 20 vestigingen" in r.reden
    assert r.schatting_penalty == 0.30
