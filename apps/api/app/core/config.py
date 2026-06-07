from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "InterviewAI"
    environment: str = "development"

    # Database — default to local sqlite for dev/tests; Postgres in prod.
    database_url: str = "sqlite+aiosqlite:///./interviewai.db"

    # Auth
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    redis_url: str = "redis://localhost:6379/0"

    # AI / transcription providers
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    transcription_provider: str = "deepgram"
    deepgram_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
