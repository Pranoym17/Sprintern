import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.models import (
    Application,
    DeliveryStatus,
    FilterNotificationOverride,
    JobChangeEvent,
    JobMatch,
    NotificationCadence,
    NotificationChannel,
    NotificationDelivery,
    NotificationPriority,
    ParserAlert,
    Profile,
    ReminderEvent,
    SourceState,
    WeeklyGoal,
)
from api.notifications.email_preferences import is_email_suppressed
from api.settings import settings

CADENCE_RANK = {
    NotificationCadence.INSTANT: 0,
    NotificationCadence.HOURLY: 1,
    NotificationCadence.DAILY: 2,
    NotificationCadence.WEEKLY: 3,
}


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def next_delivery_time(cadence: NotificationCadence, timezone: str, now: datetime) -> datetime:
    if cadence == NotificationCadence.INSTANT:
        return now
    local = now.astimezone(_zone(timezone))
    if cadence == NotificationCadence.HOURLY:
        scheduled = local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif cadence == NotificationCadence.DAILY:
        scheduled = (local + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        days = 7 - local.weekday()
        scheduled = (local + timedelta(days=days)).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
    return scheduled.astimezone(UTC)


def apply_delivery_window(profile: Profile, scheduled: datetime) -> tuple[datetime, str | None]:
    """Move delivery to the next valid local wall-clock time; ZoneInfo handles DST transitions."""
    zone = _zone(profile.timezone)
    local = scheduled.astimezone(zone)
    reason: str | None = None
    if profile.weekend_pause and local.weekday() >= 5:
        local = (local + timedelta(days=7 - local.weekday())).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        reason = "weekend_pause"
    start, end = profile.quiet_hours_start, profile.quiet_hours_end
    if start is not None and end is not None:
        clock = local.timetz().replace(tzinfo=None)
        in_quiet = start <= clock < end if start < end else clock >= start or clock < end
        if in_quiet:
            end_date = local.date()
            if start >= end and clock >= start:
                end_date += timedelta(days=1)
            local = datetime.combine(end_date, end, tzinfo=zone)
            reason = "quiet_hours"
            if profile.weekend_pause and local.weekday() >= 5:
                local = (local + timedelta(days=7 - local.weekday())).replace(
                    hour=8, minute=0, second=0, microsecond=0
                )
                reason = "weekend_pause"
    return local.astimezone(UTC), reason


class NotificationPlanner:
    @staticmethod
    def _filter_overrides(session: Session, match: JobMatch) -> list[FilterNotificationOverride]:
        filter_ids: list[uuid.UUID] = []
        for reason in match.reasons:
            try:
                if reason.get("filter_id"):
                    filter_ids.append(uuid.UUID(str(reason["filter_id"])))
            except (ValueError, TypeError):
                continue
        if not filter_ids:
            return []
        return list(
            session.scalars(
                select(FilterNotificationOverride).where(
                    FilterNotificationOverride.filter_id.in_(filter_ids)
                )
            )
        )

    @staticmethod
    def _channel_enabled(
        profile: Profile,
        overrides: list[FilterNotificationOverride],
        channel: NotificationChannel,
    ) -> bool:
        field = "email_enabled" if channel == NotificationChannel.EMAIL else "telegram_enabled"
        choices = [getattr(item, field) for item in overrides if getattr(item, field) is not None]
        if choices:
            return any(choices)
        return bool(
            profile.email_notifications_enabled
            if channel == NotificationChannel.EMAIL
            else profile.telegram_notifications_enabled
        )

    @staticmethod
    def _delivery_policy(
        profile: Profile, overrides: list[FilterNotificationOverride]
    ) -> tuple[NotificationCadence, NotificationPriority]:
        cadences = [item.cadence for item in overrides if item.cadence is not None]
        cadence = (
            min(cadences, key=lambda item: CADENCE_RANK[item])
            if cadences
            else profile.notification_cadence
        )
        priority = (
            NotificationPriority.HIGH
            if any(item.priority == NotificationPriority.HIGH for item in overrides)
            else NotificationPriority.NORMAL
        )
        if profile.priority_only_instant and priority != NotificationPriority.HIGH:
            cadence = NotificationCadence.DAILY
        return cadence, priority

    @staticmethod
    def _daily_cap_time(
        session: Session, profile: Profile, now: datetime, scheduled: datetime
    ) -> tuple[datetime, str | None]:
        local = now.astimezone(_zone(profile.timezone))
        local_start = datetime.combine(local.date(), time.min, tzinfo=local.tzinfo).astimezone(UTC)
        count = (
            session.scalar(
                select(func.count(NotificationDelivery.id)).where(
                    NotificationDelivery.profile_id == profile.id,
                    NotificationDelivery.created_at >= local_start,
                    NotificationDelivery.status != DeliveryStatus.CANCELLED,
                )
            )
            or 0
        )
        if count < profile.max_alerts_per_day:
            return scheduled, None
        tomorrow = (local + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
        return max(scheduled, tomorrow.astimezone(UTC)), "daily_cap"

    def _destinations(
        self,
        session: Session,
        profile: Profile,
        overrides: list[FilterNotificationOverride] | None = None,
        notification_type: str = "new_match",
    ) -> list[tuple[NotificationChannel, str]]:
        overrides = overrides or []
        if profile.notification_consents.get(notification_type, True) is False:
            return []
        values: list[tuple[NotificationChannel, str]] = []
        if (
            self._channel_enabled(profile, overrides, NotificationChannel.EMAIL)
            and profile.email
            and profile.email_notifications_consent_at is not None
            and not is_email_suppressed(session, profile.email)
        ):
            values.append((NotificationChannel.EMAIL, profile.email))
        if (
            self._channel_enabled(profile, overrides, NotificationChannel.TELEGRAM)
            and profile.telegram_chat_id
        ):
            values.append((NotificationChannel.TELEGRAM, profile.telegram_chat_id))
        return values

    def plan_match(
        self,
        session: Session,
        match: JobMatch,
        profile: Profile,
        now: datetime | None = None,
    ) -> int:
        session.flush()
        now = now or datetime.now(UTC)
        overrides = self._filter_overrides(session, match)
        cadence, priority = self._delivery_policy(profile, overrides)
        existing = {
            item.channel: item
            for item in session.scalars(
                select(NotificationDelivery).where(NotificationDelivery.match_id == match.id)
            )
        }
        created = 0
        destinations = self._destinations(
            session, profile, overrides, notification_type="new_match"
        )
        destination_channels = {channel for channel, _ in destinations}
        for channel, delivery in existing.items():
            if channel not in destination_channels and delivery.status in {
                DeliveryStatus.PENDING,
                DeliveryStatus.FAILED,
            }:
                delivery.status = DeliveryStatus.CANCELLED
                delivery.next_attempt_at = None
                delivery.last_error = "Notification channel disabled"
        for channel, recipient in destinations:
            existing_delivery = existing.get(channel)
            scheduled = next_delivery_time(cadence, profile.timezone, now)
            scheduled, queued_reason = apply_delivery_window(profile, scheduled)
            scheduled, cap_reason = self._daily_cap_time(session, profile, now, scheduled)
            queued_reason = cap_reason or queued_reason
            if existing_delivery:
                if existing_delivery.status in {DeliveryStatus.PENDING, DeliveryStatus.FAILED}:
                    existing_delivery.cadence = cadence
                    existing_delivery.priority = priority
                    existing_delivery.recipient = recipient
                    existing_delivery.next_attempt_at = scheduled
                    existing_delivery.queued_reason = queued_reason
                continue
            session.add(
                NotificationDelivery(
                    profile_id=profile.id,
                    match_id=match.id,
                    channel=channel,
                    cadence=cadence,
                    priority=priority,
                    recipient=recipient,
                    idempotency_key=f"{match.id}:{channel.value}",
                    next_attempt_at=scheduled,
                    queued_reason=queued_reason,
                )
            )
            created += 1
        return created

    def plan_events(self, session: Session, now: datetime | None = None) -> int:
        """Materialize due reminders and posting changes into the same idempotent delivery queue."""
        now = now or datetime.now(UTC)
        created = 0
        reminders = list(
            session.scalars(
                select(ReminderEvent).where(
                    ReminderEvent.due_at <= now, ReminderEvent.sent_at.is_(None)
                )
            )
        )
        for reminder in reminders:
            profile = session.get(Profile, reminder.profile_id)
            application = session.get(Application, reminder.application_id)
            if not profile or not application:
                continue
            for channel, recipient in self._destinations(
                session, profile, notification_type=reminder.kind.value
            ):
                key = f"reminder:{reminder.id}:{channel.value}"
                if session.scalar(
                    select(NotificationDelivery.id).where(
                        NotificationDelivery.idempotency_key == key
                    )
                ):
                    continue
                scheduled, reason = apply_delivery_window(profile, now)
                session.add(
                    NotificationDelivery(
                        profile_id=profile.id,
                        channel=channel,
                        cadence=NotificationCadence.INSTANT,
                        recipient=recipient,
                        idempotency_key=key,
                        notification_type=reminder.kind.value,
                        payload={
                            "title": f"{reminder.kind.value.replace('_', ' ').title()} reminder",
                            "body": f"{application.job.title} at {application.job.company}",
                            "apply_url": application.application_url or "",
                            "reminder_id": str(reminder.id),
                        },
                        next_attempt_at=scheduled,
                        queued_reason=reason,
                    )
                )
                created += 1
        changes = list(
            session.scalars(
                select(JobChangeEvent).where(
                    JobChangeEvent.event_type.in_(["updated", "reopened"]),
                    JobChangeEvent.created_at >= now - timedelta(days=2),
                )
            )
        )
        for change in changes:
            matches = list(
                session.scalars(select(JobMatch).where(JobMatch.job_id == change.job_id))
            )
            for match in matches:
                profile = session.get(Profile, match.profile_id)
                if not profile:
                    continue
                kind = f"posting_{change.event_type}"
                for channel, recipient in self._destinations(
                    session, profile, notification_type=kind
                ):
                    key = f"job-change:{change.id}:{profile.id}:{channel.value}"
                    if session.scalar(
                        select(NotificationDelivery.id).where(
                            NotificationDelivery.idempotency_key == key
                        )
                    ):
                        continue
                    session.add(
                        NotificationDelivery(
                            profile_id=profile.id,
                            match_id=None,
                            channel=channel,
                            cadence=profile.notification_cadence,
                            recipient=recipient,
                            idempotency_key=key,
                            notification_type=kind,
                            payload={
                                "title": f"Posting {change.event_type}",
                                "body": f"{change.job.title} at {change.job.company}",
                                "apply_url": "",
                            },
                            next_attempt_at=next_delivery_time(
                                profile.notification_cadence, profile.timezone, now
                            ),
                        )
                    )
                    created += 1
        created += self._plan_system_events(session, now)
        return created

    def _plan_system_events(self, session: Session, now: datetime) -> int:
        created = 0
        profiles = list(session.scalars(select(Profile)))
        stale_before = now - timedelta(hours=settings.source_stale_after_hours)
        stale_sources = list(
            session.scalars(
                select(SourceState).where(
                    (SourceState.last_succeeded_at < stale_before)
                    | (SourceState.consecutive_failures >= 2)
                )
            )
        )
        parser_alerts = list(
            session.scalars(select(ParserAlert).where(ParserAlert.resolved_at.is_(None)))
        )
        week_key = now.astimezone(UTC).strftime("%G-W%V")
        for profile in profiles:
            generic_events: list[tuple[str, str, str, str]] = []
            generic_events.extend(
                (
                    "source_stale",
                    f"source-stale:{source.id}:{source.last_succeeded_at or source.updated_at}",
                    "A job source needs attention",
                    f"{source.source_key} has not updated recently.",
                )
                for source in stale_sources
            )
            generic_events.extend(
                (
                    "parser_broken",
                    f"parser-broken:{alert.id}:{alert.occurrences}",
                    "A source parser needs attention",
                    f"Sprintern could not read {alert.source_key} reliably.",
                )
                for alert in parser_alerts
            )
            goal = session.scalar(select(WeeklyGoal).where(WeeklyGoal.profile_id == profile.id))
            local = now.astimezone(_zone(profile.timezone))
            if goal and goal.reminders_enabled and local.weekday() == 0 and local.hour >= 8:
                applied = (
                    session.scalar(
                        select(func.count(Application.id)).where(
                            Application.profile_id == profile.id,
                            Application.applied_at >= now - timedelta(days=7),
                        )
                    )
                    or 0
                )
                generic_events.append(
                    (
                        "weekly_progress",
                        f"weekly-progress:{profile.id}:{week_key}",
                        "Your weekly Sprintern progress",
                        f"You submitted {applied} of {goal.target} planned applications.",
                    )
                )
            for kind, event_key, title, body in generic_events:
                for channel, recipient in self._destinations(
                    session, profile, notification_type=kind
                ):
                    key = f"{event_key}:{profile.id}:{channel.value}"
                    if session.scalar(
                        select(NotificationDelivery.id).where(
                            NotificationDelivery.idempotency_key == key
                        )
                    ):
                        continue
                    scheduled, reason = apply_delivery_window(profile, now)
                    session.add(
                        NotificationDelivery(
                            profile_id=profile.id,
                            channel=channel,
                            cadence=NotificationCadence.INSTANT,
                            recipient=recipient,
                            idempotency_key=key,
                            notification_type=kind,
                            payload={"title": title, "body": body, "apply_url": ""},
                            next_attempt_at=scheduled,
                            queued_reason=reason,
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
