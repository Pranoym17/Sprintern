from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.auth import CurrentUser
from api.auth.admin import SupabaseAuthAdmin
from api.database import get_db
from api.errors import AppError
from api.models import JobFilter, JobMatch, Profile
from api.notifications.email_preferences import cancel_email_deliveries, is_email_suppressed
from api.notifications.planning import notification_planner
from api.notifications.telegram_linking import telegram_link_service
from api.rate_limiting import user_rate_limit
from api.repositories.profiles import get_or_create_profile
from api.schemas import ProfileResponse, ProfileUpdate
from api.schemas.profile import (
    AccountDeletionRequest,
    AccountDeletionResponse,
    TelegramLinkResponse,
)
from api.settings import settings

router = APIRouter(prefix="/users", tags=["users"])
Database = Annotated[Session, Depends(get_db)]
auth_admin = SupabaseAuthAdmin(settings.supabase_url, settings.supabase_service_role_key)


@router.get("/me", response_model=ProfileResponse)
def read_me(user: CurrentUser, session: Database) -> object:
    return get_or_create_profile(session, user.id, user.email)


@router.patch(
    "/me",
    response_model=ProfileResponse,
    dependencies=[Depends(user_rate_limit("profiles.update", 30))],
)
def update_me(payload: ProfileUpdate, user: CurrentUser, session: Database) -> object:
    profile = get_or_create_profile(session, user.id, user.email)
    updates = payload.model_dump(exclude_unset=True)
    if (
        updates.get("timezone", "valid") is None
        or updates.get("notification_cadence", "valid") is None
    ):
        raise AppError(422, "validation_error", "Timezone and cadence cannot be null")
    email_preference = updates.get("email_notifications_enabled")
    if email_preference is True:
        if not profile.email:
            raise AppError(409, "email_unavailable", "No email address is connected")
        if is_email_suppressed(session, profile.email):
            raise AppError(
                409,
                "email_suppressed",
                "Email alerts cannot be enabled for this address",
            )
        profile.email_notifications_consent_at = datetime.now(UTC)
        profile.email_suppressed_at = None
        profile.email_suppression_reason = None
    elif email_preference is False:
        profile.email_notifications_consent_at = None
        cancel_email_deliveries(
            session, profile_id=profile.id, reason="Email notifications disabled"
        )
    for field, value in updates.items():
        setattr(profile, field, value)
    if email_preference is True:
        notification_planner.backfill_profile(session, profile.id)
    session.commit()
    session.refresh(profile)
    return profile


@router.post(
    "/me/telegram-link",
    response_model=TelegramLinkResponse,
    dependencies=[Depends(user_rate_limit("telegram.link", 10, 300))],
)
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


@router.delete(
    "/me/telegram-link",
    status_code=204,
    dependencies=[Depends(user_rate_limit("telegram.unlink", 10, 300))],
)
def disconnect_telegram(user: CurrentUser, session: Database) -> None:
    profile = get_or_create_profile(session, user.id, user.email)
    profile.telegram_chat_id = None
    profile.telegram_notifications_enabled = False
    session.commit()


@router.get(
    "/me/export",
    dependencies=[Depends(user_rate_limit("account.export", 5, 300))],
)
def export_me(user: CurrentUser, session: Database) -> dict[str, Any]:
    profile = get_or_create_profile(session, user.id, user.email)
    filters = list(session.scalars(select(JobFilter).where(JobFilter.profile_id == profile.id)))
    matches = list(
        session.scalars(
            select(JobMatch)
            .options(selectinload(JobMatch.job), selectinload(JobMatch.deliveries))
            .where(JobMatch.profile_id == profile.id)
        )
    )
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": {
            "id": str(profile.id),
            "email": profile.email,
            "timezone": profile.timezone,
            "notification_cadence": profile.notification_cadence.value,
            "email_notifications_enabled": profile.email_notifications_enabled,
            "email_notifications_consent_at": profile.email_notifications_consent_at,
            "telegram_connected": profile.telegram_chat_id is not None,
            "telegram_notifications_enabled": profile.telegram_notifications_enabled,
            "created_at": profile.created_at,
        },
        "filters": [
            {
                "id": str(item.id),
                "name": item.name,
                "role_keywords": item.role_keywords,
                "location_keywords": item.location_keywords,
                "terms": item.terms,
                "work_mode": item.work_mode.value,
                "active": item.active,
            }
            for item in filters
        ],
        "matches": [
            {
                "id": str(item.id),
                "status": item.status.value,
                "applied_at": item.applied_at,
                "reasons": item.reasons,
                "job": {
                    "id": str(item.job.id),
                    "company": item.job.company,
                    "title": item.job.title,
                    "location": item.job.location,
                    "term": item.job.term,
                },
                "deliveries": [
                    {
                        "channel": delivery.channel.value,
                        "status": delivery.status.value,
                        "sent_at": delivery.sent_at,
                    }
                    for delivery in item.deliveries
                ],
            }
            for item in matches
        ],
    }


@router.delete(
    "/me",
    response_model=AccountDeletionResponse,
    dependencies=[Depends(user_rate_limit("account.delete", 3, 3600))],
)
async def delete_me(
    payload: AccountDeletionRequest, user: CurrentUser, session: Database
) -> AccountDeletionResponse:
    if payload.confirmation != "DELETE":
        raise AppError(422, "confirmation_required", "Type DELETE to confirm account deletion")
    profile = session.get(Profile, user.id)
    # Supabase Auth owns the login identity; this server-only admin call removes it before
    # application data so a partial failure cannot leave a user able to recreate data.
    await auth_admin.delete_user(user.id)
    if profile is not None:
        session.delete(profile)
        session.commit()
    return AccountDeletionResponse(application_data_deleted=True, auth_identity_deleted=True)
