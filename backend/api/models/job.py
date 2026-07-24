import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.models.base import TimestampMixin
from api.models.enums import DeadlineSource, InternshipStatus, JobSourceName, JobStatus, WorkMode


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_posted", "status", "posted_at"),
        Index("ix_jobs_fingerprint", "canonical_fingerprint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company: Mapped[str] = mapped_column(String(200))
    normalized_company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    normalized_title: Mapped[str] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(300))
    normalized_location: Mapped[str | None] = mapped_column(String(300))
    term: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    internship_status: Mapped[InternshipStatus] = mapped_column(
        Enum(
            InternshipStatus,
            native_enum=False,
            create_constraint=True,
            name="internship_status",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=InternshipStatus.UNKNOWN,
        server_default=InternshipStatus.UNKNOWN.value,
    )
    matcher_version: Mapped[str | None] = mapped_column(String(32))
    work_mode: Mapped[WorkMode] = mapped_column(
        Enum(
            WorkMode,
            native_enum=False,
            create_constraint=True,
            name="job_work_mode",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=WorkMode.UNKNOWN,
        server_default=WorkMode.UNKNOWN.value,
    )
    canonical_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            native_enum=False,
            create_constraint=True,
            name="job_status",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=JobStatus.ACTIVE,
        server_default=JobStatus.ACTIVE.value,
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_source: Mapped[DeadlineSource | None] = mapped_column(
        Enum(
            DeadlineSource,
            native_enum=False,
            create_constraint=True,
            name="deadline_source",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    title_incomplete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    sources = relationship("JobSource", back_populates="job", cascade="all, delete-orphan")
    matches = relationship("JobMatch", back_populates="job")
    changes = relationship("JobChangeEvent", back_populates="job", cascade="all, delete-orphan")

    @property
    def application_url(self) -> str:
        """Expose one destination without leaking the internal ingestion origin."""
        if not self.sources:
            return ""
        preferred = min(
            self.sources,
            key=lambda item: (
                not item.active,
                urlparse(item.apply_url).hostname in {"github.com", "www.github.com"},
                item.source == JobSourceName.GITHUB_REPO,
            ),
        )
        return str(preferred.apply_url)

    @property
    def deadline_is_estimated(self) -> bool:
        return self.deadline_source == DeadlineSource.INFERRED


class JobSource(TimestampMixin, Base):
    __tablename__ = "job_sources"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_key",
            "external_id",
            "occurrence",
            name="uq_job_sources_identity",
        ),
        Index("ix_job_sources_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[JobSourceName] = mapped_column(
        Enum(
            JobSourceName,
            native_enum=False,
            create_constraint=True,
            name="job_source_name",
            length=32,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    source_key: Mapped[str] = mapped_column(String(255))
    external_id: Mapped[str] = mapped_column(String(500))
    occurrence: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    source_url: Mapped[str | None] = mapped_column(Text)
    apply_url: Mapped[str] = mapped_column(Text)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    missing_snapshot_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    job = relationship("Job", back_populates="sources")
