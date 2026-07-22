import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from api.models.enums import ReportReason
from api.schemas.common import APIModel
from api.schemas.job import JobResponse


class InteractionUpdate(APIModel):
    bookmarked: bool | None = None
    hidden: bool | None = None
    not_interested_reason: (
        Literal[
            "wrong_role",
            "wrong_location",
            "wrong_term",
            "authorization",
            "unpaid",
            "not_internship",
            "company_preference",
            "other",
        ]
        | None
    ) = None
    deadline_override_at: datetime | None = None

    @model_validator(mode="after")
    def require_change(self) -> "InteractionUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one interaction field is required")
        return self


class InteractionResponse(APIModel):
    job_id: uuid.UUID
    bookmarked_at: datetime | None
    hidden_at: datetime | None
    not_interested_reason: str | None
    first_viewed_at: datetime | None
    last_viewed_at: datetime | None
    view_count: int
    deadline_override_at: datetime | None


class JobReportCreate(APIModel):
    reason: ReportReason
    details: str | None = Field(default=None, max_length=500)


class JobReportResponse(APIModel):
    id: uuid.UUID
    job_id: uuid.UUID
    reason: ReportReason
    details: str | None
    created_at: datetime


class ShareCreate(APIModel):
    expires_in_hours: int = Field(default=72, ge=1, le=720)


class ShareResponse(APIModel):
    id: uuid.UUID
    url: str
    expires_at: datetime


class PublicJobResponse(APIModel):
    job: JobResponse
    shared_until: datetime | None = None
