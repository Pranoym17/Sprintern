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


def test_planner_creates_idempotent_delivery_and_batches_by_timezone(db_session: Session) -> None:
    profile, match = create_match(db_session, cadence=NotificationCadence.HOURLY)
    now = datetime(2026, 7, 13, 14, 20, tzinfo=UTC)
    planner = NotificationPlanner()

    first = planner.plan_match(db_session, match, profile, now)
    db_session.flush()
    second = planner.plan_match(db_session, match, profile, now)
    delivery = db_session.scalar(select(NotificationDelivery))

    assert first == 1
    assert second == 0
    assert delivery is not None
    assert delivery.next_attempt_at == datetime(2026, 7, 13, 15, 0, tzinfo=UTC)
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

    first = await dispatcher.dispatch_due(now=datetime.now(UTC) + timedelta(seconds=1))
    second = await dispatcher.dispatch_due(now=datetime.now(UTC) + timedelta(seconds=2))
    delivery = db_session.scalar(select(NotificationDelivery))

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
    now = datetime.now(UTC) + timedelta(seconds=1)
    dispatcher = NotificationDispatcher(
        notification_factory(db_session), {NotificationChannel.EMAIL: provider}
    )

    assert await dispatcher.dispatch_due(now=now) == 0
    delivery = db_session.scalar(select(NotificationDelivery))

    assert delivery is not None and delivery.status == DeliveryStatus.FAILED
    assert delivery.attempt_count == 1
    assert delivery.next_attempt_at == now + timedelta(seconds=60)


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

    sent = await dispatcher.dispatch_due(now=now + timedelta(hours=2))

    assert sent == 2
    assert len(provider.messages) == 1
    assert provider.messages[0].subject == "Sprintern digest: 2 new internships"


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
