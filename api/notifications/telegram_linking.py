import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import Profile, TelegramLinkToken


@dataclass(frozen=True)
class TelegramLink:
    token: str
    expires_at: datetime


class TelegramLinkService:
    def create(
        self, session: Session, profile_id: uuid.UUID, *, ttl_minutes: int = 15
    ) -> TelegramLink:
        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
        session.add(
            TelegramLinkToken(
                profile_id=profile_id,
                token_hash=self._hash(raw_token),
                expires_at=expires_at,
            )
        )
        return TelegramLink(token=raw_token, expires_at=expires_at)

    def consume(
        self, session: Session, raw_token: str, telegram_chat_id: str, now: datetime | None = None
    ) -> Profile | None:
        now = now or datetime.now(UTC)
        link = session.scalar(
            select(TelegramLinkToken)
            .where(
                TelegramLinkToken.token_hash == self._hash(raw_token),
                TelegramLinkToken.used_at.is_(None),
                TelegramLinkToken.expires_at > now,
            )
            .with_for_update()
        )
        if link is None:
            return None
        profile = session.get(Profile, link.profile_id)
        if profile is None:
            return None
        profile.telegram_chat_id = telegram_chat_id
        profile.telegram_notifications_enabled = True
        link.used_at = now
        return profile

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


telegram_link_service = TelegramLinkService()
