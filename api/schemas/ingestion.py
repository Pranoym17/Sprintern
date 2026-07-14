import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import model_validator

from api.models import IngestionRunStatus, JobSourceName, PollCompleteness
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


class IngestionRunRequest(APIModel):
    source: JobSourceName
    company: str | None = None
    board_token: str | None = None
    site: str | None = None
    region: Literal["global", "eu"] = "global"
    owner: str | None = None
    repository: str | None = None
    path: str = "README.md"
    branch: str | None = None
    term: str | None = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> "IngestionRunRequest":
        required: dict[JobSourceName, tuple[str, ...]] = {
            JobSourceName.GREENHOUSE: ("company", "board_token"),
            JobSourceName.LEVER: ("company", "site"),
            JobSourceName.GITHUB_REPO: ("owner", "repository"),
            JobSourceName.REMOTEOK: (),
        }
        if self.source not in required:
            raise ValueError("source is not implemented in the MVP")
        missing = [field for field in required[self.source] if not getattr(self, field)]
        if missing:
            raise ValueError(f"missing fields for {self.source.value}: {', '.join(missing)}")
        return self


class IngestionRunResponse(APIModel):
    id: uuid.UUID
    status: IngestionRunStatus
    completeness: PollCompleteness | None
    fetched_count: int
    accepted_count: int
    rejected_count: int
    created_count: int
    updated_count: int
    duplicate_count: int
    error: str | None
