from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_db
from api.errors import AppError
from api.notifications.telegram_linking import telegram_link_service
from api.repositories.profiles import get_or_create_profile
from api.schemas import ProfileResponse, ProfileUpdate
from api.schemas.profile import TelegramLinkResponse
from api.settings import settings

router = APIRouter(prefix="/users", tags=["users"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/me", response_model=ProfileResponse)
def read_me(user: CurrentUser, session: Database) -> object:
    return get_or_create_profile(session, user.id, user.email)


@router.patch("/me", response_model=ProfileResponse)
def update_me(payload: ProfileUpdate, user: CurrentUser, session: Database) -> object:
    profile = get_or_create_profile(session, user.id, user.email)
    updates = payload.model_dump(exclude_unset=True)
    if (
        updates.get("timezone", "valid") is None
        or updates.get("notification_cadence", "valid") is None
    ):
        raise AppError(422, "validation_error", "Timezone and cadence cannot be null")
    for field, value in updates.items():
        setattr(profile, field, value)
    session.commit()
    session.refresh(profile)
    return profile


@router.post("/me/telegram-link", response_model=TelegramLinkResponse)
def create_telegram_link(user: CurrentUser, session: Database) -> TelegramLinkResponse:
    if not settings.telegram_bot_username:
        raise AppError(503, "not_configured", "Telegram bot is not configured")
    get_or_create_profile(session, user.id, user.email)
    link = telegram_link_service.create(session, user.id)
    session.commit()
    return TelegramLinkResponse(
        token=link.token,
        deep_link=f"https://t.me/{settings.telegram_bot_username}?start={link.token}",
        expires_at=link.expires_at,
    )


@router.delete("/me/telegram-link", status_code=204)
def disconnect_telegram(user: CurrentUser, session: Database) -> None:
    profile = get_or_create_profile(session, user.id, user.email)
    profile.telegram_chat_id = None
    profile.telegram_notifications_enabled = False
    session.commit()
