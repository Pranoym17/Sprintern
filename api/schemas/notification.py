from pydantic import Field

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
