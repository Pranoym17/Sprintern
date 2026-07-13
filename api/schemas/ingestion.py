import uuid
from datetime import datetime
from typing import Any

from api.models import JobSourceName
from api.schemas.common import APIModel


class SourceStatusResponse(APIModel):
    id: uuid.UUID
    source: JobSourceName
    source_key: str
    cursor: dict[str, Any]
    consecutive_failures: int
    backoff_until: datetime | None
    last_started_at: datetime | None
    last_succeeded_at: datetime | None
    last_failed_at: datetime | None
    last_error: str | None
