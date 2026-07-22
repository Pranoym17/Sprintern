import base64
import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.errors import AppError
from api.models import (
    DeliveryStatus,
    EmailSuppression,
    JobMatch,
    NotificationChannel,
    NotificationDelivery,
    Profile,
)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def email_fingerprint(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode()).hexdigest()[:24]


class UnsubscribeTokenService:
    def __init__(self, secret: str, public_api_url: str, *, lifetime_days: int = 90) -> None:
        self.secret = secret.encode()
        self.public_api_url = public_api_url.rstrip("/")
        self.lifetime = timedelta(days=lifetime_days)

    def create(self, profile_id: uuid.UUID, email: str, now: datetime | None = None) -> str:
        now = now or datetime.now(UTC)
        expires_at = int((now + self.lifetime).timestamp())
        payload = f"{profile_id}.{expires_at}.{email_fingerprint(email)}"
        signature = hmac.new(self.secret, payload.encode(), hashlib.sha256).digest()
        encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return f"{payload}.{encoded_signature}"

    def url(self, profile_id: uuid.UUID, email: str) -> str:
        token = quote(self.create(profile_id, email))
        return f"{self.public_api_url}/email/unsubscribe?token={token}"

    def verify(self, token: str, now: datetime | None = None) -> tuple[uuid.UUID, str]:
        now = now or datetime.now(UTC)
        try:
            profile_value, expiry_value, fingerprint, supplied_signature = token.split(".", 3)
            profile_id = uuid.UUID(profile_value)
            expires_at = int(expiry_value)
        except (ValueError, TypeError) as exc:
            raise AppError(400, "invalid_unsubscribe_token", "Unsubscribe link is invalid") from exc
        payload = f"{profile_value}.{expiry_value}.{fingerprint}"
        expected = (
            base64.urlsafe_b64encode(
                hmac.new(self.secret, payload.encode(), hashlib.sha256).digest()
            )
            .decode()
            .rstrip("=")
        )
        if not hmac.compare_digest(supplied_signature, expected):
            raise AppError(400, "invalid_unsubscribe_token", "Unsubscribe link is invalid")
        if expires_at < int(now.timestamp()):
            raise AppError(410, "expired_unsubscribe_token", "Unsubscribe link has expired")
        return profile_id, fingerprint


def is_email_suppressed(session: Session, email: str) -> bool:
    return session.get(EmailSuppression, normalize_email(email)) is not None


def cancel_email_deliveries(session: Session, *, profile_id: uuid.UUID, reason: str) -> None:
    session.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.match_id.in_(
                select(JobMatch.id).where(JobMatch.profile_id == profile_id)
            ),
            NotificationDelivery.channel == NotificationChannel.EMAIL,
            NotificationDelivery.status.in_(
                [DeliveryStatus.PENDING, DeliveryStatus.FAILED, DeliveryStatus.SENDING]
            ),
        )
        .values(
            status=DeliveryStatus.CANCELLED,
            next_attempt_at=None,
            locked_at=None,
            last_error=reason,
        )
    )


def unsubscribe_profile(
    session: Session, profile_id: uuid.UUID, fingerprint: str | None = None
) -> bool:
    profile = session.get(Profile, profile_id)
    if profile is None or profile.email is None:
        return False
    if fingerprint is not None and not hmac.compare_digest(
        fingerprint, email_fingerprint(profile.email)
    ):
        raise AppError(409, "email_changed", "This link no longer matches the account email")
    profile.email_notifications_enabled = False
    profile.email_notifications_consent_at = None
    cancel_email_deliveries(session, profile_id=profile_id, reason="Email notifications disabled")
    return True


def suppress_email(session: Session, email: str, reason: str) -> None:
    normalized = normalize_email(email)
    session.execute(
        insert(EmailSuppression)
        .values(email=normalized, reason=reason, provider="resend")
        .on_conflict_do_update(
            index_elements=[EmailSuppression.email],
            set_={"reason": reason, "provider": "resend", "created_at": func.now()},
        )
    )
    profiles = list(session.scalars(select(Profile).where(func.lower(Profile.email) == normalized)))
    for profile in profiles:
        profile.email_notifications_enabled = False
        profile.email_notifications_consent_at = None
        profile.email_suppressed_at = datetime.now(UTC)
        profile.email_suppression_reason = reason
        cancel_email_deliveries(
            session, profile_id=profile.id, reason=f"Email suppressed after Resend {reason}"
        )
