import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from api.database import SessionLocal
from api.models import JobSourceName, SourceState
from api.scheduler.config import GitHubSourceConfig, SchedulerSourceConfig
from api.scheduler.runtime import build_scheduler, scheduler_process_lock
from api.scheduler.status import SchedulerRuntimeStore, scheduler_status
from api.scheduler.workflows import SchedulerWorkflows
from api.settings import settings


class RecordingWorkflows:
    def __init__(self) -> None:
        self.sources: list[GitHubSourceConfig] = []
        self.dispatches = 0

    async def ingest_github(self, source: GitHubSourceConfig) -> None:
        self.sources.append(source)

    async def dispatch_notifications(self) -> None:
        self.dispatches += 1


def scheduler_config() -> SchedulerSourceConfig:
    return SchedulerSourceConfig(
        github=[
            GitHubSourceConfig(
                owner="scheduler-test-owner",
                repository="Scheduler-Test-Internships",
                branch="dev",
                term="Summer 2027",
                poll_minutes=15,
                jitter_seconds=0,
            )
        ]
    )


def test_registers_stable_non_overlapping_jobs() -> None:
    scheduler = build_scheduler(RecordingWorkflows(), scheduler_config())  # type: ignore[arg-type]

    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {
        "ingest:github:scheduler-test-owner/Scheduler-Test-Internships:README.md",
        "notifications:dispatch",
    }
    assert all(job.max_instances == 1 for job in jobs.values())
    assert all(job.coalesce is True for job in jobs.values())
    assert all(
        job.misfire_grace_time == settings.scheduler_misfire_grace_seconds
        for job in jobs.values()
    )


def test_fastapi_import_does_not_create_scheduler() -> None:
    from api.main import app

    assert app.state.__dict__.get("scheduler") is None


async def test_backoff_skips_scheduled_ingestion(db_session: Session) -> None:
    source = scheduler_config().enabled_github[0]
    state = SourceState(
        source=JobSourceName.GITHUB_REPO,
        source_key=source.source_key,
        backoff_until=datetime.now(UTC) + timedelta(minutes=5),
    )
    db_session.add(state)
    db_session.commit()
    factory = sessionmaker(
        bind=db_session.get_bind(),
        class_=Session,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    def fail_request(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("backoff must prevent GitHub requests")

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail_request)) as client:
        await SchedulerWorkflows(client, factory).ingest_github(source)


async def test_notification_workflow_treats_zero_due_as_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class Dispatcher:
        async def dispatch_due(self, *, limit: int) -> int:
            nonlocal calls
            calls += 1
            assert limit == 100
            return 0

    def fake_builder(*_args: Any, **_kwargs: Any) -> Dispatcher:
        return Dispatcher()

    monkeypatch.setattr("api.scheduler.workflows.build_dispatcher", fake_builder)
    async with httpx.AsyncClient() as client:
        await SchedulerWorkflows(client).dispatch_notifications()

    assert calls == 1


def test_runtime_heartbeat_reports_health_and_protects_new_owner(
    db_session: Session,
) -> None:
    factory = sessionmaker(
        bind=db_session.get_bind(),
        class_=Session,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    store = SchedulerRuntimeStore(factory)
    first_instance = uuid.uuid4()
    second_instance = uuid.uuid4()
    started = datetime.now(UTC)
    jobs = [{"id": "notifications:dispatch", "next_run_at": started.isoformat()}]

    store.start(first_instance, jobs, started)
    healthy = scheduler_status(db_session, 30, started + timedelta(seconds=10))
    assert healthy.state == "healthy"
    assert healthy.instance_id == first_instance
    assert healthy.configured_jobs[0].id == "notifications:dispatch"

    stale = scheduler_status(db_session, 30, started + timedelta(seconds=91))
    assert stale.state == "stale"

    store.start(second_instance, jobs, started + timedelta(seconds=100))
    assert store.heartbeat(first_instance, jobs, started + timedelta(seconds=101)) is False
    assert store.stop(first_instance, started + timedelta(seconds=102)) is False
    assert store.stop(second_instance, started + timedelta(seconds=103)) is True
    stopped = scheduler_status(db_session, 30, started + timedelta(seconds=104))
    assert stopped.state == "stopped"


async def test_scheduler_status_endpoint_is_protected(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "internal_api_key", "scheduler-test-key")

    unauthorized = await api_client.get("/internal/scheduler/status")
    authorized = await api_client.get(
        "/internal/scheduler/status",
        headers={"X-Internal-API-Key": "scheduler-test-key"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["state"] in {"healthy", "stale", "stopped", "unknown"}


def test_process_lock_rejects_second_scheduler() -> None:
    with scheduler_process_lock(SessionLocal):
        with pytest.raises(RuntimeError, match="already running"):
            with scheduler_process_lock(SessionLocal):
                raise AssertionError("a second scheduler must not acquire the lock")


async def test_workflow_waits_for_active_work() -> None:
    release = asyncio.Event()
    async with httpx.AsyncClient() as client:
        workflows = SchedulerWorkflows(client)
        active = asyncio.create_task(workflows._tracked(release.wait()))
        await asyncio.sleep(0)

        assert await workflows.wait_until_idle(0) is False
        release.set()
        await active
        assert await workflows.wait_until_idle(1) is True
