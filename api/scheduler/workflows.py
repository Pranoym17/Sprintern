import asyncio
import logging
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import TypeVar

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from api.database import SessionLocal
from api.ingestion.factory import build_adapter
from api.ingestion.service import IngestionService
from api.models import JobSourceName, SourceState
from api.notifications.runtime import build_dispatcher
from api.scheduler.config import GitHubSourceConfig
from api.schemas import IngestionRunRequest

logger = logging.getLogger(__name__)
Result = TypeVar("Result")


class SchedulerWorkflows:
    def __init__(
        self,
        client: httpx.AsyncClient,
        session_factory: sessionmaker[Session] = SessionLocal,
    ) -> None:
        self.client = client
        self.session_factory = session_factory
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
                    "scheduler ingestion skipped source=%s reason=backoff until=%s",
                    source.source_key,
                    state.backoff_until.isoformat(),
                )
                return

        started = datetime.now(UTC)
        try:
            request = IngestionRunRequest(
                source=JobSourceName.GITHUB_REPO,
                owner=source.owner,
                repository=source.repository,
                path=source.path,
                branch=source.branch,
                term=source.term,
            )
            run = await IngestionService(self.session_factory).run(
                build_adapter(request, self.client)
            )
            elapsed = (datetime.now(UTC) - started).total_seconds()
            logger.info(
                "scheduler ingestion completed source=%s status=%s fetched=%d accepted=%d "
                "created=%d updated=%d rejected=%d duplicates=%d duration_seconds=%.3f",
                source.source_key,
                run.status.value,
                run.fetched_count,
                run.accepted_count,
                run.created_count,
                run.updated_count,
                run.rejected_count,
                run.duplicate_count,
                elapsed,
            )
        except Exception as exc:
            logger.error(
                "scheduler ingestion failed source=%s error_type=%s",
                source.source_key,
                type(exc).__name__,
            )

    async def dispatch_notifications(self) -> None:
        await self._tracked(self._dispatch_notifications())

    async def _dispatch_notifications(self) -> None:
        started = datetime.now(UTC)
        try:
            sent = await build_dispatcher(self.client, self.session_factory).dispatch_due(limit=100)
            elapsed = (datetime.now(UTC) - started).total_seconds()
            logger.info(
                "scheduler notification dispatch completed sent=%d duration_seconds=%.3f",
                sent,
                elapsed,
            )
        except Exception as exc:
            logger.error(
                "scheduler notification dispatch failed error_type=%s", type(exc).__name__
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
