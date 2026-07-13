import uuid
from datetime import datetime

from pydantic import Field

from api.models.enums import NotificationCadence
from api.schemas.common import APIModel


class ProfileUpdate(APIModel):
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    notification_cadence: NotificationCadence | None = None
    telegram_chat_id: str | None = Field(default=None, max_length=64)


class ProfileResponse(APIModel):
    id: uuid.UUID
    email: str | None
    timezone: str
    notification_cadence: NotificationCadence
    telegram_chat_id: str | None
    created_at: datetime
    updated_at: datetime
