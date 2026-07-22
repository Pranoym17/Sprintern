import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator

from api.models.enums import NotificationCadence
from api.schemas.common import APIModel


class ProfileUpdate(APIModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    notification_cadence: NotificationCadence | None = None
    email_notifications_enabled: bool | None = None
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
