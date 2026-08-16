"""Deterministische basisqueries; een LLM mag later alleen aanvullen."""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .types import PlannedQuery

_ADMINISTRATIEVE_NAAMDELEN = {
    "afdeling", "filiaal", "groepswoning", "locatie", "regio", "unit",
    "vestiging", "woongroep", "woonzorgcentrum", "zorgcentrum",
}


@dataclass(frozen=True)
class QueryContext:
    naam: str
    gevraagd_jaar: int | None = None
    website_url: str | None = None
    gemeente: str | None = None
    adres: str | None = None
    huidig_jaar: int | None = None
    sbi_code: str | None = None
    sbi_omschrijving: str | None = None
    kvk_nummer: str | None = None
    # Het LRK publiceert `vestigingsnummer_houder`, dezelfde sleutel als het
    # Vestigingsregister. Daarmee is een koppeling een identiteit in plaats
    # van een naamgelijkenis; zonder dit veld valt lrk.py terug op het
    # KvK-nummer en uiteindelijk op de naam.
    vestigingsnummer: str | None = None


def _bevat_stam(tekst: str, stammen: tuple[str, ...]) -> bool:
    """Trefwoord aan een woordbegin, niet ergens middenin een ander woord."""
    return any(re.search(rf"\b{re.escape(stam)}", tekst) for stam in stammen)


# "verzorging" is een handeling (haarverzorging, autoverzorging), "zorg" is de
# sector. Kale substringmatching op "zorg" haalde daardoor een kapsalon en een
# schadeherstelbedrijf binnen als institutionele zorg, inclusief verplichte
# DigiMV-route. Woordbegin-matching alleen is te streng: "Buurtzorg",
# "thuiszorg" en "gehandicaptenzorg" zijn wél zorg maar beginnen er niet mee.
# Vandaar: knip de handeling eruit en zoek dan pas naar "zorg" — met
# verzorgingshuis en verzorgingstehuis als uitzondering, want dat zijn
# instellingen en geen handeling.
_VERZORGING_IS_GEEN_ZORG = re.compile(r"verzorging(?!s?(?:huis|tehuis))|verzorgend\w*")


def _is_zorgtekst(tekst: str) -> bool:
    return "zorg" in _VERZORGING_IS_GEEN_ZORG.sub(" ", tekst)


def plan_routes(context: QueryContext) -> list[dict]:
    """Kleine beslistabel voor redelijke onderzoeksroutes.

    Dit is bewust geen AI-planner. SBI bepaalt de drie profielen waar nu een
    concrete sectorspecifieke route voor bekend is; onbekende bedrijven
    houden het bestaande website/document/media-plan.

    KvK-verrijking levert niet altijd een SBI-code op (mislukte lookup,
    net ingeschreven bedrijf, handmatig aangeleverde testrijen). Daarom
    kijken de trefwoorden hieronder zowel naar `sbi_omschrijving` als naar de
    bedrijfsnaam zelf — een "Hospice de Ark" of "Woonzorgcentrum Amaliahof"
    is ook zonder SBI-code herkenbaar als zorgaanbieder. Dit is een fallback,
    geen vervanging: een SBI-treffer blijft leidend, en een generieke naam
    zonder sectorwoord (bijvoorbeeld een merknaam) wordt terecht niet
    herkend — dat is dan aan de reviewer.
    """
    sbi = (context.sbi_code or "").replace(".", "").strip()
    naam_en_omschrijving = (
        f"{context.sbi_omschrijving or ''} {context.naam}"
    ).lower()
    onderwijs = sbi.startswith("85") or _bevat_stam(
        naam_en_omschrijving,
        (
            "onderwijs", "school", "scholen", "college", "universit",
            "hogescho", "opleiding", "roc", "vmbo", "havo", "vwo", "mbo",
            "hbo",
        ),
    )
    zorg = (
        sbi.startswith(("86", "87", "88"))
        or _is_zorgtekst(naam_en_omschrijving)
        # Deze termen hebben geen "verzorging"-achtige valse tweelingbroer, dus
        # gewone substringmatching mag: "wijkverpleging", "polikliniek" en
        # "kinderrevalidatie" zijn allemaal zorg.
        or any(
            woord in naam_en_omschrijving
            for woord in (
                "ziekenhuis", "verpleeg", "verpleging", "hospice", "kliniek",
                "revalidatie", "psychogeriatrie", "gehandicapt",
                "groepswoning",
            )
        )
        # Korte afkortingen wél op woordgrens: "umc" en "ggz" zouden anders
        # middenin willekeurige woorden kunnen vallen.
        or _bevat_stam(naam_en_omschrijving, ("umc", "ggz"))
    )
    lokale_zorgpraktijk = sbi.startswith(("862", "8691", "8692")) or _bevat_stam(
        naam_en_omschrijving,
        (
            "tandarts", "huisarts", "fysiotherap", "verloskund",
            "podotherap", "orthodont",
        ),
    )
    institutionele_zorg = zorg and not lokale_zorgpraktijk
    kinderopvang = sbi.startswith("8891") or _bevat_stam(
        naam_en_omschrijving,
        (
            "kinderopvang", "kinderdagverblijf", "kindercentr",
            "peuterspeelzaal", "peuteropvang", "buitenschoolse opvang",
            "gastouderbureau", "kindontwikkeling",
        ),
    )
    lokale_teamdienst = lokale_zorgpraktijk or sbi.startswith("9602") or _bevat_stam(
        naam_en_omschrijving,
        ("kapper", "kapsalon", "haarverzorging", "schoonheidsverzorging"),
    )

    routes = [{
        "route": "website",
        "verplicht": True,
        "status": "wachtend",
        "reden": "officiële website en organisatiepagina's",
    }]
    # De documentroute draait altijd én is altijd verplicht. Hij stond eerder
    # uit voor lokale teamdiensten, maar SBI zegt niets over omvang: Mondriaan
    # (GGZ, 2.281 WP) deelt SBI 8622 met een tandartspraktijk. Gevolg was dat
    # Mondriaan zijn eigen jaarverslag niet meer zocht — op 25-07 leverde de
    # documentroute daar nog 2.400 en 2.294 op, daarna niets meer.
    #
    # Verplicht, omdat dit de dragende route is: van de kandidaten met een
    # WP-waarde was brontype jaarverslag 15× de énige bron binnen 25% van de
    # waarheid — meer dan alle andere brontypen samen (11×). Faalt deze route,
    # dan is de run technisch onvolledig en niet "niets gevonden".
    routes.append({
        "route": "document",
        "verplicht": True,
        "status": "wachtend",
        "reden": (
            "formele documenten zijn een kernbron voor dit profiel"
            if onderwijs or institutionele_zorg
            else "formele documenten zijn de sterkste WP-bron als ze bestaan"
        ),
    })
    if onderwijs:
        routes.append({
            "route": "duo",
            "verplicht": True,
            "status": "wachtend",
            "reden": "DUO publiceert instellings- en personeelsgegevens",
        })
    if zorg:
        routes.append({
            "route": "digimv",
            "verplicht": institutionele_zorg,
            "status": "wachtend",
            "reden": (
                "DigiMV is een kernbron voor institutionele zorg"
                if institutionele_zorg
                else "DigiMV onderzoeken wanneer de lokale zorgpraktijk erin voorkomt"
            ),
        })
    if kinderopvang:
        routes.append({
            "route": "lrk",
            # Niet verplicht: het LRK levert het aantal vestigingen en de
            # capaciteit, maar bewust géén WP-cijfer (kindplaatsen zijn
            # dagcapaciteit). Een run mag hier niet op vastlopen.
            "verplicht": False,
            "status": "wachtend",
            "reden": (
                "het Landelijk Register Kinderopvang telt de ingeschreven "
                "locaties per houder"
            ),
        })
    if lokale_teamdienst:
        routes.append({
            "route": "team_afspraak",
            # Bewust niet verplicht. SBI 862x zegt niets over omvang, dus deze
            # route komt ook op instellingen terecht waar hij alleen ruis
            # oplevert: bij Mondriaan produceerde hij WP-waarden 3, 4 en 5 uit
            # patiënteninformatie-PDF's. Van de kandidaten met een WP-waarde
            # haalde brontype team_afspraak 0 van de 2 keer een waarde binnen
            # 25% van de waarheid. Hij mag meedraaien, maar zijn falen mag de
            # run niet als technisch onvolledig markeren en zijn vondsten
            # mogen de documentroute niet verdringen.
            "verplicht": False,
            "status": "wachtend",
            "reden": "team- en afspraakmodules tonen vaak de werkzame personen",
        })
    routes.append({
        "route": "media",
        "verplicht": True,
        "status": "wachtend",
        "reden": "aanvullende openbare context en personeelsinformatie",
    })
    return routes


def _domein(url: str | None) -> str | None:
    if not url:
        return None
    return urlsplit(url).netloc.lower().removeprefix("www.") or None


def vereenvoudigde_zoeknaam(naam: str) -> str | None:
    """Verwijder administratieve labels/codes, maar behoud de eigennaam."""
    ascii_naam = unicodedata.normalize("NFKD", naam).encode(
        "ascii", "ignore",
    ).decode("ascii")
    tokens = re.findall(r"[A-Za-z0-9]+", ascii_naam)
    bruikbaar = [
        token for token in tokens
        if (
            token.lower() not in _ADMINISTRATIEVE_NAAMDELEN
            and not token.isdigit()
            and len(token) > 1
        )
    ]
    vereenvoudigd = " ".join(bruikbaar).strip()
    if not vereenvoudigd or vereenvoudigd.lower() == ascii_naam.strip().lower():
        return None
    return vereenvoudigd


def plan_queries(context: QueryContext) -> list[PlannedQuery]:
    """Bouwt korte, gerichte zoekopdrachten.

    Gemeten op de jaarverslagzoeker (tien organisaties die aantoonbaar
    publiceren): een query met de naam tussen aanhalingstekens plus een stapel
    synoniemen scoorde 2/10, een beknopte variant 8/10. De index matcht dan op
    de trefwoorden in plaats van op de organisatie. Daarom hier: geen exacte
    frase om de naam, hooguit twee verwante termen per query, en het jaartal
    één keer. De breedte zit in het aantal query's, niet in de lengte ervan."""
    naam = context.naam.strip()
    gemeente = f" {context.gemeente.strip()}" if context.gemeente else ""
    domein = _domein(context.website_url)
    huidig_jaar = context.huidig_jaar or datetime.now(timezone.utc).year
    queries: list[PlannedQuery] = []
    actieve_routes = {item["route"] for item in plan_routes(context)}

    if domein:
        queries.extend([
            PlannedQuery(
                "website",
                f"site:{domein} {naam} medewerkers team",
                "officiële websitepagina's met expliciet WP-bewijs",
            ),
            PlannedQuery(
                "website",
                f"site:{domein} {naam} over ons organisatie",
                "officiële organisatiepagina",
            ),
        ])

    # Sectorspecifieke routes komen vóór de bredere documentqueries, zodat
    # iedere verplichte route ook bij een klein querybudget minstens één kans
    # krijgt.
    if "duo" in actieve_routes:
        queries.append(PlannedQuery(
            "duo",
            f"site:duo.nl/open_onderwijsdata {naam} personeel",
            "DUO-instellings- en personeelsgegevens",
        ))
    if "digimv" in actieve_routes:
        queries.append(PlannedQuery(
            "digimv",
            f"site:digimv13.desan.nl {naam}",
            "DigiMV-archief en zorgverantwoording",
        ))
    if "lrk" in actieve_routes:
        # Zonder query zou deze route als "overgeslagen" worden gerapporteerd
        # zodra de directe registerkoppeling niets oplevert, terwijl hij wel
        # degelijk is uitgevoerd. Dat verschil moet zichtbaar blijven.
        queries.append(PlannedQuery(
            "lrk",
            f"site:landelijkregisterkinderopvang.nl {naam}{gemeente}",
            "Landelijk Register Kinderopvang",
        ))
    if "team_afspraak" in actieve_routes:
        if domein:
            queries.append(PlannedQuery(
                "team_afspraak",
                f"site:{domein} team medewerkers afspraak boeken",
                "team- of afspraakmodule op de officiële website",
            ))
        else:
            queries.append(PlannedQuery(
                "team_afspraak",
                f"{naam}{gemeente} team afspraak medewerker kiezen",
                "team- of afspraakmodule vinden",
            ))

    queries.append(PlannedQuery(
        "website",
        f"{naam}{gemeente} medewerkers team",
        "officiële website of expliciete organisatiepagina vinden",
    ))
    zoekalias = vereenvoudigde_zoeknaam(naam)
    if zoekalias:
        queries.append(PlannedQuery(
            "website",
            f"{zoekalias}{gemeente} medewerkers team",
            "openbare bronnen onder de naam zonder administratieve code",
        ))

    if "document" in actieve_routes and not context.gevraagd_jaar:
        # Zonder peiljaar leverde deze route hiervóór géén enkele query op,
        # terwijl plan_routes hem wel plande: de route werd dan stil
        # "overgeslagen". Een jaarloze variant is nog altijd de sterkste bron
        # die er is — brontype jaarverslag was 15× de enige kandidaat binnen
        # 25% van de waarheid.
        queries.append(PlannedQuery(
            "document",
            f"site:{domein} {naam} jaarverslag" if domein
            else f"{naam}{gemeente} jaarverslag pdf",
            "formeel document zonder bekend peiljaar",
        ))

    if context.gevraagd_jaar and "document" in actieve_routes:
        jaar = context.gevraagd_jaar
        publicatiejaar = jaar + 1
        if domein:
            # Zodra het officiële domein bekend is, moet de nieuwste jaargang
            # vóór brede zoekresultaten worden onderzocht; anders verbruiken
            # algemene hits het paginabudget.
            queries.append(PlannedQuery(
                "document",
                f"site:{domein} {naam} jaarverslag {jaar}",
                "nieuwste formele document op het officiële domein",
            ))
        queries.extend([
            PlannedQuery(
                "document",
                f"{naam} jaarverslag pdf",
                "formeel document voor het gevraagde verslagjaar",
            ),
            PlannedQuery(
                "document",
                f"{naam} jaarrekening {jaar}",
                "jaarrekening als het jaarverslag ontbreekt",
            ),
            PlannedQuery(
                "document",
                # Overheden publiceren geen jaarverslag maar jaarstukken.
                f"{naam} jaarstukken filetype:pdf",
                "jaarstukken van gemeenten, provincies en waterschappen",
            ),
            PlannedQuery(
                "document",
                f"{naam} annual report pdf",
                "Engelstalig formeel document",
            ),
            PlannedQuery(
                "document",
                f"{naam} jaarverslag gepubliceerd {publicatiejaar}",
                "document gepubliceerd in jaar N+1 over verslagjaar N",
            ),
        ])
    if "media" in actieve_routes:
        queries.extend([
            PlannedQuery(
                "media",
                f"{naam} nieuws medewerkers {huidig_jaar}",
                "recente media over organisatieomvang of veranderingen",
            ),
            PlannedQuery(
                "media",
                f"{naam} reorganisatie overname",
                "recente gebeurtenissen die officiële cijfers kunnen hebben gewijzigd",
            ),
        ])

    uniek: dict[str, PlannedQuery] = {}
    for query in queries:
        uniek.setdefault(query.query, query)
    per_route: dict[str, list[PlannedQuery]] = {}
    for query in uniek.values():
        per_route.setdefault(query.pad, []).append(query)
    routevolgorde = [item["route"] for item in plan_routes(context)]
    geordend: list[PlannedQuery] = []
    grootste_route = max((len(items) for items in per_route.values()), default=0)
    for index in range(grootste_route):
        for route in routevolgorde:
            routequeries = per_route.get(route, [])
            if index < len(routequeries):
                geordend.append(routequeries[index])
    return geordend
