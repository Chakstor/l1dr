from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str
    anthropic_api_key: str | None = None

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    app_env: str = "development"
    log_level: str = "DEBUG"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()