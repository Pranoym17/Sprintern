from datetime import datetime
from typing import Any, Protocol

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from api.models import JobSourceName, PollCompleteness, WorkMode


class RawSourceJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(min_length=1, max_length=500)
    company: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    location: str | None = Field(default=None, max_length=300)
    term: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=50_000)
    work_mode: WorkMode = WorkMode.UNKNOWN
    source_url: AnyHttpUrl | None = None
    apply_url: AnyHttpUrl
    posted_at: datetime | None = None
    deadline_at: datetime | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class PollBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[RawSourceJob]
    completeness: PollCompleteness
    next_cursor: dict[str, Any] = Field(default_factory=dict)
    rejected_count: int = Field(default=0, ge=0)
    rejection_errors: list[str] = Field(default_factory=list, max_length=25)
    detected_schema: str | None = None
    missing_columns: list[str] = Field(default_factory=list)


class SourceAdapter(Protocol):
    @property
    def source(self) -> JobSourceName: ...

    @property
    def source_key(self) -> str: ...

    async def fetch(self, cursor: dict[str, Any]) -> PollBatch: ...
