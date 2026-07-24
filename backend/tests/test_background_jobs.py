import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.jobs import BackgroundJobQueue
from api.models import BackgroundJob
from api.worker.runtime import BackgroundJobHandler


def test_queue_is_idempotent_and_retries_with_a_lease(db_session: Session) -> None:
    factory = sessionmaker(
        bind=db_session.get_bind(),
        class_=Session,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    queue = BackgroundJobQueue(factory)
    with factory.begin() as session:
        first = queue.enqueue(
            session,
            job_type="matching.all",
            idempotency_key="test:matching:one",
            correlation_id="test-correlation",
        )
        session.flush()
        first_id = first.id
        duplicate = queue.enqueue(
            session,
            job_type="matching.all",
            idempotency_key="test:matching:one",
        )
        assert duplicate.id == first_id

    claimed = queue.claim("worker-a", 60)
    assert claimed is not None
    assert claimed.id == first_id
    assert claimed.attempts == 1

    queue.fail(first_id, "worker-a", TimeoutError("provider timed out"))
    retried = db_session.get_one(BackgroundJob, first_id)
    assert retried.status == "queued"
    assert retried.last_error == "TimeoutError: provider timed out"

    retried.available_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()
    second_claim = queue.claim("worker-b", 60)
    assert second_claim is not None
    assert second_claim.attempts == 2
    queue.succeed(first_id, "worker-b")

    db_session.expire_all()
    completed = db_session.scalar(select(BackgroundJob).where(BackgroundJob.id == first_id))
    assert completed is not None
    assert completed.status == "succeeded"
    assert completed.finished_at is not None


def test_queue_dead_letters_after_max_attempts(db_session: Session) -> None:
    factory = sessionmaker(
        bind=db_session.get_bind(),
        class_=Session,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    queue = BackgroundJobQueue(factory)
    with factory.begin() as session:
        job = queue.enqueue(
            session,
            job_type="unknown",
            idempotency_key=f"test:dead:{uuid.uuid4()}",
            max_attempts=1,
        )
        session.flush()
        job_id = job.id
    claimed = queue.claim("worker-a", 60)
    assert claimed is not None
    queue.fail(job_id, "worker-a", ValueError("bad payload"))
    db_session.expire_all()
    failed = db_session.get_one(BackgroundJob, job_id)
    assert failed.status == "dead"


async def test_matching_job_enqueues_immediate_notification_dispatch(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.worker import runtime

    factory = sessionmaker(
        bind=db_session.get_bind(),
        class_=Session,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(runtime, "SessionLocal", factory)
    monkeypatch.setattr(
        "api.worker.runtime.matching_service.match_all", lambda _session: 0
    )
    matching_job = BackgroundJob(
        id=uuid.uuid4(),
        job_type="matching.all",
        idempotency_key=f"test:matching:{uuid.uuid4()}",
        correlation_id="matching-correlation",
    )
    async with httpx.AsyncClient() as client:
        await BackgroundJobHandler(client).handle(matching_job)

    dispatch = db_session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.idempotency_key
            == f"notifications:matching:{matching_job.id}"
        )
    )

    assert dispatch is not None
    assert dispatch.job_type == "notifications.dispatch"
    assert dispatch.correlation_id == "matching-correlation"
