import ipaddress
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str
    frontend_url: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8010"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
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
    resend_webhook_secret: str = ""
    unsubscribe_signing_secret: str = "development-only-change-me"
    support_email: str = "support@sprintern.app"
    notification_max_attempts: int = 5
    notification_lease_seconds: int = 300
    scheduler_source_config: Path = Path("config/sources.toml")
    scheduler_notification_interval_seconds: int = Field(30, ge=5)
    scheduler_heartbeat_interval_seconds: int = Field(30, ge=5)
    scheduler_timezone: str = "UTC"
    scheduler_misfire_grace_seconds: int = Field(60, ge=1)
    scheduler_shutdown_timeout_seconds: int = Field(30, ge=1)
    scheduler_source_sync_seconds: int = Field(60, ge=15, le=3600)
    source_stale_after_hours: int = Field(24, ge=1, le=168)
    rate_limit_enabled: bool = True
    rate_limit_max_identities: int = Field(10_000, ge=100, le=1_000_000)
    admin_user_ids_value: str = Field("", alias="ADMIN_USER_IDS")

    @property
    def admin_user_ids(self) -> set[str]:
        return {
            item.strip().casefold() for item in self.admin_user_ids_value.split(",") if item.strip()
        }

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_issuer}/.well-known/jwks.json"

    cors_origins_value: str = Field("http://localhost:3000", alias="CORS_ORIGINS")
    allowed_hosts_value: str = Field("localhost,127.0.0.1,test", alias="ALLOWED_HOSTS")
    trusted_proxy_cidrs_value: str = Field("", alias="TRUSTED_PROXY_CIDRS")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_value.split(",") if origin.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts_value.split(",") if host.strip()]

    @property
    def trusted_proxy_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        return [
            ipaddress.ip_network(cidr.strip(), strict=False)
            for cidr in self.trusted_proxy_cidrs_value.split(",")
            if cidr.strip()
        ]

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env.lower() != "production":
            return self
        errors: list[str] = []
        if len(self.internal_api_key) < 32:
            errors.append("INTERNAL_API_KEY must contain at least 32 characters")
        if not self.frontend_url.startswith("https://"):
            errors.append("FRONTEND_URL must use HTTPS")
        if not self.public_api_url.startswith("https://"):
            errors.append("PUBLIC_API_URL must use HTTPS")
        if not self.supabase_url.startswith("https://"):
            errors.append("SUPABASE_URL must use HTTPS")
        if not self.supabase_anon_key:
            errors.append("SUPABASE_ANON_KEY is required")
        if not self.supabase_service_role_key:
            errors.append("SUPABASE_SERVICE_ROLE_KEY is required for account deletion")
        if len(self.unsubscribe_signing_secret) < 32:
            errors.append("UNSUBSCRIBE_SIGNING_SECRET must contain at least 32 characters")
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            errors.append("DATABASE_URL must use PostgreSQL")
        if not self.cors_origins:
            errors.append("CORS_ORIGINS must contain the production frontend origin")
        if any(origin == "*" or not origin.startswith("https://") for origin in self.cors_origins):
            errors.append("CORS_ORIGINS must contain only explicit HTTPS origins")
        try:
            _ = self.trusted_proxy_networks
        except ValueError:
            errors.append("TRUSTED_PROXY_CIDRS must contain valid IP networks")
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            errors.append("ALLOWED_HOSTS must contain only explicit production hosts")
        api_host = urlparse(self.public_api_url).hostname
        if api_host and api_host not in self.allowed_hosts:
            errors.append("ALLOWED_HOSTS must include the production API host")
        if not self.admin_user_ids:
            errors.append("ADMIN_USER_IDS must contain at least one Supabase user UUID")
        if errors:
            raise ValueError("; ".join(errors))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
