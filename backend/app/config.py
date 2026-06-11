"""Centrale configuratie. Gewichten en drempels staan hier (niet hardcoded
in de pipeline) zodat kalibratie zonder code-wijziging kan."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    provider_mode: str = "mock"  # mock | live
    database_url: str = ""       # leeg -> SQLite
    anthropic_api_key: str = ""
    google_places_api_key: str = ""
    kvk_api_key: str = ""
    jwt_secret: str = "change-me"
    register_peildatum: str = "2026-04-01"
    anthropic_model: str = "claude-sonnet-4-6"
    frontend_origin: str = "http://127.0.0.1:5173,http://localhost:5173"

    # Confidence-gewichten (som = 1.0) — zie documentatie §9
    w_locatie: float = 0.30
    w_specificiteit: float = 0.25
    w_bronkwaliteit: float = 0.20
    w_consensus: float = 0.10
    w_adres: float = 0.075
    w_actualiteit: float = 0.075

    # Drempels
    drempel_hoog: float = 0.80
    drempel_middel: float = 0.50

    # Penalties
    penalty_places_fuzzy: float = 0.05
    penalty_fte_only: float = 0.10
    cap_llm_laag: float = 0.49

    @property
    def effective_database_url(self) -> str:
        return self.database_url or "sqlite:///./vestigingsregister.db"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
