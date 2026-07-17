import pytest
from pydantic import ValidationError

from api.settings import Settings


def production_settings(**overrides: str) -> Settings:
    values = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://user:pass@db.example.com/sprintern",
        "frontend_url": "https://app.sprintern.example",
        "supabase_url": "https://project.supabase.co",
        "supabase_anon_key": "public-anon-key",
        "internal_api_key": "a" * 64,
        "CORS_ORIGINS": "https://app.sprintern.example",
    }
    aliases = {
        "APP_ENV": "app_env",
        "DATABASE_URL": "database_url",
        "FRONTEND_URL": "frontend_url",
        "SUPABASE_URL": "supabase_url",
        "SUPABASE_ANON_KEY": "supabase_anon_key",
        "INTERNAL_API_KEY": "internal_api_key",
    }
    values.update({aliases.get(key, key): value for key, value in overrides.items()})
    return Settings(**values)  # type: ignore[arg-type]


def test_secure_production_configuration_is_accepted() -> None:
    assert production_settings().cors_origins == ["https://app.sprintern.example"]


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"INTERNAL_API_KEY": "short"}, "at least 32"),
        ({"FRONTEND_URL": "http://localhost:3000"}, "FRONTEND_URL must use HTTPS"),
        ({"CORS_ORIGINS": "*"}, "explicit HTTPS origins"),
        ({"CORS_ORIGINS": "http://localhost:3000"}, "explicit HTTPS origins"),
        ({"SUPABASE_URL": "http://localhost:54321"}, "SUPABASE_URL must use HTTPS"),
    ],
)
def test_insecure_production_configuration_fails(override: dict[str, str], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        production_settings(**override)
