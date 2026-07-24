from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from api.models import (
    EmailProviderEvent,
    JobSourceName,
    ParserAlert,
    SourceConfiguration,
    SourceState,
)
from api.scheduler.status import scheduler_status
from api.schemas.monitoring import (
    GitHubRateLimitStatus,
    LaunchCheck,
    LaunchReadinessResponse,
    OperationalStatusResponse,
)
from api.settings import Settings, settings


def _rls_is_active(session: Session) -> bool:
    expected = {
        "profiles",
        "filters",
        "matches",
        "notification_deliveries",
        "applications",
        "source_configurations",
    }
    enabled = set(
        session.scalars(
            text(
                """
                SELECT relname
                FROM pg_class
                WHERE relnamespace = 'public'::regnamespace
                  AND relrowsecurity
                """
            )
        )
    )
    return expected.issubset(enabled)


def launch_readiness(
    app_settings: Settings = settings, session: Session | None = None
) -> LaunchReadinessResponse:
    """Report provider-owned launch controls without exposing their configured values."""
    support_ready = bool(
        app_settings.support_email
        and "your-domain" not in app_settings.support_email
        and "example" not in app_settings.support_email
    )
    checks = [
        LaunchCheck(
            key="production_mode",
            configured=app_settings.app_env.casefold() == "production",
            guidance="Set APP_ENV=production for the deployed API and scheduler.",
        ),
        LaunchCheck(
            key="resend_delivery",
            configured=bool(
                app_settings.resend_api_key
                and app_settings.resend_from_email
                and app_settings.resend_webhook_secret
            ),
            guidance="Configure the Resend sending key, verified sender, and event webhook secret.",
        ),
        LaunchCheck(
            key="dmarc",
            configured=app_settings.dmarc_configured,
            guidance="Publish and verify a DMARC record for the sending domain.",
        ),
        LaunchCheck(
            key="supabase_custom_smtp",
            configured=app_settings.supabase_custom_smtp_configured,
            guidance="Configure Supabase Auth to send through the production SMTP provider.",
        ),
        LaunchCheck(
            key="google_oauth",
            configured=app_settings.google_oauth_configured,
            guidance="Configure the production Google OAuth origin and callback URL.",
        ),
        LaunchCheck(
            key="telegram_webhook",
            configured=bool(
                app_settings.telegram_bot_token and app_settings.telegram_webhook_secret
            ),
            guidance="Register the production HTTPS Telegram webhook and secret.",
        ),
        LaunchCheck(
            key="support_email",
            configured=support_ready,
            guidance="Use a monitored support address in SUPPORT_EMAIL.",
        ),
        LaunchCheck(
            key="error_tracking",
            configured=bool(app_settings.error_tracking_dsn),
            guidance="Set ERROR_TRACKING_DSN for the API and scheduler.",
        ),
        LaunchCheck(
            key="database_backups",
            configured=app_settings.database_backups_configured,
            guidance="Enable and restore-test Supabase backups.",
        ),
        LaunchCheck(
            key="row_level_security",
            configured=app_settings.rls_verified
            and (session is None or _rls_is_active(session)),
            guidance="Run the RLS migration and verify policies with authenticated test users.",
        ),
        LaunchCheck(
            key="uptime_monitor",
            configured=app_settings.uptime_monitor_configured,
            guidance="Monitor /health/live and /health/ready from outside the deployment.",
        ),
        LaunchCheck(
            key="scheduler_monitor",
            configured=app_settings.scheduler_monitor_configured,
            guidance="Alert when the protected scheduler status reports stale or stopped.",
        ),
    ]
    return LaunchReadinessResponse(
        ready=all(check.configured for check in checks if check.required),
        checks=checks,
    )


def _parse_rate_reset(value: Any) -> datetime | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str):
        try:
            return datetime.fromtimestamp(int(value), UTC)
        except ValueError:
            try:
                return parsedate_to_datetime(value).astimezone(UTC)
            except (TypeError, ValueError):
                return None
    return None


async def github_rate_limit_status(
    client: httpx.AsyncClient, app_settings: Settings = settings
) -> GitHubRateLimitStatus:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": app_settings.source_user_agent,
    }
    if app_settings.github_token:
        headers["Authorization"] = f"Bearer {app_settings.github_token}"
    try:
        response = await client.get("https://api.github.com/rate_limit", headers=headers)
        response.raise_for_status()
        payload = response.json()
        core = payload["resources"]["core"]
        remaining = int(core["remaining"])
        limit = int(core["limit"])
        return GitHubRateLimitStatus(
            state=(
                "warning"
                if remaining <= app_settings.github_rate_limit_warning_remaining
                else "healthy"
            ),
            remaining=remaining,
            limit=limit,
            resets_at=_parse_rate_reset(core.get("reset")),
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return GitHubRateLimitStatus(state="unavailable")


async def operational_status(
    session: Session,
    client: httpx.AsyncClient,
    app_settings: Settings = settings,
    now: datetime | None = None,
) -> OperationalStatusResponse:
    now = now or datetime.now(UTC)
    enabled_keys = set(
        session.scalars(
            select(SourceConfiguration.source_key).where(SourceConfiguration.enabled.is_(True))
        )
    )
    source_rows = list(
        session.scalars(
            select(SourceState).where(
                SourceState.source == JobSourceName.GITHUB_REPO,
                SourceState.source_key.in_(enabled_keys),
            )
        )
    )
    state_by_key = {row.source_key: row for row in source_rows}
    stale_before = now - timedelta(hours=app_settings.source_stale_after_hours)
    failing_sources = sum(
        1
        for key in enabled_keys
        if (row := state_by_key.get(key)) is not None and row.consecutive_failures > 0
    )
    stale_sources = sum(
        1
        for key in enabled_keys
        if (row := state_by_key.get(key)) is None
        or row.last_succeeded_at is None
        or row.last_succeeded_at < stale_before
    )
    parser_alerts = int(
        session.scalar(
            select(func.count()).select_from(ParserAlert).where(ParserAlert.resolved_at.is_(None))
        )
        or 0
    )
    resend_events = int(
        session.scalar(
            select(func.count())
            .select_from(EmailProviderEvent)
            .where(
                EmailProviderEvent.received_at >= now - timedelta(hours=24),
                EmailProviderEvent.event_type.in_(
                    ("email.bounced", "email.complained", "email.suppressed")
                ),
            )
        )
        or 0
    )
    database_bytes = int(session.scalar(text("SELECT pg_database_size(current_database())")) or 0)
    scheduler = scheduler_status(
        session, app_settings.scheduler_heartbeat_interval_seconds, now=now
    )
    github = await github_rate_limit_status(client, app_settings)
    degraded = any(
        (
            scheduler.state != "healthy",
            failing_sources > 0,
            stale_sources > 0,
            parser_alerts > 0,
            database_bytes >= app_settings.database_capacity_warning_bytes,
            github.state != "healthy",
        )
    )
    return OperationalStatusResponse(
        state="degraded" if degraded else "healthy",
        scheduler_state=scheduler.state,
        enabled_sources=len(enabled_keys),
        failing_sources=failing_sources,
        stale_sources=stale_sources,
        unresolved_parser_alerts=parser_alerts,
        resend_problem_events_24h=resend_events,
        database_bytes=database_bytes,
        database_capacity_warning=(
            database_bytes >= app_settings.database_capacity_warning_bytes
        ),
        github=github,
    )
