import uuid
from datetime import UTC, datetime, time, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import AuthenticatedUser
from api.models import (
    Application,
    ApplicationStage,
    FilterNotificationOverride,
    Job,
    JobFilter,
    JobMatch,
    JobSource,
    JobSourceName,
    NotificationCadence,
    NotificationChannel,
    NotificationDelivery,
    NotificationPriority,
    Profile,
    ReminderEvent,
    ReminderType,
)
from api.notifications.message_builder import build_message
from api.notifications.planning import (
    NotificationPlanner,
    apply_delivery_window,
    next_email_digest_time,
)
from api.settings import settings


def notification_match(db_session: Session, profile: Profile, job_filter: JobFilter) -> JobMatch:
    now = datetime.now(UTC)
    job = Job(
        company="Notification Controls",
        normalized_company="notification controls",
        title="Software Intern",
        normalized_title="software intern",
        location="Toronto, Canada",
        normalized_location="toronto canada",
        canonical_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
        first_seen_at=now,
        last_seen_at=now,
    )
    job.sources.append(
        JobSource(
            source=JobSourceName.GITHUB_REPO,
            source_key="notifications/test:README.md",
            external_id=uuid.uuid4().hex,
            apply_url="https://employer.example/apply",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    match = JobMatch(
        profile=profile,
        job=job,
        reasons=[{"filter_id": str(job_filter.id), "filter_name": job_filter.name}],
    )
    db_session.add(match)
    db_session.flush()
    return match


def test_filter_override_keeps_priority_while_email_remains_daily(db_session: Session) -> None:
    profile = Profile(
        id=uuid.uuid4(),
        email="alerts@example.com",
        timezone="America/Toronto",
        notification_cadence=NotificationCadence.DAILY,
        email_notifications_enabled=True,
        email_notifications_consent_at=datetime.now(UTC),
        telegram_notifications_enabled=False,
        quiet_hours_start=time(22),
        quiet_hours_end=time(7),
        max_alerts_per_day=25,
    )
    job_filter = JobFilter(profile=profile, name="Priority", role_keywords=["software"])
    db_session.add(job_filter)
    db_session.flush()
    db_session.add(
        FilterNotificationOverride(
            filter_id=job_filter.id,
            profile_id=profile.id,
            email_enabled=True,
            cadence=NotificationCadence.INSTANT,
            priority=NotificationPriority.HIGH,
        )
    )
    match = notification_match(db_session, profile, job_filter)
    now = datetime(2026, 7, 23, 3, 30, tzinfo=UTC)  # 11:30 PM in Toronto.

    assert NotificationPlanner().plan_match(db_session, match, profile, now) == 1
    db_session.flush()
    delivery = db_session.scalar(
        select(NotificationDelivery).where(NotificationDelivery.match_id == match.id)
    )
    assert delivery is not None
    assert delivery.priority == NotificationPriority.HIGH
    assert delivery.cadence == NotificationCadence.DAILY
    assert delivery.queued_reason is None
    assert delivery.next_attempt_at == datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def test_delivery_window_moves_weekend_to_monday() -> None:
    profile = Profile(
        id=uuid.uuid4(),
        timezone="America/Toronto",
        weekend_pause=True,
        max_alerts_per_day=25,
    )
    saturday = datetime(2026, 7, 25, 14, tzinfo=UTC)
    scheduled, reason = apply_delivery_window(profile, saturday)
    assert scheduled == datetime(2026, 7, 27, 14, tzinfo=UTC)
    assert reason == "weekend_pause"


def test_email_digest_time_handles_dst_gap() -> None:
    profile = Profile(
        id=uuid.uuid4(),
        timezone="America/Toronto",
        preferred_email_time=time(2, 30),
    )

    scheduled = next_email_digest_time(profile, datetime(2026, 3, 8, 5, 0, tzinfo=UTC))

    assert scheduled == datetime(2026, 3, 8, 7, 30, tzinfo=UTC)


def test_telegram_new_match_bypasses_quiet_hours(db_session: Session) -> None:
    profile = Profile(
        id=uuid.uuid4(),
        email="alerts@example.com",
        timezone="America/Toronto",
        telegram_chat_id="instant-chat",
        telegram_notifications_enabled=True,
        quiet_hours_start=time(22),
        quiet_hours_end=time(7),
        weekend_pause=True,
    )
    job_filter = JobFilter(profile=profile, name="Instant Telegram")
    match = notification_match(db_session, profile, job_filter)
    now = datetime(2026, 7, 25, 3, 30, tzinfo=UTC)

    NotificationPlanner().plan_match(db_session, match, profile, now)
    db_session.flush()
    delivery = db_session.scalar(
        select(NotificationDelivery).where(
            NotificationDelivery.match_id == match.id,
            NotificationDelivery.channel == NotificationChannel.TELEGRAM,
        )
    )

    assert delivery is not None
    assert delivery.cadence == NotificationCadence.INSTANT
    assert delivery.next_attempt_at == now
    assert delivery.queued_reason is None
    message = build_message([delivery])
    assert message.telegram_parse_mode == "HTML"
    assert message.text == (
        "🎯 <b>New match:</b> Software Intern\n"
        "🏢 <b>Notification Controls</b>\n"
        "📍 Toronto, Canada · Term not specified\n\n"
        '<a href="https://employer.example/apply">Apply now</a>'
    )


def test_match_uses_new_match_consent_and_deterministic_priority(
    db_session: Session,
) -> None:
    profile = Profile(
        id=uuid.uuid4(),
        email="digest@example.com",
        email_notifications_enabled=True,
        email_notifications_consent_at=datetime.now(UTC),
        notification_cadence=NotificationCadence.WEEKLY,
        notification_consents={"new_match": True},
        max_alerts_per_day=25,
    )
    job_filter = JobFilter(profile=profile, name="Strong match")
    match = notification_match(db_session, profile, job_filter)
    match.reasons = [
        {
            "filter_id": str(job_filter.id),
            "dimensions": {"role": "software", "location": "Toronto", "term": "Summer 2027"},
        }
    ]
    NotificationPlanner().plan_match(db_session, match, profile, datetime.now(UTC))
    db_session.flush()
    delivery = db_session.scalar(
        select(NotificationDelivery).where(NotificationDelivery.match_id == match.id)
    )
    assert delivery is not None
    assert delivery.notification_type == "new_match"
    assert delivery.cadence == NotificationCadence.DAILY
    assert delivery.priority == NotificationPriority.HIGH


def test_empty_digest_is_opt_in_and_idempotent(db_session: Session) -> None:
    now = datetime(2026, 7, 24, 13, 0, tzinfo=UTC)
    profile = Profile(
        id=uuid.uuid4(),
        email="empty@example.com",
        timezone="UTC",
        preferred_email_time=time(8),
        email_notifications_enabled=True,
        email_notifications_consent_at=now,
        email_empty_digest_enabled=True,
    )
    db_session.add(profile)
    db_session.flush()
    planner = NotificationPlanner()

    first = planner.plan_events(db_session, now)
    db_session.flush()
    second = planner.plan_events(db_session, now)
    empty = list(
        db_session.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.profile_id == profile.id,
                NotificationDelivery.notification_type == "daily_empty_digest",
            )
        )
    )

    assert first == 1
    assert second == 0
    assert len(empty) == 1


async def test_filter_notification_preferences_are_owned(
    api_client: httpx.AsyncClient,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    profile = Profile(id=authenticated_user.id, email=authenticated_user.email)
    job_filter = JobFilter(profile=profile, name="Owned", role_keywords=["software"])
    db_session.add(job_filter)
    db_session.commit()
    response = await api_client.put(
        f"/filters/{job_filter.id}/notifications",
        json={
            "email_enabled": True,
            "telegram_enabled": False,
            "priority": "high",
        },
    )
    assert response.status_code == 200
    assert response.json()["priority"] == "high"
    missing = await api_client.get(f"/filters/{uuid.uuid4()}/notifications")
    assert missing.status_code == 404


def test_due_reminder_is_planned_once_with_separate_consent(db_session: Session) -> None:
    now = datetime.now(UTC)
    profile = Profile(
        id=uuid.uuid4(),
        email="reminder@example.com",
        email_notifications_enabled=True,
        email_notifications_consent_at=now,
        notification_consents={"follow_up": True},
        max_alerts_per_day=25,
    )
    job_filter = JobFilter(profile=profile, name="Reminder filter")
    match = notification_match(db_session, profile, job_filter)
    application = Application(
        profile_id=profile.id, job_id=match.job_id, stage=ApplicationStage.APPLIED
    )
    db_session.add(application)
    db_session.flush()
    reminder = ReminderEvent(
        profile_id=profile.id,
        application_id=application.id,
        kind=ReminderType.FOLLOW_UP,
        due_at=now - timedelta(minutes=1),
        idempotency_key=f"test:{uuid.uuid4()}",
    )
    db_session.add(reminder)
    db_session.flush()
    planner = NotificationPlanner()
    first = planner.plan_events(db_session, now)
    db_session.flush()
    second = planner.plan_events(db_session, now)
    deliveries = list(
        db_session.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.idempotency_key.like(f"reminder:{reminder.id}:%")
            )
        )
    )
    assert first >= 1
    assert second >= 0
    assert len(deliveries) == 1
    assert build_message(deliveries).subject == "Follow Up reminder"


async def test_telegram_pause_command_only_uses_linked_chat(
    api_client: httpx.AsyncClient,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
    monkeypatch,
) -> None:
    from api.routes import telegram

    profile = Profile(
        id=authenticated_user.id,
        email=authenticated_user.email,
        telegram_chat_id="phase20-chat",
        telegram_notifications_enabled=True,
    )
    db_session.add(profile)
    db_session.commit()
    replies: list[str] = []

    async def fake_reply(_: str, text: str) -> None:
        replies.append(text)

    monkeypatch.setattr(telegram, "_reply", fake_reply)
    monkeypatch.setattr(settings, "telegram_webhook_secret", "phase20-secret")
    response = await api_client.post(
        "/webhooks/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "phase20-secret"},
        json={"message": {"text": "/pause", "chat": {"id": "phase20-chat"}}},
    )
    db_session.refresh(profile)
    assert response.status_code == 204
    assert profile.telegram_notifications_enabled is False
    assert "paused" in replies[0]
