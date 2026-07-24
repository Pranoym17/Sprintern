from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_db
from api.errors import AppError
from api.models import DeliveryStatus, NotificationChannel, NotificationDelivery
from api.notifications.domain import NotificationMessage
from api.notifications.providers import ResendProvider, TelegramProvider
from api.rate_limiting import user_rate_limit
from api.repositories.profiles import get_or_create_profile
from api.schemas.notification import (
    DeliveryQueueSummary,
    TestNotificationRequest,
    TestNotificationResponse,
)
from api.settings import settings

router = APIRouter(prefix="/notifications", tags=["notifications"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/queue", response_model=DeliveryQueueSummary)
def queue_summary(user: CurrentUser, session: Database) -> DeliveryQueueSummary:
    rows: dict[str | None, int] = {
        reason: count
        for reason, count in session.execute(
            select(NotificationDelivery.queued_reason, func.count(NotificationDelivery.id))
            .where(
                NotificationDelivery.profile_id == user.id,
                NotificationDelivery.status.in_([DeliveryStatus.PENDING, DeliveryStatus.FAILED]),
            )
            .group_by(NotificationDelivery.queued_reason)
        )
    }
    failed = (
        session.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.profile_id == user.id,
                NotificationDelivery.status == DeliveryStatus.FAILED,
            )
        )
        or 0
    )
    suppressed = (
        session.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.profile_id == user.id,
                NotificationDelivery.status == DeliveryStatus.CANCELLED,
            )
        )
        or 0
    )
    return DeliveryQueueSummary(
        pending=sum(rows.values()),
        delayed_by_quiet_hours=rows.get("quiet_hours", 0),
        delayed_by_weekend=rows.get("weekend_pause", 0),
        delayed_by_daily_cap=rows.get("daily_cap", 0),
        failed=failed,
        suppressed=suppressed,
    )


@router.post(
    "/test",
    response_model=TestNotificationResponse,
    dependencies=[Depends(user_rate_limit("notifications.test", 5, 300))],
)
async def send_test_notification(
    payload: TestNotificationRequest, user: CurrentUser, session: Database
) -> TestNotificationResponse:
    profile = get_or_create_profile(session, user.id, user.email)
    if payload.channel == NotificationChannel.EMAIL:
        if not profile.email or not profile.email_notifications_enabled:
            raise AppError(409, "channel_disabled", "Enable email alerts before testing")
        recipient = profile.email
    else:
        if not profile.telegram_chat_id or not profile.telegram_notifications_enabled:
            raise AppError(409, "channel_disabled", "Enable Telegram alerts before testing")
        recipient = profile.telegram_chat_id
    message = NotificationMessage(
        recipient=recipient,
        subject="Sprintern test alert",
        text="Your Sprintern notifications are configured correctly.",
        html="<h2>Sprintern test alert</h2><p>Your notifications are configured correctly.</p>",
        apply_url=settings.public_api_url,
        idempotency_key=f"test:{user.id}:{payload.channel.value}",
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        provider = (
            ResendProvider(settings.resend_api_key, settings.resend_from_email, client)
            if payload.channel == NotificationChannel.EMAIL
            else TelegramProvider(settings.telegram_bot_token, client)
        )
        result = await provider.send(message)
    return TestNotificationResponse(
        channel=payload.channel,
        outcome=result.outcome.value,
        provider_message_id=result.provider_message_id,
        error=result.error,
    )
