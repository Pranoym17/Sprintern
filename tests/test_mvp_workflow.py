from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import AnyHttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from api.ingestion import PollBatch, RawSourceJob
from api.ingestion.service import IngestionService
from api.models import (
    DeliveryStatus,
    Job,
    JobMatch,
    JobSourceName,
    MatchStatus,
    NotificationChannel,
    NotificationDelivery,
    PollCompleteness,
    Profile,
)
from api.notifications import (
    DeliveryOutcome,
    NotificationDispatcher,
    NotificationMessage,
    ProviderResult,
)


class GitHubWorkflowAdapter:
    source = JobSourceName.GITHUB_REPO
    source_key = "phase10/Summer2027-Internships:README.md"

    def __init__(self) -> None:
        self.seen_cursors: list[dict[str, Any]] = []

    async def fetch(self, cursor: dict[str, Any]) -> PollBatch:
        self.seen_cursors.append(cursor)
        return PollBatch(
            records=[
                RawSourceJob(
                    external_id="phase10-job-1",
                    company="Example Robotics",
                    title="Backend Software Engineering Intern",
                    location="Toronto, Canada",
                    term="Summer 2027",
                    apply_url=AnyHttpUrl("https://careers.example.com/jobs/phase10-job-1"),
                    posted_at=datetime.now(UTC),
                )
            ],
            completeness=PollCompleteness.COMPLETE,
            next_cursor={"sha": "stable-commit"},
        )


class RecordingProvider:
    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        self.messages: list[NotificationMessage] = []

    async def send(self, message: NotificationMessage) -> ProviderResult:
        self.messages.append(message)
        return ProviderResult(DeliveryOutcome.SENT, self.provider_id)


def workflow_factory(session: Session) -> sessionmaker[Session]:
    return sessionmaker(
        bind=session.get_bind(),
        class_=Session,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


async def test_authenticated_mvp_workflow_is_idempotent(
    api_client: httpx.AsyncClient, db_session: Session
) -> None:
    # Supabase signup/signin and JWT verification have dedicated boundary tests;
    # this test begins with the authenticated identity injected by api_client.
    profile_response = await api_client.get("/users/me")
    assert profile_response.status_code == 200
    profile_id = profile_response.json()["id"]
    profile = db_session.get_one(Profile, profile_id)
    profile.telegram_chat_id = "phase10-chat"
    profile.telegram_notifications_enabled = True
    profile.email_notifications_enabled = True
    db_session.commit()

    filter_response = await api_client.post(
        "/filters",
        json={
            "name": "Toronto backend internships",
            "role_keywords": ["backend", "software"],
            "location_keywords": ["Toronto", "Canada"],
            "terms": ["Summer 2027"],
        },
    )
    assert filter_response.status_code == 201

    factory = workflow_factory(db_session)
    adapter = GitHubWorkflowAdapter()
    ingestion = IngestionService(factory)
    first_run = await ingestion.run(adapter)
    second_run = await ingestion.run(adapter)

    assert first_run.created_count == 1
    assert second_run.created_count == 0
    assert second_run.updated_count == 1
    assert adapter.seen_cursors == [{}, {"sha": "stable-commit"}]

    matches_response = await api_client.get("/matches")
    matches = matches_response.json()["items"]
    assert len(matches) == 1
    match = matches[0]
    assert match["job"]["company"] == "Example Robotics"
    assert match["job"]["sources"][0]["apply_url"] == (
        "https://careers.example.com/jobs/phase10-job-1"
    )

    email = RecordingProvider("email-provider-id")
    telegram = RecordingProvider("telegram-provider-id")
    dispatcher = NotificationDispatcher(
        factory,
        {NotificationChannel.EMAIL: email, NotificationChannel.TELEGRAM: telegram},
    )
    now = datetime.now(UTC) + timedelta(seconds=1)
    assert await dispatcher.dispatch_due(now=now, limit=100) == 2
    assert await dispatcher.dispatch_due(now=now + timedelta(seconds=1), limit=100) == 0
    assert len(email.messages) == 1
    assert len(telegram.messages) == 1
    assert email.messages[0].apply_url == "https://careers.example.com/jobs/phase10-job-1"

    applied = await api_client.patch(
        f"/matches/{match['id']}", json={"status": MatchStatus.APPLIED.value}
    )
    analytics = await api_client.get("/analytics/summary")
    assert applied.status_code == 200
    assert applied.json()["applied_at"] is not None
    assert analytics.json()["matched_count"] == 1
    assert analytics.json()["applied_count"] == 1

    assert db_session.scalar(select(func.count()).select_from(Job)) == 1
    assert db_session.scalar(select(func.count()).select_from(JobMatch)) == 1
    assert db_session.scalar(select(func.count()).select_from(NotificationDelivery)) == 2
    assert set(db_session.scalars(select(NotificationDelivery.status))) == {DeliveryStatus.SENT}
