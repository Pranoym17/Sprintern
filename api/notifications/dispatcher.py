from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from api.models import (
    DeliveryStatus,
    Job,
    JobMatch,
    JobStatus,
    MatchStatus,
    NotificationCadence,
    NotificationChannel,
    NotificationDelivery,
)
from api.notifications.domain import DeliveryOutcome, ProviderResult
from api.notifications.message_builder import build_message
from api.notifications.providers import NotificationProvider


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
                result = await provider.send(build_message(group))
            self._record_result([delivery.id for delivery in group], result, now)
            if result.outcome == DeliveryOutcome.SENT:
                sent += len(group)
        return sent

    def _claim_due(self, limit: int, now: datetime) -> list[NotificationDelivery]:
        lease_expired = now - timedelta(seconds=self.lease_seconds)
        with self.session_factory() as session:
            statement = (
                select(NotificationDelivery)
                .options(
                    selectinload(NotificationDelivery.match)
                    .selectinload(JobMatch.job)
                    .selectinload(Job.sources)
                )
                .where(
                    NotificationDelivery.attempt_count < self.max_attempts,
                    or_(
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
                    ),
                )
                .order_by(NotificationDelivery.next_attempt_at, NotificationDelivery.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            claimed = list(session.scalars(statement))
            for delivery in claimed:
                delivery.status = DeliveryStatus.SENDING
                delivery.locked_at = now
                delivery.last_attempt_at = now
                delivery.attempt_count += 1
            session.commit()
            for delivery in claimed:
                session.expunge(delivery)
            return claimed

    @staticmethod
    def _group(deliveries: list[NotificationDelivery]) -> list[list[NotificationDelivery]]:
        grouped: defaultdict[
            tuple[NotificationChannel, str, NotificationCadence], list[NotificationDelivery]
        ] = defaultdict(list)
        result: list[list[NotificationDelivery]] = []
        for delivery in deliveries:
            if delivery.cadence == NotificationCadence.INSTANT:
                result.append([delivery])
            else:
                grouped[(delivery.channel, delivery.recipient, delivery.cadence)].append(delivery)
        result.extend(grouped.values())
        return result

    @staticmethod
    def _is_sendable(deliveries: list[NotificationDelivery]) -> bool:
        return bool(deliveries[0].recipient) and all(
            delivery.match.status == MatchStatus.MATCHED
            and delivery.match.job.status == JobStatus.ACTIVE
            for delivery in deliveries
        )

    def _record_result(
        self, delivery_ids: list[object], result: ProviderResult, attempted_at: datetime
    ) -> None:
        with self.session_factory() as session:
            deliveries = list(
                session.scalars(
                    select(NotificationDelivery).where(NotificationDelivery.id.in_(delivery_ids))
                )
            )
            for delivery in deliveries:
                delivery.locked_at = None
                delivery.last_error = result.error[:2000] if result.error else None
                if result.outcome == DeliveryOutcome.SENT:
                    delivery.status = DeliveryStatus.SENT
                    delivery.sent_at = attempted_at
                    delivery.provider_message_id = result.provider_message_id
                    delivery.next_attempt_at = None
                elif result.outcome == DeliveryOutcome.PERMANENT_FAILURE:
                    delivery.status = DeliveryStatus.CANCELLED
                    delivery.next_attempt_at = None
                elif delivery.attempt_count >= self.max_attempts:
                    delivery.status = DeliveryStatus.CANCELLED
                    delivery.next_attempt_at = None
                else:
                    delivery.status = DeliveryStatus.FAILED
                    delay = result.retry_after_seconds or min(
                        3600.0, float(2**delivery.attempt_count)
                    )
                    delivery.next_attempt_at = attempted_at + timedelta(seconds=delay)
            session.commit()
