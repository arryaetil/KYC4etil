"""Minimale, deterministische routeselectie per organisatieprofiel."""

from app.research.query_planner import QueryContext, plan_routes


def _routes(context: QueryContext) -> dict[str, dict]:
    return {item["route"]: item for item in plan_routes(context)}


def test_onderwijs_krijgt_duo_en_documentroute():
    routes = _routes(QueryContext(
        naam="Voorbeeldschool",
        sbi_code="85201",
        sbi_omschrijving="Basisonderwijs",
    ))

    assert routes["duo"]["verplicht"] is True
    assert routes["document"]["verplicht"] is True
    assert routes["duo"]["status"] == "wachtend"
    assert "digimv" not in routes


def test_zorg_krijgt_digimv_en_documentroute():
    routes = _routes(QueryContext(
        naam="Voorbeeld Zorg",
        sbi_code="86101",
        sbi_omschrijving="Ziekenhuizen",
    ))

    assert routes["digimv"]["verplicht"] is True
    assert routes["document"]["verplicht"] is True
    assert "duo" not in routes


def test_lokale_zorgpraktijk_krijgt_teamroute_en_digimv_voorwaardelijk():
    routes = _routes(QueryContext(
        naam="Voorbeeld Tandarts",
        sbi_code="86231",
        sbi_omschrijving="Praktijken van tandartsen",
    ))

    assert routes["digimv"]["verplicht"] is False
    # De documentroute komt erbij, niet in plaats van de teamroute: SBI 862x
    # dekt zowel een tandartspraktijk als Mondriaan (GGZ, 2.281 WP). Verplicht,
    # want juist bij die grote deler is het jaarverslag de enige harde bron —
    # en of een organisatie er een publiceert weet je pas ná het zoeken, niet
    # uit haar SBI-code.
    assert routes["document"]["verplicht"] is True
    # Andersom is de teamroute niet verplicht: hij landt via dezelfde SBI ook
    # op instellingen, waar hij alleen ruis oplevert.
    assert routes["team_afspraak"]["verplicht"] is False


def test_kapper_krijgt_team_afspraakroute_en_onverplichte_documentroute():
    routes = _routes(QueryContext(
        naam="Voorbeeldkapper",
        sbi_code="96021",
        sbi_omschrijving="Haarverzorging",
    ))

    assert routes["team_afspraak"]["verplicht"] is False
    # De documentroute draait er nu naast in plaats van te vervallen.
    assert "document" in routes
    assert {"website", "media"}.issubset(routes)
    # En deze kapper is géén zorg meer: "haarverzorging" bevat weliswaar
    # "zorg", maar niet als sectorwoord. Zie
    # test_dienstverlening_met_verzorging_in_de_naam_is_geen_zorg.
    assert "digimv" not in routes


def test_onbekend_profiel_houdt_het_bestaande_basisplan():
    routes = _routes(QueryContext(naam="Voorbeeldbedrijf"))

    assert set(routes) == {"website", "document", "media"}
    # Ook zonder sectorprofiel is het formele document de sterkste bron die er
    # is; het basisplan laat hem daarom niet stilzwijgend vervallen.
    assert routes["document"]["verplicht"] is True


def test_zorgnaam_krijgt_digimv_ook_zonder_sbi_code():
    """
    Regressie: KvK-verrijking levert niet altijd een SBI-code op. Een
    bedrijfsnaam als "Hospice de Ark" is ook zonder sbi_code herkenbaar als
    Wlz-zorgaanbieder — jaarverantwoordingzorg.nl is wettelijk verplicht voor
    elke Wlz/Zvw-zorgaanbieder, ongeacht grootte of SBI-registratie.
    """
    for naam in (
        "Hospice de Ark",
        "Woonzorgcentrum Amaliahof",
        "Groene Kruis Kraamzorg - Regio Westelijke Mijnstreek",
        "Groene Kruis Wijkverpleging, Team Echt Zuid",
        "Groepswoningen Eldershof",
        "Revalidatiekliniek Noord-Limburg - Venray",
        "Integr. Expert.centr. Psychogeriatrie Venray",
    ):
        routes = _routes(QueryContext(naam=naam))
        assert "digimv" in routes, f"{naam} zou digimv moeten krijgen"


def test_onderwijsnaam_krijgt_duo_ook_zonder_sbi_code():
    for naam in ("Zuyd Hogeschool", "Open Universiteit"):
        routes = _routes(QueryContext(naam=naam))
        assert routes["duo"]["verplicht"] is True, f"{naam} zou duo moeten krijgen"


def test_sbi_code_blijft_leidend_ook_als_naam_neutraal_is():
    """Een sbi-treffer werkt onafhankelijk van wat de naam wel of niet bevat."""
    routes = _routes(QueryContext(
        naam="Okechamp B.V.", sbi_code="1039", sbi_omschrijving="Groente verwerken",
    ))

    assert "digimv" not in routes
    assert "duo" not in routes


def test_merknaam_zonder_sectorwoord_wordt_niet_geforceerd():
    """
    Een generieke merknaam zonder sbi-code en zonder sectorwoord in de naam
    (zoals "Stichting Philadelphia") wordt terecht niet herkend — de fallback
    raadt niet, hij herkent alleen expliciete sectorwoorden.
    """
    routes = _routes(QueryContext(naam="Stichting Philadelphia"))

    assert "digimv" not in routes


def test_welzijnsorganisatie_krijgt_geen_digimv():
    """Welzijnswerk is geen Wlz/Zvw-zorg en levert dus niet aan DigiMV aan.

    "Welzijn" stond in de zorg-trefwoorden en gaf Punt Welzijn een verplichte
    DigiMV-route. Een directe bevraging van het DigiMV-archief levert voor die
    organisatie nul documenten; in productie leverde de route bij alle zestien
    inzetten nul bronnen op. De documentroute vindt hun jaarverslag wel.
    """
    routes = _routes(QueryContext(naam="Stichting Punt Welzijn"))
    assert "digimv" not in routes
    assert "document" in routes


def test_dienstverlening_met_verzorging_in_de_naam_is_geen_zorg():
    """Substringbug: "Haarverzorging" bevat "zorg".

    Een kapsalon en een schadeherstelbedrijf kregen daardoor een verplichte
    DigiMV-route. Samenstellingen waar "zorg" wél de sector aanduidt, moeten
    blijven werken — ook als het woord niet vooraan staat.
    """
    for naam in (
        "Kapsalon Haarverzorging",
        "Autoschade Verzorging BV",
        "Schoonheidssalon Lichaamsverzorging",
    ):
        assert "digimv" not in _routes(QueryContext(naam=naam)), naam

    for naam in (
        "Buurtzorg Nederland",
        "Zorgboerderij Wienes B.V.",
        "Stichting Gehandicaptenzorg Limburg",
        "Verzorgingshuis De Linde",
        "Maastricht UMC+",
    ):
        assert "digimv" in _routes(QueryContext(naam=naam)), naam


def test_documentroute_is_altijd_verplicht():
    """De dragende route mag niet stil wegvallen.

    Van de kandidaten met een WP-waarde was brontype jaarverslag 15× de enige
    bron binnen 25% van de waarheid — meer dan alle andere brontypen samen.
    Toen de SBI-planner hem uitzette voor SBI 862x, verloor Mondriaan zijn
    eigen jaarverantwoording (2.294/2.400 tegen een waarheid van 2.281).
    """
    for naam, sbi in (
        ("Mondriaan", "8622"),
        ("Salon Handmade", "9602"),
        ("Hallux Podotherapie", "8691"),
        ("Bakkerij Broekmans", ""),
    ):
        routes = _routes(QueryContext(naam=naam, sbi_code=sbi, gevraagd_jaar=2026))
        assert routes["document"]["verplicht"] is True, naam


def test_teamroute_is_nooit_verplicht():
    """SBI zegt niets over omvang, dus deze route landt ook op instellingen.

    Bij Mondriaan leverde team_afspraak WP-waarden 3, 4 en 5 op uit
    patiënteninformatie-PDF's. Brontype team_afspraak haalde 0 van de 2 keer
    een waarde binnen 25% van de waarheid. Meedraaien mag; de run als
    technisch onvolledig markeren als hij faalt, niet.
    """
    for naam, sbi in (("Salon Handmade", "9602"), ("Hallux Podotherapie", "8691")):
        routes = _routes(QueryContext(naam=naam, sbi_code=sbi))
        assert routes["team_afspraak"]["verplicht"] is False, naam


def test_documentroute_krijgt_ook_zonder_peiljaar_een_query():
    """plan_routes plande de route, plan_queries leverde er geen enkele.

    De route werd dan stil "overgeslagen" in plaats van uitgevoerd.
    """
    from app.research.query_planner import plan_queries

    paden = {q.pad for q in plan_queries(QueryContext(naam="Onvindbare Organisatie"))}
    assert "document" in paden


def test_kinderopvang_krijgt_lrk_route():
    """Het LRK is koppelbaar op vestigingsnummer en tweemaal per week ververst.

    Kinderopvang is 10 van de 205 monitoringorganisaties, en het register geeft
    per houder een exacte locatietelling — precies het vestigingsniveau dat
    elders ontbreekt.
    """
    for naam in (
        "Hoera Kindercentrum",
        "Kinderopvang Flow",
        "Stichting Kinderopvang 't Nest",
        "Wee-Play Kinderopvang",
    ):
        routes = _routes(QueryContext(naam=naam))
        assert "lrk" in routes, naam
        # Niet verplicht: het register levert bewust geen WP-cijfer, dus een
        # run mag er niet op vastlopen.
        assert routes["lrk"]["verplicht"] is False, naam


def test_niet_kinderopvang_krijgt_geen_lrk_route():
    for naam in ("Mondriaan", "Bakkerij Voncken", "Dreessen Advocaten"):
        assert "lrk" not in _routes(QueryContext(naam=naam)), naam
