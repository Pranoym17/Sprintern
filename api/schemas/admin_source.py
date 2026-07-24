import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from api.models.enums import IngestionRunStatus, PollCompleteness
from api.schemas.common import APIModel


class AdminSourceCreate(APIModel):
    owner: str = Field(min_length=1, max_length=100)
    repository: str = Field(min_length=1, max_length=100)
    branch: str | None = Field(default=None, min_length=1, max_length=255)
    path: str = Field(default="README.md", min_length=1, max_length=500)
    poll_minutes: int = Field(default=15, ge=5, le=1440)
    jitter_seconds: int = Field(default=30, ge=0, le=300)
    default_term: str | None = Field(default=None, max_length=100)
    parser_schema: str = Field(default="github_markdown_table", max_length=64)
    parser_version: str = Field(default="1", max_length=32)


class AdminSourceUpdate(APIModel):
    owner: str | None = Field(default=None, min_length=1, max_length=100)
    repository: str | None = Field(default=None, min_length=1, max_length=100)
    branch: str | None = Field(default=None, min_length=1, max_length=255)
    path: str | None = Field(default=None, min_length=1, max_length=500)
    poll_minutes: int | None = Field(default=None, ge=5, le=1440)
    jitter_seconds: int | None = Field(default=None, ge=0, le=300)
    default_term: str | None = Field(default=None, max_length=100)
    parser_schema: str | None = Field(default=None, min_length=1, max_length=64)
    parser_version: str | None = Field(default=None, min_length=1, max_length=32)


class SourceStateChange(APIModel):
    enabled: bool
    confirmation: str

    @model_validator(mode="after")
    def validate_confirmation(self) -> "SourceStateChange":
        expected = "ENABLE" if self.enabled else "DISABLE"
        if self.confirmation != expected:
            raise ValueError(f"confirmation must be {expected}")
        return self


class SourceDeleteRequest(APIModel):
    confirmation: str


class AdminSourceResponse(APIModel):
    id: uuid.UUID
    source_key: str
    owner: str
    repository: str
    branch: str | None
    path: str
    enabled: bool
    poll_minutes: int
    jitter_seconds: int
    default_term: str | None
    parser_schema: str
    parser_version: str
    last_validated_at: datetime | None
    last_succeeded_at: datetime | None = None
    last_failed_at: datetime | None = None
    consecutive_failures: int = 0
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class PreviewSample(APIModel):
    company: str
    title: str
    location: str | None
    term: str | None
    application_url: str
    application_domain: str | None
    canonical_fingerprint: str


class TermSummary(APIModel):
    term: str
    count: int


class SourcePreviewResponse(APIModel):
    rows_fetched: int
    accepted: int
    rejected: int
    duplicate_candidates: int
    sample_normalized_output: list[PreviewSample]
    detected_table_schema: str
    missing_columns: list[str]
    rejected_rows: list[str]
    suspicious_truncated_values: list[str]
    inferred_terms: list[TermSummary]
    application_domains: list[str]


class AdminRunResponse(APIModel):
    id: uuid.UUID
    status: IngestionRunStatus
    completeness: PollCompleteness | None
    started_at: datetime
    finished_at: datetime | None
    fetched_count: int
    accepted_count: int
    rejected_count: int
    created_count: int
    updated_count: int
    duplicate_count: int
    error: str | None


class SourceAuditResponse(APIModel):
    id: uuid.UUID
    source_configuration_id: uuid.UUID | None
    administrator_id: uuid.UUID
    action: str
    details: dict[str, Any]
    request_id: str | None
    created_at: datetime


class AdminAccessResponse(APIModel):
    administrator: Literal[True] = True
