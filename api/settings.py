from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str
    frontend_url: str = "http://localhost:3000"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_cache_seconds: int = 600
    internal_api_key: str = ""
    source_user_agent: str = "Sprintern/0.1"
    github_token: str = ""
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    telegram_webhook_secret: str = ""
    resend_api_key: str = ""
    resend_from_email: str = ""
    notification_max_attempts: int = 5
    notification_lease_seconds: int = 300
    scheduler_source_config: Path = Path("config/sources.toml")
    scheduler_notification_interval_seconds: int = Field(30, ge=5)
    scheduler_heartbeat_interval_seconds: int = Field(30, ge=5)
    scheduler_timezone: str = "UTC"
    scheduler_misfire_grace_seconds: int = Field(60, ge=1)
    scheduler_shutdown_timeout_seconds: int = Field(30, ge=1)

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"

    cors_origins_value: str = Field("http://localhost:3000", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_value.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env.lower() != "production":
            return self
        errors: list[str] = []
        if len(self.internal_api_key) < 32:
            errors.append("INTERNAL_API_KEY must contain at least 32 characters")
        if not self.frontend_url.startswith("https://"):
            errors.append("FRONTEND_URL must use HTTPS")
        if not self.supabase_url.startswith("https://"):
            errors.append("SUPABASE_URL must use HTTPS")
        if not self.supabase_anon_key:
            errors.append("SUPABASE_ANON_KEY is required")
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            errors.append("DATABASE_URL must use PostgreSQL")
        if not self.cors_origins:
            errors.append("CORS_ORIGINS must contain the production frontend origin")
        if any(origin == "*" or not origin.startswith("https://") for origin in self.cors_origins):
            errors.append("CORS_ORIGINS must contain only explicit HTTPS origins")
        if errors:
            raise ValueError("; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
