"""Centrale applicatieconfiguratie."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    provider_mode: str = "mock"  # mock | live
    database_url: str = ""       # leeg -> SQLite
    openai_api_key: str = ""
    # Hoofd-model; overschrijfbaar via OPENAI_MODEL. Extractie, scope-classificatie
    # en de bronreview zijn oordeelstaken ("is dit een namenlijst van medewerkers
    # of van bestuurders?"); gpt-4o-mini bleek daar te licht voor. Bij ~82k in en
    # ~5,6k out per bedrijf kost luna circa 1,4x zoveel — een paar tientjes per
    # volledige cyclus. Zie openai_prijs_* hieronder: die moeten meeveranderen.
    openai_model: str = "gpt-5.6-luna"
    openai_model_extraction: str = ""          # leeg = fallback naar openai_model
    openai_web_search_model: str = "gpt-4.1-mini"
    openai_web_search_enabled: bool = False     # zoeken uitsluitend via Serper
    # Extractie en classificatie zijn oordeelstaken met één juist antwoord, geen
    # creatieve taken. De OpenAI-default van 1.0 levert daar alleen ruis op:
    # dezelfde bron kan tussen twee runs een ander oordeel krijgen.
    openai_temperature: float = 0.0
    # Azure AI Foundry. Leeg = rechtstreeks naar OpenAI, zoals nu. Vul je het
    # endpoint, dan gaat elke modelcall via Azure — de aanroepen zelf blijven
    # gelijk, want het is dezelfde SDK met een andere client. Productie moet op
    # termijn naar Azure; door dit hier te zetten is dat één omgevingsvariabele
    # in plaats van tien bestanden.
    # Waar brondocumenten worden bewaard. Leeg = niet bewaren; op Railway wijst
    # dit naar een volume, want zonder volume is de schijf bij de volgende
    # deploy weg en is "bewaard" een loze belofte.
    brondocumenten_pad: str = ""
    # Waar de dagelijkse herstelpunten van de database staan. Leeg = uit;
    # op Railway een submap van het gemonteerde volume, want daarbuiten
    # verdwijnt het bestand bij de volgende deploy.
    backup_pad: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2025-04-01-preview"
    jaarverslag_web_fallback: bool = False     # Fase C fallback: extra OpenAI-call als PDF mislukt
    jaarverslag_max_pogingen: int = 3          # retries met een ANDER zoekresultaat bij afgewezen/lege bron
    max_website_pages: int = 3                 # max pagina's per bedrijf voor website-agent (kostenbeheersing)
    extra_bronnen_aantal: int = 2               # extra publieke media-bronnen naast website/jaarverslag (human-in-the-loop; 0 = uit)
    research_media_venster_maanden: int = 18
    research_max_queries: int = 10
    research_max_pages: int = 15
    research_max_rounds: int = 3
    research_max_kandidaten: int = 8
    # Indicatieve OpenAI-prijzen (cent per 1000 tokens) — controleer tegen de
    # actuele OpenAI-pricingpagina voor het geconfigureerde model vóórdat
    # kosten_cents als harde budgetbron wordt gebruikt.
    # Deze twee horen bij openai_model hierboven en moeten bij elke modelwissel
    # mee: anders rapporteert de app kosten van een model dat niet meer draait.
    # gpt-5.6-luna: $0,20/1M in = 0,02 cent/1k · $1,20/1M uit = 0,12 cent/1k.
    openai_prijs_in_cent_per_1k: float = 0.02
    openai_prijs_out_cent_per_1k: float = 0.12
    research_company_timeout_seconds: int = 300
    # Eén aangedragen bron uitlezen gebeurt terwijl de reviewer staat te
    # wachten, niet in de achtergrond. Ruim genoeg voor het downloaden van
    # een jaarverslag van tientallen megabytes plus één modelaanroep, en
    # kort genoeg om niet als een vastloper te voelen.
    losse_bron_timeout_seconds: int = 90
    # Hoeveel organisaties tegelijk. Stond vast op één: de lijst was precies zo
    # lang als de som van haar runs — gemeten op productie 100% bezetting, geen
    # dode tijd ertussen, dus 108 vestigingen betekende 6 uur 19. De rem zat er
    # om API-budgetten te bewaken, maar dat is een taak voor een limiet en niet
    # voor het op een rij zetten van al het werk. De gedeelde browser heeft een
    # eigen rem (crawl4ai_max_parallel), en de kostenteller loopt per taak via
    # contextvars. Op 1 zetten geeft exact het oude gedrag terug.
    research_max_parallel_companies: int = 4
    playwright_enabled: bool = False
    # Altijd via Crawl4AI renderen in plaats van alleen als fallback bij te
    # weinig platte tekst. Levert markdown met behoud van koppen, lijsten en
    # tabellen en zonder navigatie-boilerplate: minder ruis én minder
    # inputtokens. Werkt alleen als playwright_enabled aanstaat.
    crawl4ai_altijd: bool = True
    # Maximaal aantal gelijktijdige renders op de gedeelde browser, per
    # organisatie. De supervisor inspecteert tot research_max_pages pagina's in
    # één gather; zonder deze rem zouden dat evenveel gelijktijdige tabs zijn.
    #
    # Per organisatie, want de semafoor in fetch.py is er één voor het hele
    # proces. Toen dit getal werd gekozen liep er één organisatie tegelijk en
    # was het verschil er niet. Sinds research_max_parallel_companies boven 1
    # staat delen alle organisaties diezelfde plaatsen, en dan is een vast
    # getal stilzwijgend een deling: vier organisaties kregen samen nog steeds
    # drie tabs. Zie crawl4ai_max_parallel hieronder voor de procesbrede rem.
    crawl4ai_max_parallel_per_organisatie: int = 3
    frontend_origin: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174"
    frontend_url: str = "http://localhost:5173"  # publieke URL voor chat-links in emails
    resend_api_key: str = ""
    email_from: str = "onboarding@resend.dev"
    email_demo_recipient: str = ""
    demo_armina_password: str = ""
    demo_anita_password: str = ""
    demo_admin_password: str = ""
    demo_vanzandvoort_password: str = ""
    demo_vaessens_password: str = ""
    demo_paffen_password: str = ""
    google_places_api_key: str = ""
    # Google Places Text Search pagineert hier niet: bij precies dit aantal
    # resultaten is de landelijke vestigingstelling een ondergrens.
    places_max_resultaten: int = 20
    serper_api_key: str = ""     # betrouwbare zoek-fallback i.p.v. OpenAI web_search (kostenbeheersing)
    kvk_api_key: str = ""
    jwt_secret: str = "change-me"
    register_peildatum: str = "2026-04-01"

    # Drempels
    drempel_hoog: float = 0.80
    drempel_middel: float = 0.50

    # Penalties
    penalty_places_fuzzy: float = 0.05
    penalty_fte_only: float = 0.10
    # Actualiteit: een jaarverslag over jaar X verschijnt pas in X+1, dus één
    # jaar verschil is normaal. Pas daarboven telt het cijfer als verouderd.
    peilmoment_max_leeftijd_jaren: int = 1
    penalty_verouderd_peilmoment: float = 0.15
    # Bronranking staat los van WP-confidence (som = 1.0)
    rank_w_identiteit: float = 0.30
    rank_w_autoriteit: float = 0.25
    rank_w_relevantie: float = 0.20
    rank_w_actualiteit: float = 0.15
    rank_w_bewijs: float = 0.10

    @property
    def crawl4ai_max_parallel(self) -> int:
        """Procesbrede rem op de gedeelde browser: zoveel renders per
        organisatie, maal het aantal organisaties dat tegelijk loopt.

        Afgeleid en niet apart in te stellen, omdat de twee getallen niet los
        van elkaar kunnen bestaan: de semafoor in fetch.py geldt voor het hele
        proces, dus elke organisatie die erbij komt deelt mee. Twee losse
        constanten hielden dat verband verborgen, en daar ging het eerder mis.

        Het raakt ook de timeout en niet alleen de snelheid. page_timeout staat
        op 30s en research_max_pages op 15: met drie renders tegelijk zijn dat
        vijf golven (150s) en dat past binnen research_company_timeout_seconds
        (300s). Zouden vier organisaties samen drie plaatsen houden, dan worden
        het twintig golven en loopt een organisatie in haar eigen timeout.
        """
        return self.crawl4ai_max_parallel_per_organisatie * max(
            1, self.research_max_parallel_companies,
        )

    @property
    def effective_database_url(self) -> str:
        return self.database_url or "sqlite:///./vestigingsregister.db"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
