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
    openai_temperature: float = 0.4
    openai_api_key: str | None = None

    # Database
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/prolific"

    # CORS / UI
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
