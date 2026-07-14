import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient
from pydantic import AnyHttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.ingestion import PollBatch, RawSourceJob
from api.ingestion.adapters import GreenhouseAdapter, LeverAdapter, RemoteOKAdapter
from api.ingestion.factory import build_adapter
from api.ingestion.http import RetryingHTTPClient, SourceHTTPError
from api.ingestion.normalization import canonicalize_url, normalize_job, normalize_text
from api.ingestion.persistence import JobPersister, PersistenceOutcome
from api.ingestion.service import IngestionService
from api.models import (
    IngestionRunStatus,
    Job,
    JobSource,
    JobSourceName,
    JobStatus,
    PollCompleteness,
    SourceState,
)
from api.schemas.ingestion import IngestionRunRequest
from api.settings import settings


class FakeAdapter:
    source = JobSourceName.GREENHOUSE
    source_key = "test-board"

    def __init__(self, batch: PollBatch | None = None, error: Exception | None = None) -> None:
        self.batch = batch
        self.error = error
        self.received_cursor: dict[str, Any] | None = None

    async def fetch(self, cursor: dict[str, Any]) -> PollBatch:
        self.received_cursor = cursor
        if self.error:
            raise self.error
        assert self.batch is not None
        return self.batch


def raw_job(external_id: str = "job-1", company: str = "Example, Inc.") -> RawSourceJob:
    return RawSourceJob(
        external_id=external_id,
        company=company,
        title=" Software   Engineering Intern ",
        location="Toronto, ON",
        apply_url=AnyHttpUrl("https://jobs.example.com/apply?utm_source=test&id=1"),
        raw_metadata={"department": "Engineering"},
    )


@pytest.fixture
def ingestion_factory(db_session: Session) -> sessionmaker[Session]:
    return sessionmaker(
        bind=db_session.get_bind(),
        class_=Session,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


def test_normalizes_text_url_and_fingerprint() -> None:
    first = normalize_job(JobSourceName.GREENHOUSE, "example", raw_job())
    second = normalize_job(
        JobSourceName.LEVER, "example", raw_job("different-source-id", "example inc")
    )

    assert normalize_text("Montréal, QC") == "montreal qc"
    assert (
        canonicalize_url("HTTPS://Example.com/a?utm_source=x&id=2#top")
        == "https://example.com/a?id=2"
    )
    assert first.canonical_fingerprint == second.canonical_fingerprint
    assert first.apply_url == "https://jobs.example.com/apply?id=1"


async def test_http_client_honors_retry_after() -> None:
    calls = 0
    delays: list[float] = []

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"ok": True})

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        retrying = RetryingHTTPClient(client, sleep=record_sleep)
        result = await retrying.get_json("https://example.com/jobs")

    assert result == {"ok": True}
    assert calls == 2
    assert delays == [2.0]


async def test_http_client_does_not_retry_permanent_errors() -> None:
    calls = 0

    async def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceHTTPError):
            await RetryingHTTPClient(client).get_json("https://example.com/missing")

    assert calls == 1


async def test_ingestion_is_idempotent_and_advances_cursor(
    ingestion_factory: sessionmaker[Session],
) -> None:
    batch = PollBatch(
        records=[raw_job()],
        completeness=PollCompleteness.COMPLETE,
        next_cursor={"page": 2},
    )
    service = IngestionService(ingestion_factory)
    first = await service.run(FakeAdapter(batch))
    second_adapter = FakeAdapter(batch)
    second = await service.run(second_adapter)

    with ingestion_factory() as session:
        jobs = list(session.scalars(select(Job)))
        state = session.scalar(select(SourceState))

    assert first.created_count == 1
    assert second.updated_count == 1
    assert len(jobs) == 1
    assert state is not None and state.cursor == {"page": 2}
    assert second_adapter.received_cursor == {"page": 2}


async def test_failed_run_preserves_cursor_and_records_failure(
    ingestion_factory: sessionmaker[Session],
) -> None:
    service = IngestionService(ingestion_factory)
    successful = PollBatch(
        records=[],
        completeness=PollCompleteness.INCREMENTAL,
        next_cursor={"sha": "good"},
    )
    await service.run(FakeAdapter(successful))

    with pytest.raises(RuntimeError):
        await service.run(FakeAdapter(error=RuntimeError("source unavailable")))

    with ingestion_factory() as session:
        state = session.scalar(select(SourceState))

    assert state is not None
    assert state.cursor == {"sha": "good"}
    assert state.consecutive_failures == 1
    assert state.last_error == "RuntimeError: source unavailable"


async def test_same_source_runs_do_not_overlap(
    ingestion_factory: sessionmaker[Session],
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class BlockingAdapter(FakeAdapter):
        async def fetch(self, cursor: dict[str, Any]) -> PollBatch:
            started.set()
            await release.wait()
            return PollBatch(records=[], completeness=PollCompleteness.COMPLETE)

    service = IngestionService(ingestion_factory)
    first_task = asyncio.create_task(service.run(BlockingAdapter()))
    await started.wait()
    skipped = await service.run(BlockingAdapter())
    release.set()
    completed = await first_task

    assert skipped.status == IngestionRunStatus.SKIPPED
    assert completed.status == IngestionRunStatus.SUCCEEDED


async def test_internal_source_status_requires_service_key(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    unconfigured = await api_client.get("/internal/sources/status")
    assert unconfigured.status_code == 503

    monkeypatch.setattr(settings, "internal_api_key", "test-service-key")
    unauthorized = await api_client.get("/internal/sources/status")
    authorized = await api_client.get(
        "/internal/sources/status", headers={"X-Internal-API-Key": "test-service-key"}
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


async def test_complete_snapshots_drive_stale_and_expired_lifecycle(
    ingestion_factory: sessionmaker[Session],
) -> None:
    service = IngestionService(ingestion_factory)
    await service.run(
        FakeAdapter(
            PollBatch(
                records=[raw_job("removed"), raw_job("remaining", "Other")],
                completeness=PollCompleteness.COMPLETE,
            )
        )
    )
    only_remaining = PollBatch(
        records=[raw_job("remaining", "Other")],
        completeness=PollCompleteness.COMPLETE,
    )

    await service.run(FakeAdapter(only_remaining))
    with ingestion_factory() as session:
        job = session.scalar(select(Job).where(Job.normalized_company == "example inc"))
        assert job is not None and job.status == JobStatus.ACTIVE

    await service.run(FakeAdapter(only_remaining))
    with ingestion_factory() as session:
        job = session.scalar(select(Job).where(Job.normalized_company == "example inc"))
        assert job is not None and job.status == JobStatus.STALE

    await service.run(FakeAdapter(only_remaining))
    with ingestion_factory() as session:
        job = session.scalar(select(Job).where(Job.normalized_company == "example inc"))
        assert job is not None and job.status == JobStatus.EXPIRED
        assert job.expired_at is not None


async def test_partial_and_empty_snapshots_do_not_expire_jobs(
    ingestion_factory: sessionmaker[Session],
) -> None:
    service = IngestionService(ingestion_factory)
    await service.run(
        FakeAdapter(PollBatch(records=[raw_job()], completeness=PollCompleteness.COMPLETE))
    )
    await service.run(FakeAdapter(PollBatch(records=[], completeness=PollCompleteness.PARTIAL)))
    empty_run = await service.run(
        FakeAdapter(PollBatch(records=[], completeness=PollCompleteness.COMPLETE))
    )

    with ingestion_factory() as session:
        job = session.scalar(select(Job))
        source = session.scalar(select(JobSource))

    assert job is not None and job.status == JobStatus.ACTIVE
    assert source is not None and source.missing_snapshot_count == 0
    assert empty_run.error == "Empty snapshot ignored for lifecycle safety"


def test_expired_external_id_reused_after_threshold_creates_repost(
    db_session: Session,
) -> None:
    persister = JobPersister(repost_threshold_days=30)
    old_seen_at = datetime.now(UTC) - timedelta(days=31)
    candidate = normalize_job(JobSourceName.GREENHOUSE, "example", raw_job())
    assert persister.persist(db_session, candidate, old_seen_at) == PersistenceOutcome.CREATED
    db_session.commit()

    original_job = db_session.scalar(select(Job))
    original_source = db_session.scalar(select(JobSource))
    assert original_job is not None and original_source is not None
    original_job.status = JobStatus.EXPIRED
    original_source.active = False
    original_source.missing_snapshot_count = 3
    db_session.commit()

    outcome = persister.persist(db_session, candidate, datetime.now(UTC))
    db_session.commit()
    sources = list(db_session.scalars(select(JobSource).order_by(JobSource.occurrence)))

    assert outcome == PersistenceOutcome.CREATED
    assert [source.occurrence for source in sources] == [1, 2]
    assert len(list(db_session.scalars(select(Job)))) == 2


async def test_manual_ingestion_factory_builds_configured_adapters() -> None:
    async with httpx.AsyncClient() as client:
        greenhouse = build_adapter(
            IngestionRunRequest(
                source=JobSourceName.GREENHOUSE, company="Example", board_token="example"
            ),
            client,
        )
        lever = build_adapter(
            IngestionRunRequest(
                source=JobSourceName.LEVER,
                company="Example",
                site="example",
                region="eu",
            ),
            client,
        )
        remoteok = build_adapter(IngestionRunRequest(source=JobSourceName.REMOTEOK), client)

    assert isinstance(greenhouse, GreenhouseAdapter)
    assert isinstance(lever, LeverAdapter)
    assert lever.base_url == "https://api.eu.lever.co"
    assert isinstance(remoteok, RemoteOKAdapter)
