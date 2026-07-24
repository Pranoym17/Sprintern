import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.launch import launch_readiness, operational_status
from api.models import (
    JobSourceName,
    SchedulerRuntime,
    SourceConfiguration,
    SourceState,
)
from api.settings import settings


def test_launch_readiness_requires_provider_owned_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "resend_api_key", "resend")
    monkeypatch.setattr(settings, "resend_from_email", "Sprintern <alerts@sprintern.ca>")
    monkeypatch.setattr(settings, "resend_webhook_secret", "webhook")
    monkeypatch.setattr(settings, "dmarc_configured", True)
    monkeypatch.setattr(settings, "supabase_custom_smtp_configured", True)
    monkeypatch.setattr(settings, "google_oauth_configured", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "bot")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "telegram-secret")
    monkeypatch.setattr(settings, "support_email", "support@sprintern.ca")
    monkeypatch.setattr(settings, "error_tracking_dsn", "https://public@sentry.example/1")
    monkeypatch.setattr(settings, "database_backups_configured", True)
    monkeypatch.setattr(settings, "rls_verified", True)
    monkeypatch.setattr(settings, "uptime_monitor_configured", True)
    monkeypatch.setattr(settings, "scheduler_monitor_configured", True)

    result = launch_readiness()

    assert result.ready is True
    assert all(check.configured for check in result.checks)


async def test_operational_status_collects_safe_monitoring_signals(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    source_key = "owner/repository:README.md"
    db_session.add_all(
        [
            SourceConfiguration(
                source=JobSourceName.GITHUB_REPO,
                source_key=source_key,
                configuration={},
                owner="owner",
                repository="repository",
                branch="main",
                path="README.md",
                enabled=True,
            ),
            SourceState(
                source=JobSourceName.GITHUB_REPO,
                source_key=source_key,
                cursor={},
                last_succeeded_at=now,
            ),
            SchedulerRuntime(
                name="default",
                instance_id=uuid.uuid4(),
                version="test",
                started_at=now,
                last_heartbeat_at=now,
                jobs=[],
            ),
        ]
    )
    db_session.flush()
    monkeypatch.setattr(settings, "database_capacity_warning_bytes", 10**15)
    monkeypatch.setattr(settings, "github_rate_limit_warning_remaining", 500)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"].startswith("Bearer ")
        return httpx.Response(
            200,
            json={"resources": {"core": {"remaining": 4_000, "limit": 5_000, "reset": 0}}},
        )

    monkeypatch.setattr(settings, "github_token", "github-secret")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await operational_status(db_session, client, now=now)

    assert result.state == "healthy"
    assert result.scheduler_state == "healthy"
    assert result.enabled_sources == 1
    assert result.github.remaining == 4_000
    assert result.database_bytes > 0


def test_user_data_tables_have_row_level_security(db_session: Session) -> None:
    protected = {
        row[0]: row[1]
        for row in db_session.execute(
            text(
                """
                SELECT relname, relrowsecurity
                FROM pg_class
                WHERE relname IN (
                  'profiles', 'filters', 'matches', 'notification_deliveries',
                  'applications', 'source_configurations'
                )
                """
            )
        )
    }
    policies = set(
        db_session.scalars(
            text(
                """
                SELECT policyname
                FROM pg_policies
                WHERE schemaname = 'public'
                """
            )
        )
    )

    assert protected and all(protected.values())
    assert "profiles_owner_access" in policies
    assert "filters_owner_access" in policies
    assert "applications_owner_access" in policies
