import logging
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from api.models import (
    DeliveryStatus,
    Job,
    JobMatch,
    JobStatus,
    MatchStatus,
    NotificationCadence,
    NotificationChannel,
    NotificationDelivery,
    NotificationPriority,
    Profile,
    ReminderEvent,
)
from api.notifications.domain import DeliveryOutcome, ProviderResult
from api.notifications.email_preferences import suppress_email
from api.notifications.message_builder import build_message
from api.notifications.planning import has_notification_consent
from api.notifications.providers import NotificationProvider

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        providers: dict[NotificationChannel, NotificationProvider],
        *,
        max_attempts: int = 5,
        lease_seconds: int = 300,
    ) -> None:
        self.session_factory = session_factory
        self.providers = providers
        self.max_attempts = max_attempts
        self.lease_seconds = lease_seconds

    async def dispatch_due(self, *, limit: int = 100, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        deliveries = self._claim_due(limit, now)
        groups = self._group(deliveries)
        sent = 0
        for group in groups:
            provider = self.providers.get(group[0].channel)
            if provider is None:
                result = ProviderResult(
                    DeliveryOutcome.PERMANENT_FAILURE, error="Notification provider is disabled"
                )
            elif not self._is_sendable(group):
                result = ProviderResult(
                    DeliveryOutcome.PERMANENT_FAILURE,
                    error="Match is no longer eligible for notification",
                )
            else:
                try:
                    result = await provider.send(build_message(group))
                except Exception as exc:
                    logger.exception(
                        "notification.provider.failed",
                        extra={
                            "event": "notification.provider.failed",
                            "channel": group[0].channel.value,
                            "exception_class": type(exc).__name__,
                        },
                    )
                    result = ProviderResult(
                        DeliveryOutcome.TRANSIENT_FAILURE,
                        error=f"ProviderError:{type(exc).__name__}",
                    )
            delivery_ids = [delivery.id for delivery in group]
            self._record_result(delivery_ids, result, now)
            logger.info(
                "notification.delivery.completed",
                extra={
                    "event": "notification.delivery.completed",
                    "delivery_ids": [str(item) for item in delivery_ids],
                    "channel": group[0].channel.value,
                    "outcome": result.outcome.value,
                    "count": len(group),
                },
            )
            if result.outcome == DeliveryOutcome.SENT:
                sent += len(group)
        return sent

    def _claim_due(self, limit: int, now: datetime) -> list[NotificationDelivery]:
        lease_expired = now - timedelta(seconds=self.lease_seconds)
        with self.session_factory() as session:
            due = or_(
                and_(
                    NotificationDelivery.status.in_(
                        [DeliveryStatus.PENDING, DeliveryStatus.FAILED]
                    ),
                    or_(
                        NotificationDelivery.next_attempt_at.is_(None),
                        NotificationDelivery.next_attempt_at <= now,
                    ),
                ),
                and_(
                    NotificationDelivery.status == DeliveryStatus.SENDING,
                    NotificationDelivery.locked_at < lease_expired,
                ),
            )
            statement = (
                select(NotificationDelivery)
                .options(
                    selectinload(NotificationDelivery.match)
                    .selectinload(JobMatch.job)
                    .selectinload(Job.sources),
                    selectinload(NotificationDelivery.match).selectinload(JobMatch.profile),
                    selectinload(NotificationDelivery.profile),
                )
                .where(
                    NotificationDelivery.attempt_count < self.max_attempts,
                    due,
                    ~and_(
                        NotificationDelivery.channel == NotificationChannel.EMAIL,
                        NotificationDelivery.notification_type == "new_match",
                    ),
                )
                .order_by(NotificationDelivery.next_attempt_at, NotificationDelivery.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            claimed = list(session.scalars(statement))
            for delivery in claimed:
                self._mark_claimed(delivery, now)
            if len(claimed) < limit:
                claimed.extend(
                    self._claim_email_digests(
                        session,
                        due,
                        now,
                        profile_limit=limit - len(claimed),
                    )
                )
            session.commit()
            for delivery in claimed:
                session.expunge(delivery)
            return claimed

    def _claim_email_digests(
        self,
        session: Session,
        due: ColumnElement[bool],
        now: datetime,
        *,
        profile_limit: int,
    ) -> list[NotificationDelivery]:
        """Freeze each due user's top-N rows so retries resend the same curated digest."""
        profile_ids = list(
            session.scalars(
                select(NotificationDelivery.profile_id)
                .where(
                    NotificationDelivery.channel == NotificationChannel.EMAIL,
                    NotificationDelivery.notification_type == "new_match",
                    NotificationDelivery.attempt_count < self.max_attempts,
                    due,
                )
                .distinct()
                .limit(profile_limit)
            )
        )
        claimed: list[NotificationDelivery] = []
        for profile_id in profile_ids:
            profile = session.scalar(
                select(Profile).where(Profile.id == profile_id).with_for_update()
            )
            if profile is None:
                continue
            candidates = list(
                session.scalars(
                    select(NotificationDelivery)
                    .options(
                        selectinload(NotificationDelivery.match)
                        .selectinload(JobMatch.job)
                        .selectinload(Job.sources),
                        selectinload(NotificationDelivery.match).selectinload(JobMatch.profile),
                        selectinload(NotificationDelivery.profile),
                    )
                    .where(
                        NotificationDelivery.profile_id == profile_id,
                        NotificationDelivery.channel == NotificationChannel.EMAIL,
                        NotificationDelivery.notification_type == "new_match",
                        NotificationDelivery.attempt_count < self.max_attempts,
                        due,
                    )
                    .with_for_update(skip_locked=True)
                )
            )
            ranked = sorted(candidates, key=self._digest_rank, reverse=True)
            selected = ranked[: profile.email_digest_job_limit]
            for delivery in selected:
                self._mark_claimed(delivery, now)
            for delivery in ranked[profile.email_digest_job_limit :]:
                delivery.status = DeliveryStatus.CANCELLED
                delivery.next_attempt_at = None
                delivery.queued_reason = "digest_not_selected"
                delivery.last_error = "Not selected for the curated daily digest"
            claimed.extend(selected)
        return claimed

    @staticmethod
    def _digest_rank(delivery: NotificationDelivery) -> tuple[int, int, float]:
        match = delivery.match
        if match is None:
            return (0, 0, 0.0)
        dimensions = {
            key for reason in match.reasons for key in (reason.get("dimensions") or {}).keys()
        }
        seen_at = match.job.posted_at or match.job.first_seen_at
        return (
            1 if delivery.priority == NotificationPriority.HIGH else 0,
            len(dimensions),
            seen_at.timestamp(),
        )

    @staticmethod
    def _mark_claimed(delivery: NotificationDelivery, now: datetime) -> None:
        delivery.status = DeliveryStatus.SENDING
        delivery.locked_at = now
        delivery.last_attempt_at = now
        delivery.attempt_count += 1

    @staticmethod
    def _group(deliveries: list[NotificationDelivery]) -> list[list[NotificationDelivery]]:
        grouped: defaultdict[
            tuple[NotificationChannel, str, NotificationCadence], list[NotificationDelivery]
        ] = defaultdict(list)
        result: list[list[NotificationDelivery]] = []
        for delivery in deliveries:
            if delivery.cadence == NotificationCadence.INSTANT or delivery.match is None:
                result.append([delivery])
            else:
                grouped[(delivery.channel, delivery.recipient, delivery.cadence)].append(delivery)
        result.extend(grouped.values())
        return result

    @staticmethod
    def _is_sendable(deliveries: list[NotificationDelivery]) -> bool:
        if not deliveries[0].recipient:
            return False
        return all(
            (has_notification_consent(delivery.profile, delivery.notification_type))
            and (
                (
                    delivery.channel == NotificationChannel.EMAIL
                    and delivery.profile.email_notifications_enabled
                    and delivery.profile.email_notifications_consent_at is not None
                    and delivery.profile.email_suppressed_at is None
                )
                or (
                    delivery.channel == NotificationChannel.TELEGRAM
                    and delivery.profile.telegram_notifications_enabled
                )
            )
            and (
                delivery.match is None
                or (
                    delivery.match.status == MatchStatus.MATCHED
                    and delivery.match.job.status == JobStatus.ACTIVE
                )
            )
            for delivery in deliveries
        )

    def _record_result(
        self, delivery_ids: Sequence[object], result: ProviderResult, attempted_at: datetime
    ) -> None:
        with self.session_factory() as session:
            deliveries = list(
                session.scalars(
                    select(NotificationDelivery).where(NotificationDelivery.id.in_(delivery_ids))
                )
            )
            permanently_failed_emails: set[str] = set()
            for delivery in deliveries:
                delivery.locked_at = None
                delivery.last_error = result.error[:2000] if result.error else None
                if result.outcome == DeliveryOutcome.SENT:
                    delivery.status = DeliveryStatus.SENT
                    delivery.sent_at = attempted_at
                    delivery.provider_message_id = result.provider_message_id
                    delivery.next_attempt_at = None
                    reminder_id = delivery.payload.get("reminder_id")
                    if reminder_id:
                        reminder = session.get(ReminderEvent, reminder_id)
                        if reminder is not None:
                            reminder.sent_at = attempted_at
                elif result.outcome == DeliveryOutcome.PERMANENT_FAILURE:
                    delivery.status = DeliveryStatus.CANCELLED
                    delivery.next_attempt_at = None
                    if (
                        delivery.channel == NotificationChannel.EMAIL
                        and result.error
                        and result.error.startswith("Resend rejected")
                    ):
                        permanently_failed_emails.add(delivery.recipient)
                elif delivery.attempt_count >= self.max_attempts:
                    delivery.status = DeliveryStatus.CANCELLED
                    delivery.next_attempt_at = None
                else:
                    delivery.status = DeliveryStatus.FAILED
                    delay = result.retry_after_seconds or min(
                        3600.0, float(2**delivery.attempt_count)
                    )
                    delivery.next_attempt_at = attempted_at + timedelta(seconds=delay)
            session.flush()
            for email in permanently_failed_emails:
                failure_count = session.scalar(
                    select(func.count(NotificationDelivery.id)).where(
                        NotificationDelivery.channel == NotificationChannel.EMAIL,
                        func.lower(NotificationDelivery.recipient) == email.casefold(),
                        NotificationDelivery.status == DeliveryStatus.CANCELLED,
                        NotificationDelivery.last_error.like("Resend rejected%"),
                    )
                )
                if (failure_count or 0) >= 3:
                    suppress_email(session, email, "repeated_failure")
            session.commit()
