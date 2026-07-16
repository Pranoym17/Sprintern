import uuid
from datetime import datetime
from typing import Literal

from api.schemas.common import APIModel


class SchedulerJobStatus(APIModel):
    id: str
    next_run_at: datetime | None


class SchedulerStatusResponse(APIModel):
    state: Literal["healthy", "stale", "stopped", "unknown"]
    instance_id: uuid.UUID | None = None
    version: str | None = None
    started_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    heartbeat_age_seconds: float | None = None
    stopped_at: datetime | None = None
    configured_jobs: list[SchedulerJobStatus]
    last_error: str | None = None
