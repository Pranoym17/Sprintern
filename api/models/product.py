import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.models.base import TimestampMixin
from api.models.enums import (
    ApplicationStage,
    ExclusionType,
    JobSourceName,
    NotificationCadence,
    NotificationPriority,
    ReminderType,
    ReportReason,
)


class JobInteraction(TimestampMixin, Base):
    __tablename__ = "job_interactions"
    __table_args__ = (
        UniqueConstraint("profile_id", "job_id", name="uq_job_interactions_profile_job"),
        Index("ix_job_interactions_profile_recent", "profile_id", "last_viewed_at"),
        Index("ix_job_interactions_profile_hidden", "profile_id", "hidden_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    bookmarked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    not_interested_reason: Mapped[str | None] = mapped_column(String(64))
    first_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    deadline_override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job = relationship("Job")


class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("profile_id", "job_id", name="uq_applications_profile_job"),
        Index("ix_applications_profile_stage", "profile_id", "stage"),
        Index("ix_applications_profile_follow_up", "profile_id", "follow_up_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
    )
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(
            ApplicationStage,
            native_enum=False,
            name="application_stage",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=ApplicationStage.SAVED,
        server_default=ApplicationStage.SAVED.value,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact: Mapped[str | None] = mapped_column(String(300))
    resume_version: Mapped[str | None] = mapped_column(String(200))
    application_url: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(100))
    import_key: Mapped[str | None] = mapped_column(String(64))

    job = relationship("Job")
    events = relationship(
        "ApplicationEvent", back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    __table_args__ = (
        Index("ix_application_events_application_created", "application_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    corrected_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("application_events.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    application = relationship(
        "Application", back_populates="events", foreign_keys=[application_id]
    )


class JobChangeEvent(Base):
    __tablename__ = "job_change_events"
    __table_args__ = (Index("ix_job_change_events_job_created", "job_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32))
    changes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    job = relationship("Job", back_populates="changes")


class JobReport(TimestampMixin, Base):
    __tablename__ = "job_reports"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "job_id", "reason", name="uq_job_reports_profile_job_reason"
        ),
        Index("ix_job_reports_job_status", "job_id", "resolved_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[ReportReason] = mapped_column(
        Enum(
            ReportReason,
            native_enum=False,
            name="report_reason",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    details: Mapped[str | None] = mapped_column(String(500))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShareLink(TimestampMixin, Base):
    __tablename__ = "share_links"
    __table_args__ = (
        Index("ix_share_links_token_hash", "token_hash", unique=True),
        Index("ix_share_links_profile", "profile_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CompanyWatchlist(TimestampMixin, Base):
    __tablename__ = "company_watchlists"
    __table_args__ = (
        UniqueConstraint("profile_id", "normalized_company", name="uq_watchlist_profile_company"),
        Index("ix_watchlists_profile_active", "profile_id", "active"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    company: Mapped[str] = mapped_column(String(200))
    normalized_company: Mapped[str] = mapped_column(String(200))
    terms: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    locations: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class FilterExclusion(Base):
    __tablename__ = "filter_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "filter_id", "kind", "normalized_value", name="uq_filter_exclusions_value"
        ),
        Index("ix_filter_exclusions_filter", "filter_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filters.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[ExclusionType] = mapped_column(
        Enum(
            ExclusionType,
            native_enum=False,
            name="exclusion_type",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    value: Mapped[str] = mapped_column(String(200))
    normalized_value: Mapped[str] = mapped_column(String(200))
    job_filter = relationship("JobFilter", back_populates="exclusions")


class FilterNotificationOverride(TimestampMixin, Base):
    __tablename__ = "filter_notification_overrides"
    filter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("filters.id", ondelete="CASCADE"), primary_key=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email_enabled: Mapped[bool | None] = mapped_column(Boolean)
    telegram_enabled: Mapped[bool | None] = mapped_column(Boolean)
    cadence: Mapped[NotificationCadence | None] = mapped_column(
        Enum(
            NotificationCadence,
            native_enum=False,
            name="override_cadence",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    priority: Mapped[NotificationPriority] = mapped_column(
        Enum(
            NotificationPriority,
            native_enum=False,
            name="notification_priority",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=NotificationPriority.NORMAL,
        server_default=NotificationPriority.NORMAL.value,
    )


class ReminderEvent(TimestampMixin, Base):
    __tablename__ = "reminder_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_reminder_idempotency"),
        Index("ix_reminders_profile_due", "profile_id", "due_at", "sent_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE")
    )
    kind: Mapped[ReminderType] = mapped_column(
        Enum(
            ReminderType,
            native_enum=False,
            name="reminder_type",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WeeklyGoal(TimestampMixin, Base):
    __tablename__ = "weekly_goals"
    __table_args__ = (UniqueConstraint("profile_id", name="uq_weekly_goals_profile"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    target: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    streaks_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class SourceConfiguration(TimestampMixin, Base):
    __tablename__ = "source_configurations"
    __table_args__ = (
        UniqueConstraint("source", "source_key", name="uq_source_config_identity"),
        Index("ix_source_config_enabled", "enabled"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[JobSourceName] = mapped_column(
        Enum(
            JobSourceName,
            native_enum=False,
            name="configured_source_name",
            length=32,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    source_key: Mapped[str] = mapped_column(String(255))
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ParserAlert(TimestampMixin, Base):
    __tablename__ = "parser_alerts"
    __table_args__ = (
        UniqueConstraint("source_key", "fingerprint", name="uq_parser_alert_fingerprint"),
        Index("ix_parser_alert_unresolved", "resolved_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(String(255))
    fingerprint: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(500))
    occurrences: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnonymousOutcomeAggregate(Base):
    __tablename__ = "anonymous_outcome_aggregates"
    __table_args__ = (
        UniqueConstraint(
            "week_start", "normalized_role", "stage", name="uq_outcome_aggregate_bucket"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_start: Mapped[date] = mapped_column(Date)
    normalized_role: Mapped[str] = mapped_column(String(100))
    stage: Mapped[ApplicationStage] = mapped_column(
        Enum(
            ApplicationStage,
            native_enum=False,
            name="aggregate_application_stage",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    conversion_rate: Mapped[float | None] = mapped_column(Float)
