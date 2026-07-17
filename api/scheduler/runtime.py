import asyncio
import hashlib
import logging
import signal
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from api.database import SessionLocal
from api.scheduler.config import SchedulerSourceConfig, load_source_config
from api.scheduler.status import SchedulerRuntimeStore
from api.scheduler.workflows import SchedulerWorkflows
from api.settings import Settings, settings

logger = logging.getLogger(__name__)


def job_snapshot(scheduler: AsyncIOScheduler) -> list[dict[str, str | None]]:
    return [
        {
            "id": job.id,
            "next_run_at": job.next_run_time.isoformat() if job.next_run_time else None,
        }
        for job in scheduler.get_jobs()
    ]


def build_scheduler(
    workflows: SchedulerWorkflows,
    source_config: SchedulerSourceConfig,
    app_settings: Settings = settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=app_settings.scheduler_timezone)
    startup_time = datetime.now(UTC)
    for source in source_config.enabled_github:
        scheduler.add_job(
            workflows.ingest_github,
            "interval",
            args=[source],
            minutes=source.poll_minutes,
            jitter=source.jitter_seconds or None,
            id=source.job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=app_settings.scheduler_misfire_grace_seconds,
            next_run_time=startup_time,
        )
    scheduler.add_job(
        workflows.dispatch_notifications,
        "interval",
        seconds=app_settings.scheduler_notification_interval_seconds,
        id="notifications:dispatch",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=app_settings.scheduler_misfire_grace_seconds,
        next_run_time=startup_time,
    )
    return scheduler


async def run_scheduler(app_settings: Settings = settings) -> None:
    source_config = load_source_config(app_settings.scheduler_source_config)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        loop.call_soon_threadsafe(stop_event.set)

    restore_signals = _install_signal_handlers(request_stop)
    try:
        with scheduler_process_lock():
            async with httpx.AsyncClient(timeout=15.0) as client:
                workflows = SchedulerWorkflows(client)
                scheduler = build_scheduler(workflows, source_config, app_settings)
                runtime_store = SchedulerRuntimeStore()
                instance_id = uuid.uuid4()

                def heartbeat() -> None:
                    runtime_store.heartbeat(instance_id, job_snapshot(scheduler))

                scheduler.add_job(
                    heartbeat,
                    "interval",
                    seconds=app_settings.scheduler_heartbeat_interval_seconds,
                    id="scheduler:heartbeat",
                    replace_existing=True,
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=app_settings.scheduler_misfire_grace_seconds,
                )
                scheduler.start(paused=True)
                runtime_started = False
                try:
                    runtime_store.start(instance_id, job_snapshot(scheduler))
                    runtime_started = True
                    scheduler.resume()
                    logger.info(
                        "scheduler.started",
                        extra={
                            "event": "scheduler.started",
                            "github_sources": len(source_config.enabled_github),
                            "jobs": len(scheduler.get_jobs()),
                            "timezone": app_settings.scheduler_timezone,
                        },
                    )
                    await stop_event.wait()
                finally:
                    scheduler.pause()
                    idle = await workflows.wait_until_idle(
                        app_settings.scheduler_shutdown_timeout_seconds
                    )
                    if not idle:
                        logger.warning(
                            "scheduler.shutdown_timeout",
                            extra={"event": "scheduler.shutdown_timeout"},
                        )
                    scheduler.shutdown(wait=False)
                    await asyncio.sleep(0)
                    if runtime_started:
                        runtime_store.stop(instance_id)
                    logger.info("scheduler.stopped", extra={"event": "scheduler.stopped"})
    finally:
        restore_signals()


@contextmanager
def scheduler_process_lock(
    session_factory: sessionmaker[Session] = SessionLocal,
) -> Iterator[None]:
    lock_key = int.from_bytes(
        hashlib.blake2b(b"sprintern:scheduler", digest_size=8).digest(),
        byteorder="big",
        signed=True,
    )
    with session_factory() as session:
        if session.get_bind().dialect.name != "postgresql":
            yield
            return
        acquired = bool(
            session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key})
        )
        if not acquired:
            raise RuntimeError("another scheduler process is already running")
        try:
            yield
        finally:
            session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})


def _install_signal_handlers(callback: Callable[[], None]) -> Callable[[], None]:
    previous: dict[signal.Signals, Any] = {}
    supported = [signal.SIGINT]
    if hasattr(signal, "SIGTERM"):
        supported.append(signal.SIGTERM)
    for signum in supported:
        previous[signum] = signal.getsignal(signum)
        signal.signal(signum, lambda _signum, _frame: callback())

    def restore() -> None:
        for signum, handler in previous.items():
            signal.signal(signum, handler)

    return restore
