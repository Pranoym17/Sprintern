import uuid
from datetime import datetime

from api.models.enums import JobStatus, WorkMode
from api.schemas.common import APIModel


class PublicJobResponse(APIModel):
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
    deadline_is_estimated: bool
    title_incomplete: bool
    latitude: float | None
    longitude: float | None
    application_url: str


class JobPage(APIModel):
    items: list[PublicJobResponse]
    next_cursor: str | None
