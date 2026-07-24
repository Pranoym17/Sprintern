import uuid
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator

from api.models.enums import (
    ApplicationStage,
    DeliveryStatus,
    MatchStatus,
    NotificationCadence,
    NotificationChannel,
    WorkMode,
)
from api.schemas.common import APIModel, strip_internal_origin


class ProfileUpdate(APIModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    notification_cadence: NotificationCadence | None = None
    email_notifications_enabled: bool | None = None
    preferred_email_time: time | None = None
    email_digest_job_limit: int | None = Field(default=None, ge=1, le=10)
    email_empty_digest_enabled: bool | None = None
    telegram_notifications_enabled: bool | None = None
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    weekend_pause: bool | None = None
    max_alerts_per_day: int | None = Field(default=None, ge=1, le=500)
    priority_only_instant: bool | None = None
    notification_consents: dict[str, bool] | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class ProfileResponse(APIModel):
    id: uuid.UUID
    email: str | None
    timezone: str
    notification_cadence: NotificationCadence
    telegram_chat_id: str | None
    email_notifications_enabled: bool
    email_notifications_consent_at: datetime | None
    email_suppressed_at: datetime | None
    email_suppression_reason: str | None
    preferred_email_time: time
    email_digest_job_limit: int
    email_empty_digest_enabled: bool
    telegram_notifications_enabled: bool
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    weekend_pause: bool
    max_alerts_per_day: int
    priority_only_instant: bool
    notification_consents: dict[str, bool]
    created_at: datetime
    updated_at: datetime


class TelegramLinkResponse(APIModel):
    token: str
    deep_link: str
    expires_at: datetime


class AccountDeletionResponse(APIModel):
    application_data_deleted: bool
    auth_identity_deleted: bool


class AccountDeletionRequest(APIModel):
    confirmation: str = Field(min_length=6, max_length=6)


class AccountExportProfile(APIModel):
    id: uuid.UUID
    email: str | None
    timezone: str
    notification_cadence: NotificationCadence
    email_notifications_enabled: bool
    email_notifications_consent_at: datetime | None
    preferred_email_time: time
    email_digest_job_limit: int
    email_empty_digest_enabled: bool
    telegram_connected: bool
    telegram_notifications_enabled: bool
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    weekend_pause: bool
    max_alerts_per_day: int
    priority_only_instant: bool
    notification_consents: dict[str, bool]
    created_at: datetime


class AccountExportFilter(APIModel):
    id: uuid.UUID
    name: str
    role_keywords: list[str]
    location_keywords: list[str]
    terms: list[str]
    work_mode: WorkMode
    active: bool


class AccountExportJob(APIModel):
    id: uuid.UUID | None = None
    company: str
    title: str
    location: str | None = None
    term: str | None = None


class AccountExportDelivery(APIModel):
    channel: NotificationChannel
    status: DeliveryStatus
    sent_at: datetime | None


class AccountExportMatch(APIModel):
    id: uuid.UUID
    status: MatchStatus
    applied_at: datetime | None
    reasons: dict[str, Any] | list[Any]
    job: AccountExportJob
    deliveries: list[AccountExportDelivery]


class AccountExportTimelineEvent(APIModel):
    id: uuid.UUID
    event_type: str
    data: dict[str, Any]
    corrected_event_id: uuid.UUID | None
    created_at: datetime

    _strip_origin = field_validator("data", mode="before")(strip_internal_origin)


class AccountExportApplication(APIModel):
    id: uuid.UUID
    job_id: uuid.UUID
    company: str
    title: str
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
    timeline: list[AccountExportTimelineEvent]


class AccountExportResponse(APIModel):
    exported_at: datetime
    profile: AccountExportProfile
    filters: list[AccountExportFilter]
    matches: list[AccountExportMatch]
    applications: list[AccountExportApplication]
