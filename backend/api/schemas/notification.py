from typing import Any

from pydantic import ConfigDict, Field, field_validator

from api.models.enums import NotificationChannel
from api.schemas.common import APIModel


class TestNotificationRequest(APIModel):
    channel: NotificationChannel


class TestNotificationResponse(APIModel):
    channel: NotificationChannel
    outcome: str
    provider_message_id: str | None = None
    error: str | None = None


class DeliveryQueueSummary(APIModel):
    pending: int = Field(ge=0)
    delayed_by_quiet_hours: int = Field(ge=0)
    delayed_by_weekend: int = Field(ge=0)
    delayed_by_daily_cap: int = Field(ge=0)
    failed: int = Field(ge=0)
    suppressed: int = Field(ge=0)


class TelegramChat(APIModel):
    model_config = ConfigDict(extra="allow")

    id: int | str


class TelegramMessage(APIModel):
    model_config = ConfigDict(extra="allow")

    text: str | None = None
    chat: TelegramChat | None = None


class TelegramUpdate(APIModel):
    model_config = ConfigDict(extra="allow")

    update_id: int | None = None
    message: TelegramMessage | None = None


class ResendEventData(APIModel):
    model_config = ConfigDict(extra="allow")

    to: list[str] = Field(default_factory=list)

    @field_validator("to", mode="before")
    @classmethod
    def normalize_recipients(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        return value if isinstance(value, list) else []


class ResendWebhookEvent(APIModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    type: str
    data: ResendEventData | None = None
