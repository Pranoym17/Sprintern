import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.auth import AuthenticatedUser
from api.models import (
    DeliveryStatus,
    EmailSuppression,
    Job,
    JobMatch,
    JobSource,
    JobSourceName,
    NotificationCadence,
    NotificationChannel,
    NotificationDelivery,
    Profile,
)
from api.notifications import (
    DeliveryOutcome,
    NotificationDispatcher,
    NotificationMessage,
    NotificationPlanner,
    ProviderResult,
    ResendProvider,
    TelegramProvider,
)
from api.notifications.message_builder import build_message
from api.notifications.telegram_linking import TelegramLinkService
from api.settings import settings


def notification_factory(db_session: Session) -> sessionmaker[Session]:
    return sessionmaker(
        bind=db_session.get_bind(),
        class_=Session,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


def create_match(
    db_session: Session, *, cadence: NotificationCadence = NotificationCadence.INSTANT
) -> tuple[Profile, JobMatch]:
    now = datetime.now(UTC)
    profile = Profile(
        id=uuid.uuid4(),
        email="student@example.com",
        notification_cadence=cadence,
        email_notifications_enabled=True,
        email_notifications_consent_at=now,
    )
    job = Job(
        company="Example <Corp>",
        normalized_company="example corp",
        title="Software Intern & Builder",
        normalized_title="software intern builder",
        canonical_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
        first_seen_at=now,
        last_seen_at=now,
    )
    job.sources.append(
        JobSource(
            source=JobSourceName.GREENHOUSE,
            source_key="example",
            external_id=uuid.uuid4().hex,
            apply_url="https://example.com/apply?a=1&b=2",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    match = JobMatch(profile=profile, job=job, reasons=[])
    db_session.add(match)
    db_session.flush()
    return profile, match


def test_planner_creates_idempotent_daily_email_delivery(db_session: Session) -> None:
    profile, match = create_match(db_session, cadence=NotificationCadence.HOURLY)
    now = datetime(2026, 7, 13, 14, 20, tzinfo=UTC)
    planner = NotificationPlanner()

    first = planner.plan_match(db_session, match, profile, now)
    db_session.flush()
    second = planner.plan_match(db_session, match, profile, now)
    delivery = db_session.scalar(
        select(NotificationDelivery).where(NotificationDelivery.match_id == match.id)
    )

    assert first == 1
    assert second == 0
    assert delivery is not None
    assert delivery.cadence == NotificationCadence.DAILY
    assert delivery.next_attempt_at == datetime(2026, 7, 14, 8, 0, tzinfo=UTC)
    assert delivery.idempotency_key == f"{match.id}:email"


async def test_telegram_provider_handles_success_and_rate_limit() -> None:
    responses = [
        httpx.Response(200, json={"ok": True, "result": {"message_id": 42}}),
        httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 3}}),
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sendMessage")
        return responses.pop(0)

    message = NotificationMessage(
        "123", "Subject", "Text", "<p>Text</p>", "https://example.com", "key"
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = TelegramProvider("token", client)
        sent = await provider.send(message)
        limited = await provider.send(message)

    assert sent == ProviderResult(DeliveryOutcome.SENT, provider_message_id="42")
    assert limited.outcome == DeliveryOutcome.RATE_LIMITED
    assert limited.retry_after_seconds == 3


async def test_resend_provider_uses_stable_idempotency_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Idempotency-Key"] == "delivery-key"
        assert request.headers["Authorization"] == "Bearer resend-key"
        assert "\n" not in json.loads(request.content)["subject"]
        return httpx.Response(200, json={"id": "email-123"})

    message = NotificationMessage(
        "student@example.com",
        "Subject\nInjected",
        "Text",
        "<p>Text</p>",
        "https://example.com",
        "delivery-key",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await ResendProvider("resend-key", "alerts@example.com", client).send(message)

    assert result == ProviderResult(DeliveryOutcome.SENT, provider_message_id="email-123")


async def test_user_can_send_labelled_test_digest_without_delivery_rows(
    api_client: httpx.AsyncClient,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = Profile(
        id=authenticated_user.id,
        email=authenticated_user.email,
        email_notifications_enabled=True,
        email_notifications_consent_at=datetime.now(UTC),
    )
    db_session.add(profile)
    db_session.commit()
    messages: list[NotificationMessage] = []

    async def record(
        _provider: ResendProvider, message: NotificationMessage
    ) -> ProviderResult:
        messages.append(message)
        return ProviderResult(DeliveryOutcome.SENT, provider_message_id="test-email")

    monkeypatch.setattr(ResendProvider, "send", record)
    response = await api_client.post("/notifications/test", json={"channel": "email"})

    assert response.status_code == 200
    assert response.json()["outcome"] == "sent"
    assert messages[0].subject == "[Test] 3 new internship matches for you today"
    assert "source" not in messages[0].text.casefold()
    assert db_session.scalar(select(NotificationDelivery.id)) is None


@pytest.mark.parametrize("provider_name", ["telegram", "resend"])
async def test_notification_provider_timeout_is_retryable(provider_name: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider timed out", request=request)

    message = NotificationMessage(
        "recipient", "Subject", "Text", "<p>Text</p>", "https://example.com", "key"
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = (
            TelegramProvider("telegram-token", client)
            if provider_name == "telegram"
            else ResendProvider("resend-key", "alerts@example.com", client)
        )
        result = await provider.send(message)

    assert result.outcome == DeliveryOutcome.TRANSIENT_FAILURE
    assert result.error == "ReadTimeout"


class RecordingProvider:
    def __init__(self, result: ProviderResult) -> None:
        self.result = result
        self.messages: list[NotificationMessage] = []

    async def send(self, message: NotificationMessage) -> ProviderResult:
        self.messages.append(message)
        return self.result


async def test_dispatcher_claims_once_and_records_success(db_session: Session) -> None:
    profile, match = create_match(db_session)
    NotificationPlanner().plan_match(db_session, match, profile)
    db_session.commit()
    provider = RecordingProvider(ProviderResult(DeliveryOutcome.SENT, "provider-1"))
    dispatcher = NotificationDispatcher(
        notification_factory(db_session), {NotificationChannel.EMAIL: provider}
    )

    first = await dispatcher.dispatch_due(now=datetime.now(UTC) + timedelta(days=2))
    second = await dispatcher.dispatch_due(now=datetime.now(UTC) + timedelta(days=2, seconds=1))
    delivery = db_session.scalar(
        select(NotificationDelivery).where(NotificationDelivery.match_id == match.id)
    )

    assert first == 1
    assert second == 0
    assert len(provider.messages) == 1
    assert delivery is not None and delivery.status == DeliveryStatus.SENT
    assert delivery.provider_message_id == "provider-1"


async def test_dispatcher_retries_transient_failure(db_session: Session) -> None:
    profile, match = create_match(db_session)
    NotificationPlanner().plan_match(db_session, match, profile)
    db_session.commit()
    provider = RecordingProvider(
        ProviderResult(DeliveryOutcome.RATE_LIMITED, error="slow down", retry_after_seconds=60)
    )
    now = datetime.now(UTC) + timedelta(days=2)
    dispatcher = NotificationDispatcher(
        notification_factory(db_session), {NotificationChannel.EMAIL: provider}
    )

    assert await dispatcher.dispatch_due(now=now) == 0
    delivery = db_session.scalar(select(NotificationDelivery))

    assert delivery is not None and delivery.status == DeliveryStatus.FAILED
    assert delivery.attempt_count == 1
    assert delivery.next_attempt_at == now + timedelta(seconds=60)


async def test_repeated_permanent_email_failures_suppress_recipient(db_session: Session) -> None:
    profile, first_match = create_match(db_session)
    matches = [first_match]
    now = datetime.now(UTC)
    for index in range(2):
        job = Job(
            company=f"Failure {index}",
            normalized_company=f"failure {index}",
            title="Software Intern",
            normalized_title="software intern",
            canonical_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
            first_seen_at=now,
            last_seen_at=now,
        )
        job.sources.append(
            JobSource(
                source=JobSourceName.GREENHOUSE,
                source_key=f"failure-{index}",
                external_id=uuid.uuid4().hex,
                apply_url=f"https://example.com/apply/{index}",
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        match = JobMatch(profile=profile, job=job, reasons=[])
        db_session.add(match)
        matches.append(match)
    planner = NotificationPlanner()
    for match in matches:
        planner.plan_match(db_session, match, profile, now)
    db_session.commit()
    provider = RecordingProvider(
        ProviderResult(
            DeliveryOutcome.PERMANENT_FAILURE, error="Resend rejected message with HTTP 422"
        )
    )
    dispatcher = NotificationDispatcher(
        notification_factory(db_session), {NotificationChannel.EMAIL: provider}
    )

    await dispatcher.dispatch_due(limit=10, now=now + timedelta(days=2))
    db_session.refresh(profile)

    assert profile.email_notifications_enabled is False
    assert profile.email_suppression_reason == "repeated_failure"
    assert db_session.get(EmailSuppression, "student@example.com") is not None


async def test_dispatcher_groups_due_digest_deliveries(db_session: Session) -> None:
    profile, first_match = create_match(db_session, cadence=NotificationCadence.HOURLY)
    now = datetime.now(UTC)
    second_job = Job(
        company="Second",
        normalized_company="second",
        title="Data Intern",
        normalized_title="data intern",
        canonical_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
        first_seen_at=now,
        last_seen_at=now,
    )
    second_job.sources.append(
        JobSource(
            source=JobSourceName.LEVER,
            source_key="second",
            external_id=uuid.uuid4().hex,
            apply_url="https://second.example/apply",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    second_match = JobMatch(profile=profile, job=second_job, reasons=[])
    db_session.add(second_match)
    db_session.flush()
    planner = NotificationPlanner()
    planner.plan_match(db_session, first_match, profile, now)
    planner.plan_match(db_session, second_match, profile, now)
    db_session.commit()
    provider = RecordingProvider(ProviderResult(DeliveryOutcome.SENT, "digest-1"))
    dispatcher = NotificationDispatcher(
        notification_factory(db_session), {NotificationChannel.EMAIL: provider}
    )

    sent = await dispatcher.dispatch_due(now=now + timedelta(days=2))

    assert sent == 2
    assert len(provider.messages) == 1
    assert provider.messages[0].subject == "2 new internship matches for you today"


async def test_dispatcher_sends_one_telegram_message_per_match(
    db_session: Session,
) -> None:
    profile, first_match = create_match(db_session)
    profile.email_notifications_enabled = False
    profile.email_notifications_consent_at = None
    profile.telegram_chat_id = "instant-chat"
    profile.telegram_notifications_enabled = True
    now = datetime.now(UTC)
    second_job = Job(
        company="Second Telegram",
        normalized_company="second telegram",
        title="Data Intern",
        normalized_title="data intern",
        canonical_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
        first_seen_at=now,
        last_seen_at=now,
    )
    second_job.sources.append(
        JobSource(
            source=JobSourceName.LEVER,
            source_key="telegram-second",
            external_id=uuid.uuid4().hex,
            apply_url="https://second.example/apply",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    second_match = JobMatch(profile=profile, job=second_job, reasons=[])
    db_session.add(second_match)
    db_session.flush()
    planner = NotificationPlanner()
    planner.plan_match(db_session, first_match, profile, now)
    planner.plan_match(db_session, second_match, profile, now)
    db_session.commit()
    provider = RecordingProvider(ProviderResult(DeliveryOutcome.SENT, "telegram"))
    dispatcher = NotificationDispatcher(
        notification_factory(db_session), {NotificationChannel.TELEGRAM: provider}
    )

    sent = await dispatcher.dispatch_due(now=now + timedelta(seconds=1))

    assert sent == 2
    assert len(provider.messages) == 2
    assert all(message.text.count("🎯 New match:") == 1 for message in provider.messages)
    assert all("source" not in message.text.casefold() for message in provider.messages)


async def test_dispatcher_curates_digest_to_user_limit(db_session: Session) -> None:
    profile, first_match = create_match(db_session)
    profile.email_digest_job_limit = 2
    now = datetime.now(UTC)
    matches = [first_match]
    for index in range(3):
        job = Job(
            company=f"Rank {index}",
            normalized_company=f"rank {index}",
            title=f"Software Intern {index}",
            normalized_title=f"software intern {index}",
            canonical_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
            first_seen_at=now + timedelta(minutes=index),
            last_seen_at=now + timedelta(minutes=index),
        )
        job.sources.append(
            JobSource(
                source=JobSourceName.GREENHOUSE,
                source_key=f"rank-{index}",
                external_id=uuid.uuid4().hex,
                apply_url=f"https://employer.example/apply/{index}",
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        match = JobMatch(
            profile=profile,
            job=job,
            reasons=[
                {
                    "dimensions": {
                        key: key
                        for key in ["role", "location", "term"][: index + 1]
                    }
                }
            ],
        )
        db_session.add(match)
        matches.append(match)
    planner = NotificationPlanner()
    for match in matches:
        planner.plan_match(db_session, match, profile, now)
    db_session.commit()
    provider = RecordingProvider(ProviderResult(DeliveryOutcome.SENT, "digest-curated"))
    dispatcher = NotificationDispatcher(
        notification_factory(db_session), {NotificationChannel.EMAIL: provider}
    )

    sent = await dispatcher.dispatch_due(now=now + timedelta(days=2), limit=100)
    deliveries = list(
        db_session.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.profile_id == profile.id,
                NotificationDelivery.channel == NotificationChannel.EMAIL,
            )
        )
    )

    assert sent == 2
    assert len(provider.messages) == 1
    assert provider.messages[0].subject == "2 new internship matches for you today"
    assert "Software Intern 2" in provider.messages[0].html
    assert sum(item.status == DeliveryStatus.SENT for item in deliveries) == 2
    assert sum(item.queued_reason == "digest_not_selected" for item in deliveries) == 2


def test_message_builder_escapes_untrusted_html(db_session: Session) -> None:
    profile, match = create_match(db_session)
    NotificationPlanner().plan_match(db_session, match, profile)
    db_session.flush()
    delivery = db_session.scalar(select(NotificationDelivery))
    assert delivery is not None

    message = build_message([delivery])

    assert "Example &lt;Corp&gt;" in message.html
    assert "Software Intern &amp; Builder" in message.html
    assert "&amp;" in message.html
    assert message.unsubscribe_url is not None
    assert "Unsubscribe" in message.html
    assert "Support:" in message.text
    assert "Source:" not in message.text
    assert "github" not in message.text.casefold()


def test_telegram_message_has_no_email_unsubscribe_link(db_session: Session) -> None:
    profile, match = create_match(db_session)
    profile.email_notifications_enabled = False
    profile.email_notifications_consent_at = None
    profile.telegram_chat_id = "12345"
    profile.telegram_notifications_enabled = True
    NotificationPlanner().plan_match(db_session, match, profile)
    db_session.flush()
    delivery = db_session.scalar(
        select(NotificationDelivery).where(
            NotificationDelivery.channel == NotificationChannel.TELEGRAM
        )
    )
    assert delivery is not None

    message = build_message([delivery])

    assert message.unsubscribe_url is None
    assert "Unsubscribe" not in message.text


def test_telegram_link_token_is_single_use_and_not_stored_raw(db_session: Session) -> None:
    profile = Profile(id=uuid.uuid4(), email="student@example.com")
    db_session.add(profile)
    db_session.flush()
    service = TelegramLinkService()
    link = service.create(db_session, profile.id)
    db_session.flush()

    linked = service.consume(db_session, link.token, "12345")
    reused = service.consume(db_session, link.token, "99999")

    assert linked is profile
    assert reused is None
    assert profile.telegram_chat_id == "12345"
    assert link.token not in str(profile.telegram_link_tokens[0].token_hash)


async def test_telegram_webhook_consumes_authenticated_link(
    api_client: httpx.AsyncClient,
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "telegram_bot_username", "SprinternBot")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "webhook-secret")
    link_response = await api_client.post("/users/me/telegram-link")
    token = link_response.json()["token"]

    webhook_response = await api_client.post(
        "/webhooks/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"},
        json={"message": {"text": f"/start {token}", "chat": {"id": 12345}}},
    )
    profile = db_session.get(Profile, authenticated_user.id)

    assert link_response.status_code == 200
    assert webhook_response.status_code == 204
    assert profile is not None and profile.telegram_chat_id == "12345"
    assert profile.telegram_notifications_enabled is True
