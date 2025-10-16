from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_name: str = "prolific-interview"
    environment: str = "dev"
    api_key: str | None = None

    # LLM
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.7
    openai_api_key: str | None = None

    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/prolific"

    # CORS / UI
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"

    # Statistics defaults
    stats_prior_mean: float = 3.0
    stats_prior_variance: float = 0.25
    stats_prior_strength: int = 1
    stats_se_floor: float = 0.1
    stats_se_floor_min_real: int = 1


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
