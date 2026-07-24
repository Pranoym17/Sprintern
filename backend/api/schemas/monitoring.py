from datetime import datetime
from typing import Literal

from api.schemas.common import APIModel


class LaunchCheck(APIModel):
    key: str
    configured: bool
    required: bool = True
    guidance: str


class LaunchReadinessResponse(APIModel):
    ready: bool
    checks: list[LaunchCheck]


class GitHubRateLimitStatus(APIModel):
    state: Literal["healthy", "warning", "unavailable"]
    remaining: int | None = None
    limit: int | None = None
    resets_at: datetime | None = None


class OperationalStatusResponse(APIModel):
    state: Literal["healthy", "degraded"]
    scheduler_state: str
    enabled_sources: int
    failing_sources: int
    stale_sources: int
    unresolved_parser_alerts: int
    resend_problem_events_24h: int
    database_bytes: int
    database_capacity_warning: bool
    github: GitHubRateLimitStatus
