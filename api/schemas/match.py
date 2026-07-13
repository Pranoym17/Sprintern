import uuid
from datetime import datetime
from typing import Any

from api.models.enums import MatchStatus
from api.schemas.common import APIModel
from api.schemas.job import JobResponse


class MatchUpdate(APIModel):
    status: MatchStatus


class MatchResponse(APIModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    reasons: list[dict[str, Any]]
    status: MatchStatus
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime
    job: JobResponse


class MatchPage(APIModel):
    items: list[MatchResponse]
    next_cursor: str | None


class AnalyticsSummary(APIModel):
    matched_count: int
    applied_count: int
    average_seconds_to_apply: float | None
