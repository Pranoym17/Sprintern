import uuid
from datetime import datetime
from typing import Any

from pydantic import field_validator

from api.models.enums import (
    DeliveryStatus,
    MatchStatus,
    NotificationCadence,
    NotificationChannel,
    NotificationPriority,
)
from api.schemas.common import APIModel, strip_internal_origin
from api.schemas.job import JobResponse


class MatchUpdate(APIModel):
    status: MatchStatus


class DeliverySummary(APIModel):
    channel: NotificationChannel
    status: DeliveryStatus
    cadence: NotificationCadence
    priority: NotificationPriority
    queued_reason: str | None
    sent_at: datetime | None


class MatchResponse(APIModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    reasons: list[dict[str, Any]]
    status: MatchStatus
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
    job: JobResponse
    deliveries: list[DeliverySummary]

    _strip_origin = field_validator("reasons", mode="before")(strip_internal_origin)


class MatchPage(APIModel):
    items: list[MatchResponse]
    next_cursor: str | None
    counts: "MatchCounts"


class MatchCounts(APIModel):
    all: int
    matched: int
    applied: int
    dismissed: int


class AnalyticsSummary(APIModel):
    matched_count: int
    applied_count: int
    average_seconds_to_apply: float | None
