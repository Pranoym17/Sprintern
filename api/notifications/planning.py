import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import (
    JobMatch,
    NotificationCadence,
    NotificationChannel,
    NotificationDelivery,
    Profile,
)


def next_delivery_time(cadence: NotificationCadence, timezone: str, now: datetime) -> datetime:
    if cadence == NotificationCadence.INSTANT:
        return now
    try:
        local = now.astimezone(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        local = now.astimezone(UTC)
    if cadence == NotificationCadence.HOURLY:
        scheduled = local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        scheduled = (local + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return scheduled.astimezone(UTC)


class NotificationPlanner:
    def plan_match(
        self,
        session: Session,
        match: JobMatch,
        profile: Profile,
        now: datetime | None = None,
    ) -> int:
        session.flush()
        now = now or datetime.now(UTC)
        destinations: list[tuple[NotificationChannel, str]] = []
        if profile.email_notifications_enabled and profile.email:
            destinations.append((NotificationChannel.EMAIL, profile.email))
        if profile.telegram_notifications_enabled and profile.telegram_chat_id:
            destinations.append((NotificationChannel.TELEGRAM, profile.telegram_chat_id))

        existing_channels = set(
            session.scalars(
                select(NotificationDelivery.channel).where(
                    NotificationDelivery.match_id == match.id
                )
            )
        )
        created = 0
        for channel, recipient in destinations:
            if channel in existing_channels:
                continue
            session.add(
                NotificationDelivery(
                    match_id=match.id,
                    channel=channel,
                    cadence=profile.notification_cadence,
                    recipient=recipient,
                    idempotency_key=f"{match.id}:{channel.value}",
                    next_attempt_at=next_delivery_time(
                        profile.notification_cadence, profile.timezone, now
                    ),
                )
            )
            created += 1
        return created

    def backfill_profile(self, session: Session, profile_id: uuid.UUID) -> int:
        profile = session.get(Profile, profile_id)
        if profile is None:
            return 0
        matches = list(session.scalars(select(JobMatch).where(JobMatch.profile_id == profile_id)))
        return sum(self.plan_match(session, match, profile) for match in matches)


notification_planner = NotificationPlanner()
