from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Configuración de la app, leída de variables de entorno y del archivo .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Proveedores ---
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    
    # --- Sesión 2 (se eliminan en el bloque B, cuando entre el wrapper) ---
    LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    LLM_MODEL: str = "gpt-4o-mini"

    # --- Sesión 3: wrapper LiteLLM ---
    PRIMARY_MODEL: str = "gpt-4o-mini"
    FALLBACK_MODEL: str = "claude-haiku-4-5-20251001"
    LLM_TIMEOUT: int = 30
    LLM_RETRIES: int = 2

    # --- Sesión 3: caché Redis ---
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 60 * 60 * 24  # 24 horas, en segundos

    # --- App ---
    APP_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "DEBUG"

    @model_validator(mode="after")
    def validate_at_least_one_api_key(self) -> "Settings":
        """Con fallback se pueden usar los dos proveedores: basta con que haya al menos una clave."""
        if not self.OPENAI_API_KEY and not self.ANTHROPIC_API_KEY:
            raise ValueError("At least one of OPENAI_API_KEY or ANTHROPIC_API_KEY must be set")
        return self

@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración, creada una sola vez y reutilizada después."""
    return Settings()