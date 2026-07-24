import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from api.models.enums import ApplicationStage
from api.schemas.common import APIModel, strip_internal_origin
from api.schemas.job import PublicJobResponse


class ApplicationCreate(APIModel):
    job_id: uuid.UUID
    stage: ApplicationStage = ApplicationStage.SAVED
    notes: str | None = Field(default=None, max_length=10_000)
    deadline_at: datetime | None = None
    follow_up_at: datetime | None = None
    interview_at: datetime | None = None
    contact: str | None = Field(default=None, max_length=300)
    resume_version: str | None = Field(default=None, max_length=200)
    application_url: str | None = Field(default=None, max_length=2000)
    applied_at: datetime | None = None
    outcome: str | None = Field(default=None, max_length=100)


class ApplicationUpdate(APIModel):
    stage: ApplicationStage | None = None
    notes: str | None = Field(default=None, max_length=10_000)
    deadline_at: datetime | None = None
    follow_up_at: datetime | None = None
    interview_at: datetime | None = None
    contact: str | None = Field(default=None, max_length=300)
    resume_version: str | None = Field(default=None, max_length=200)
    application_url: str | None = Field(default=None, max_length=2000)
    applied_at: datetime | None = None
    outcome: str | None = Field(default=None, max_length=100)


class ApplicationCorrection(APIModel):
    note: str = Field(min_length=1, max_length=500)


class ApplicationEventResponse(APIModel):
    id: uuid.UUID
    event_type: str
    data: dict[str, Any]
    corrected_event_id: uuid.UUID | None
    created_at: datetime

    _strip_origin = field_validator("data", mode="before")(strip_internal_origin)


class ApplicationResponse(APIModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    stage: ApplicationStage
    notes: str | None
    deadline_at: datetime | None
    follow_up_at: datetime | None
    interview_at: datetime | None
    contact: str | None
    resume_version: str | None
    application_url: str | None
    applied_at: datetime | None
    outcome: str | None
    created_at: datetime
    updated_at: datetime
    job: PublicJobResponse
    events: list[ApplicationEventResponse]


class CSVImportRequest(APIModel):
    csv_text: str = Field(min_length=1, max_length=2_000_000)
    mapping: dict[str, str]
    dry_run: bool = True


class CSVImportRow(APIModel):
    row: int
    status: str
    message: str


class CSVImportResponse(APIModel):
    total_rows: int
    valid_rows: int
    imported_rows: int
    duplicate_rows: int
    errors: list[CSVImportRow]
    detected_columns: list[str]


class WeeklyGoalUpdate(APIModel):
    target: int = Field(ge=0, le=100)
    reminders_enabled: bool = False
    streaks_enabled: bool = True


class WeeklyProgress(APIModel):
    target: int
    applied: int
    interviews: int
    offers: int
    current_streak: int
    best_streak: int
    reminders_enabled: bool
    streaks_enabled: bool
