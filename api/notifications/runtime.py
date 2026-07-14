import httpx
from sqlalchemy.orm import Session, sessionmaker

from api.database import SessionLocal
from api.models import NotificationChannel
from api.notifications.dispatcher import NotificationDispatcher
from api.notifications.providers import NotificationProvider, ResendProvider, TelegramProvider
from api.settings import settings


def build_dispatcher(
    client: httpx.AsyncClient,
    session_factory: sessionmaker[Session] = SessionLocal,
) -> NotificationDispatcher:
    providers: dict[NotificationChannel, NotificationProvider] = {}
    if settings.telegram_bot_token:
        providers[NotificationChannel.TELEGRAM] = TelegramProvider(
            settings.telegram_bot_token, client
        )
    if settings.resend_api_key and settings.resend_from_email:
        providers[NotificationChannel.EMAIL] = ResendProvider(
            settings.resend_api_key, settings.resend_from_email, client
        )
    return NotificationDispatcher(
        session_factory,
        providers,
        max_attempts=settings.notification_max_attempts,
        lease_seconds=settings.notification_lease_seconds,
    )
