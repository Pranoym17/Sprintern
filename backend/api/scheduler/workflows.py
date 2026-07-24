import asyncio
import logging
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import TypeVar

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.database import SessionLocal
from api.jobs import BackgroundJobQueue
from api.models import JobSourceName, SourceState
from api.scheduler.config import GitHubSourceConfig
from api.settings import settings

logger = logging.getLogger(__name__)
Result = TypeVar("Result")


class SchedulerWorkflows:
    def __init__(
        self,
        _client: httpx.AsyncClient | None = None,
        session_factory: sessionmaker[Session] = SessionLocal,
    ) -> None:
        self.session_factory = session_factory
        self.queue = BackgroundJobQueue(session_factory)
        self._active_tasks = 0
        self._idle = asyncio.Event()
        self._idle.set()

    async def ingest_github(self, source: GitHubSourceConfig) -> None:
        await self._tracked(self._ingest_github(source))

    async def _ingest_github(self, source: GitHubSourceConfig) -> None:
        now = datetime.now(UTC)
        with self.session_factory() as session:
            state = session.scalar(
                select(SourceState).where(
                    SourceState.source == JobSourceName.GITHUB_REPO,
                    SourceState.source_key == source.source_key,
                )
            )
            if state and state.backoff_until and state.backoff_until > now:
                logger.info(
                    "scheduler.ingestion.skipped",
                    extra={
                        "event": "scheduler.ingestion.skipped",
                        "source": source.source_key,
                        "reason": "backoff",
                        "backoff_until": state.backoff_until.isoformat(),
                    },
                )
                return

        try:
            bucket = int(now.timestamp()) // max(source.poll_minutes * 60, 1)
            with self.session_factory.begin() as session:
                self.queue.enqueue(
                    session,
                    job_type="ingestion.github",
                    idempotency_key=f"ingestion:{source.source_key}:{bucket}",
                    payload={
                        "owner": source.owner,
                        "repository": source.repository,
                        "path": source.path,
                        "branch": source.branch,
                        "term": source.term,
                    },
                    correlation_id=f"{source.source_key}:{bucket}",
                )
            logger.info(
                "scheduler.ingestion.enqueued",
                extra={
                    "event": "scheduler.ingestion.enqueued",
                    "source": source.source_key,
                },
            )
        except Exception as exc:
            logger.error(
                "scheduler.ingestion.failed",
                extra={
                    "event": "scheduler.ingestion.failed",
                    "source": source.source_key,
                    "exception_class": type(exc).__name__,
                },
            )

    async def dispatch_notifications(self) -> None:
        await self._tracked(self._dispatch_notifications())

    async def _dispatch_notifications(self) -> None:
        try:
            now = datetime.now(UTC)
            interval = settings.scheduler_notification_interval_seconds
            bucket = int(now.timestamp()) // interval
            with self.session_factory.begin() as session:
                self.queue.enqueue(
                    session,
                    job_type="notifications.dispatch",
                    idempotency_key=f"notifications:dispatch:{bucket}",
                    correlation_id=f"notifications:{bucket}",
                )
            logger.info(
                "scheduler.notifications.enqueued",
                extra={
                    "event": "scheduler.notifications.enqueued",
                },
            )
        except Exception as exc:
            logger.error(
                "scheduler.notifications.failed",
                extra={
                    "event": "scheduler.notifications.failed",
                    "exception_class": type(exc).__name__,
                },
            )

    async def wait_until_idle(self, timeout_seconds: int) -> bool:
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=timeout_seconds)
            return True
        except TimeoutError:
            return False

    async def _tracked(self, operation: Awaitable[Result]) -> Result:
        self._active_tasks += 1
        self._idle.clear()
        try:
            return await operation
        finally:
            self._active_tasks -= 1
            if self._active_tasks == 0:
                self._idle.set()
