import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from api.models import BackgroundJob
from api.observability import redact_text


class BackgroundJobQueue:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    @staticmethod
    def enqueue(
        session: Session,
        *,
        job_type: str,
        idempotency_key: str,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        max_attempts: int = 5,
        available_at: datetime | None = None,
    ) -> BackgroundJob:
        job_id = uuid.uuid4()
        inserted_id = session.scalar(
            insert(BackgroundJob)
            .values(
                id=job_id,
                job_type=job_type,
                idempotency_key=idempotency_key,
                payload=payload or {},
                correlation_id=correlation_id or uuid.uuid4().hex,
                max_attempts=max_attempts,
                available_at=available_at or datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=[BackgroundJob.idempotency_key])
            .returning(BackgroundJob.id)
        )
        resolved_id = inserted_id or session.scalar(
            select(BackgroundJob.id).where(BackgroundJob.idempotency_key == idempotency_key)
        )
        if resolved_id is None:
            raise RuntimeError("background job idempotency conflict could not be resolved")
        return session.get_one(BackgroundJob, resolved_id)

    def claim(self, owner: str, lease_seconds: int) -> BackgroundJob | None:
        now = datetime.now(UTC)
        expired = now - timedelta(seconds=lease_seconds)
        with self.session_factory.begin() as session:
            job = session.scalar(
                select(BackgroundJob)
                .where(
                    BackgroundJob.status.in_(("queued", "running")),
                    BackgroundJob.available_at <= now,
                    or_(BackgroundJob.locked_at.is_(None), BackgroundJob.locked_at < expired),
                )
                .order_by(BackgroundJob.available_at, BackgroundJob.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            job.status = "running"
            job.attempts += 1
            job.locked_at = now
            job.lease_owner = owner
            session.flush()
            session.expunge(job)
            return job

    def succeed(self, job_id: uuid.UUID, owner: str) -> None:
        with self.session_factory.begin() as session:
            job = session.get_one(BackgroundJob, job_id)
            if job.lease_owner != owner:
                return
            job.status = "succeeded"
            job.finished_at = datetime.now(UTC)
            job.locked_at = None
            job.lease_owner = None
            job.last_error = None

    def fail(self, job_id: uuid.UUID, owner: str, exc: Exception) -> None:
        now = datetime.now(UTC)
        with self.session_factory.begin() as session:
            job = session.get_one(BackgroundJob, job_id)
            if job.lease_owner != owner:
                return
            job.last_error = redact_text(f"{type(exc).__name__}: {exc}")[:2000]
            job.locked_at = None
            job.lease_owner = None
            if job.attempts >= job.max_attempts:
                job.status = "dead"
                job.finished_at = now
            else:
                job.status = "queued"
                delay = min(30 * (2 ** max(job.attempts - 1, 0)), 3600)
                job.available_at = now + timedelta(seconds=delay)
