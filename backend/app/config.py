"""Centrale applicatieconfiguratie."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    provider_mode: str = "mock"  # mock | live
    database_url: str = ""       # leeg -> SQLite
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"         # hoofd-model; overschrijfbaar via OPENAI_MODEL
    openai_model_extraction: str = ""          # leeg = fallback naar openai_model
    openai_web_search_model: str = "gpt-4.1-mini"
    jaarverslag_web_fallback: bool = False     # Fase C fallback: extra OpenAI-call als PDF mislukt
    jaarverslag_max_pogingen: int = 3          # retries met een ANDER zoekresultaat bij afgewezen/lege bron
    max_website_pages: int = 3                 # max pagina's per bedrijf voor website-agent (kostenbeheersing)
    extra_bronnen_aantal: int = 2               # extra publieke media-bronnen naast website/jaarverslag (human-in-the-loop; 0 = uit)
    research_media_venster_maanden: int = 18
    research_max_queries: int = 12
    research_max_pages: int = 15
    research_max_pages_after_primary: int = 8
    research_max_rounds: int = 3
    research_max_kandidaten: int = 8
    # Indicatieve OpenAI-prijzen (cent per 1000 tokens) — controleer tegen de
    # actuele OpenAI-pricingpagina voor het geconfigureerde model vóórdat
    # kosten_cents als harde budgetbron wordt gebruikt.
    openai_prijs_in_cent_per_1k: float = 0.015
    openai_prijs_out_cent_per_1k: float = 0.06
    research_company_timeout_seconds: int = 300
    playwright_enabled: bool = False
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
    # Bronranking staat los van WP-confidence (som = 1.0)
    rank_w_identiteit: float = 0.30
    rank_w_autoriteit: float = 0.25
    rank_w_relevantie: float = 0.20
    rank_w_actualiteit: float = 0.15
    rank_w_bewijs: float = 0.10

    @property
    def effective_database_url(self) -> str:
        return self.database_url or "sqlite:///./vestigingsregister.db"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
