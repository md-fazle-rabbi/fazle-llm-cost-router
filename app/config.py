"""Application configuration — reads all secrets from .env file."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All environment variables with strict type validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_version: str = "1.0.0"

    gemini_api_key: str
    cheap_model: str = "gemini/gemini-2.5-flash"
    expensive_model: str = "gemini/gemini-2.5-pro"
    anthropic_api_key: str = ""

    complexity_threshold: float = 0.5
    max_tokens_cheap: int = 150

    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600

    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_project_id: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
