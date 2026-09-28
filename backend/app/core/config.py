"""
app/core/config.py
──────────────────
Application-wide settings loaded from environment variables via pydantic-settings.
All code that needs a config value imports `settings` from this module; nothing
reaches for os.environ directly.
"""

from functools import lru_cache

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────
    # asyncpg DSN used by SQLAlchemy async engine (runtime queries)
    database_url: str = Field(
        default="postgresql+asyncpg://civicpulse:secret@localhost:5432/civicpulse",
        description="Async DSN for SQLAlchemy (asyncpg driver).",
    )
    # psycopg2 DSN used exclusively by Alembic (sync migration runner)
    database_sync_url: str = Field(
        default="postgresql+psycopg2://civicpulse:secret@localhost:5432/civicpulse",
        description="Sync DSN for Alembic migrations (psycopg2 driver).",
    )

    # ── Application ───────────────────────────────────────────────────────
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=False)
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    log_level: str = Field(default="info")

    # ── LLM providers (Phase 2 – populated later) ─────────────────────────
    groq_api_key: str = Field(default="")
    ollama_base_url: str = Field(default="http://localhost:11434")

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"app_env must be one of {allowed}")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# Module-level alias for convenient import: `from app.core.config import settings`
settings: Settings = get_settings()
