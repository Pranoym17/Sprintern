import asyncio
import logging
import signal
from collections.abc import Callable
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from api.scheduler.config import SchedulerSourceConfig, load_source_config
from api.scheduler.workflows import SchedulerWorkflows
from api.settings import Settings, settings

logger = logging.getLogger(__name__)


def build_scheduler(
    workflows: SchedulerWorkflows,
    source_config: SchedulerSourceConfig,
    app_settings: Settings = settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=app_settings.scheduler_timezone)
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
    )
    return scheduler


async def run_scheduler(app_settings: Settings = settings) -> None:
    source_config = load_source_config(app_settings.scheduler_source_config)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        loop.call_soon_threadsafe(stop_event.set)

    restore_signals = _install_signal_handlers(request_stop)
    async with httpx.AsyncClient(timeout=15.0) as client:
        scheduler = build_scheduler(SchedulerWorkflows(client), source_config, app_settings)
        scheduler.start()
        logger.info(
            "scheduler started github_sources=%d jobs=%d timezone=%s",
            len(source_config.enabled_github),
            len(scheduler.get_jobs()),
            app_settings.scheduler_timezone,
        )
        try:
            await stop_event.wait()
        finally:
            scheduler.shutdown(wait=True)
            restore_signals()
            logger.info("scheduler stopped")


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
