import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from api.database import get_db
from api.notifications.telegram_linking import telegram_link_service
from api.rate_limiting import ip_rate_limit
from api.settings import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"], include_in_schema=False)
Database = Annotated[Session, Depends(get_db)]


@router.post(
    "/telegram",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(ip_rate_limit("webhooks.telegram", 120))],
)
def telegram_webhook(
    payload: dict[str, Any],
    session: Database,
    secret_token: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> None:
    if not settings.telegram_webhook_secret:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Telegram webhook is not configured"
        )
    if secret_token is None or not secrets.compare_digest(
        secret_token, settings.telegram_webhook_secret
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Telegram webhook secret")
    message = payload.get("message") or {}
    text = message.get("text")
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not isinstance(text, str) or not text.startswith("/start ") or chat_id is None:
        return
    raw_token = text.split(maxsplit=1)[1].strip()
    if telegram_link_service.consume(session, raw_token, str(chat_id)):
        session.commit()
