import logging
import secrets
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.database import get_db
from api.errors import AppError
from api.ingestion.http import RetryingHTTPClient, SourceHTTPError
from api.models import JobFilter, Profile
from api.notifications.telegram_linking import telegram_link_service
from api.rate_limiting import ip_rate_limit
from api.schemas.notification import TelegramUpdate
from api.settings import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"], include_in_schema=False)
Database = Annotated[Session, Depends(get_db)]
HELP = (
    "Sprintern commands:\n"
    "/status - connection and alert status\n"
    "/filters - active filters\n"
    "/pause - pause Telegram alerts\n"
    "/resume - resume Telegram alerts\n"
    "/help - show this message"
)
logger = logging.getLogger(__name__)


async def _reply(chat_id: str, text: str) -> None:
    if not settings.telegram_bot_token:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await RetryingHTTPClient(client, max_attempts=3).post_json(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4096]},
            )
        except SourceHTTPError:
            logger.warning(
                "telegram.command_reply.failed",
                extra={"event": "telegram.command_reply.failed"},
            )


@router.post(
    "/telegram",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(ip_rate_limit("webhooks.telegram", 120))],
)
async def telegram_webhook(
    payload: TelegramUpdate,
    session: Database,
    secret_token: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> None:
    if not settings.telegram_webhook_secret:
        raise AppError(503, "not_configured", "Telegram webhook is not configured")
    if secret_token is None or not secrets.compare_digest(
        secret_token, settings.telegram_webhook_secret
    ):
        raise AppError(401, "invalid_webhook_secret", "Invalid Telegram webhook secret")
    message = payload.message
    if message is None or message.text is None or message.chat is None:
        return
    text = message.text
    chat_id = str(message.chat.id)
    command, _, argument = text.strip().partition(" ")
    command = command.split("@", 1)[0].casefold()
    if command == "/start" and argument:
        if telegram_link_service.consume(session, argument.strip(), chat_id):
            session.commit()
            await _reply(chat_id, f"Telegram is linked to Sprintern.\n\n{HELP}")
        return

    profile = session.scalar(select(Profile).where(Profile.telegram_chat_id == chat_id))
    if profile is None:
        await _reply(chat_id, "Link this chat from Sprintern settings before using commands.")
        return
    if command == "/pause":
        profile.telegram_notifications_enabled = False
        session.commit()
        await _reply(chat_id, "Telegram alerts are paused. Use /resume when you are ready.")
    elif command == "/resume":
        profile.telegram_notifications_enabled = True
        session.commit()
        await _reply(chat_id, "Telegram alerts are active.")
    elif command == "/status":
        state = "active" if profile.telegram_notifications_enabled else "paused"
        await _reply(
            chat_id, f"Telegram alerts: {state}\nCadence: {profile.notification_cadence.value}"
        )
    elif command == "/filters":
        filters = list(
            session.scalars(
                select(JobFilter)
                .where(JobFilter.profile_id == profile.id, JobFilter.active.is_(True))
                .order_by(JobFilter.name)
            )
        )
        body = "\n".join(f"- {item.name}" for item in filters) or "No active filters."
        await _reply(chat_id, f"Active filters:\n{body}")
    else:
        await _reply(chat_id, HELP)
