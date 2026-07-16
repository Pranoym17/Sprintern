import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from api.database import SessionLocal
from api.models import SchedulerRuntime
from api.schemas.scheduler import SchedulerJobStatus, SchedulerStatusResponse

RUNTIME_NAME = "default"
SCHEDULER_VERSION = "0.1.0"


class SchedulerRuntimeStore:
    def __init__(self, session_factory: sessionmaker[Session] = SessionLocal) -> None:
        self.session_factory = session_factory

    def start(
        self,
        instance_id: uuid.UUID,
        jobs: list[dict[str, Any]],
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(UTC)
        statement = insert(SchedulerRuntime).values(
            name=RUNTIME_NAME,
            instance_id=instance_id,
            version=SCHEDULER_VERSION,
            started_at=now,
            last_heartbeat_at=now,
            stopped_at=None,
            last_error=None,
            jobs=jobs,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[SchedulerRuntime.name],
            set_={
                "instance_id": instance_id,
                "version": SCHEDULER_VERSION,
                "started_at": now,
                "last_heartbeat_at": now,
                "stopped_at": None,
                "last_error": None,
                "jobs": jobs,
            },
        )
        with self.session_factory() as session:
            session.execute(statement)
            session.commit()

    def heartbeat(
        self,
        instance_id: uuid.UUID,
        jobs: list[dict[str, Any]],
        now: datetime | None = None,
    ) -> bool:
        now = now or datetime.now(UTC)
        with self.session_factory() as session:
            result = cast(
                CursorResult[Any],
                session.execute(
                    update(SchedulerRuntime)
                    .where(
                        SchedulerRuntime.name == RUNTIME_NAME,
                        SchedulerRuntime.instance_id == instance_id,
                    )
                    .values(last_heartbeat_at=now, jobs=jobs)
                ),
            )
            session.commit()
            return bool(result.rowcount)

    def stop(self, instance_id: uuid.UUID, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        with self.session_factory() as session:
            result = cast(
                CursorResult[Any],
                session.execute(
                    update(SchedulerRuntime)
                    .where(
                        SchedulerRuntime.name == RUNTIME_NAME,
                        SchedulerRuntime.instance_id == instance_id,
                    )
                    .values(stopped_at=now, last_heartbeat_at=now)
                ),
            )
            session.commit()
            return bool(result.rowcount)


def scheduler_status(
    session: Session,
    heartbeat_interval_seconds: int,
    now: datetime | None = None,
) -> SchedulerStatusResponse:
    now = now or datetime.now(UTC)
    runtime = session.get(SchedulerRuntime, RUNTIME_NAME)
    if runtime is None:
        return SchedulerStatusResponse(state="unknown", configured_jobs=[])

    heartbeat_age = max((now - runtime.last_heartbeat_at).total_seconds(), 0.0)
    stale_after = max(heartbeat_interval_seconds * 3, 90)
    if runtime.stopped_at is not None:
        state = "stopped"
    elif heartbeat_age > stale_after:
        state = "stale"
    else:
        state = "healthy"
    return SchedulerStatusResponse(
        state=state,
        instance_id=runtime.instance_id,
        version=runtime.version,
        started_at=runtime.started_at,
        last_heartbeat_at=runtime.last_heartbeat_at,
        heartbeat_age_seconds=heartbeat_age,
        stopped_at=runtime.stopped_at,
        configured_jobs=[SchedulerJobStatus.model_validate(job) for job in runtime.jobs],
        last_error=runtime.last_error,
    )
