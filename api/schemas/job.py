import uuid
from datetime import datetime

from api.models.enums import DeadlineSource, JobSourceName, JobStatus, WorkMode
from api.schemas.common import APIModel


class JobSourceResponse(APIModel):
    source: JobSourceName
    external_id: str
    source_url: str | None
    apply_url: str


class JobResponse(APIModel):
    id: uuid.UUID
    company: str
    title: str
    location: str | None
    term: str | None
    description: str | None
    work_mode: WorkMode
    status: JobStatus
    posted_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    reopened_at: datetime | None
    deadline_at: datetime | None
    deadline_source: DeadlineSource | None
    title_incomplete: bool
    latitude: float | None
    longitude: float | None
    sources: list[JobSourceResponse]


class JobPage(APIModel):
    items: list[JobResponse]
    next_cursor: str | None
