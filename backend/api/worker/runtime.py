import asyncio
import logging
import signal
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx

from api.database import SessionLocal
from api.ingestion.factory import build_adapter
from api.ingestion.service import IngestionService
from api.jobs import BackgroundJobQueue
from api.matching import ProfileRefresh, matching_service
from api.models import BackgroundJob, JobSourceName
from api.notifications.planning import notification_planner
from api.notifications.runtime import build_dispatcher
from api.retention import job_retention_service
from api.schemas import IngestionRunRequest
from api.settings import Settings, settings

logger = logging.getLogger(__name__)


class BackgroundJobHandler:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def handle(self, job: BackgroundJob) -> None:
        if job.job_type == "ingestion.github":
            request = IngestionRunRequest(source=JobSourceName.GITHUB_REPO, **job.payload)
            await IngestionService(SessionLocal).run(build_adapter(request, self.client))
            return
        if job.job_type in {"matching.all", "matching.jobs", "matching.profile"}:
            with SessionLocal.begin() as session:
                if job.job_type == "matching.all":
                    matching_service.match_all(session)
                elif job.job_type == "matching.jobs":
                    fingerprints = job.payload.get("fingerprints", [])
                    if not isinstance(fingerprints, list) or not all(
                        isinstance(item, str) for item in fingerprints
                    ):
                        raise ValueError("matching.jobs requires a fingerprint list")
                    matching_service.match_fingerprints(session, fingerprints)
                else:
                    profile_value = job.payload.get("profile_id")
                    if not isinstance(profile_value, str):
                        raise ValueError("matching.profile requires a profile_id")
                    try:
                        profile_id = uuid.UUID(profile_value)
                    except ValueError as exc:
                        raise ValueError("matching.profile has an invalid profile_id") from exc
                    seen_since_value = job.payload.get("seen_since")
                    if seen_since_value is not None and not isinstance(seen_since_value, str):
                        raise ValueError("matching.profile has an invalid seen_since")
                    try:
                        seen_since = (
                            datetime.fromisoformat(seen_since_value)
                            if seen_since_value is not None
                            else None
                        )
                    except ValueError as exc:
                        raise ValueError("matching.profile has an invalid seen_since") from exc
                    matching_service.match_profile(session, profile_id, seen_since=seen_since)
                BackgroundJobQueue.enqueue(
                    session,
                    job_type="notifications.dispatch",
                    idempotency_key=f"notifications:matching:{job.id}",
                    correlation_id=job.correlation_id,
                )
            return
        if job.job_type == "notifications.dispatch":
            with SessionLocal.begin() as session:
                notification_planner.plan_events(session)
            await build_dispatcher(self.client, SessionLocal).dispatch_due(limit=100)
            return
        if job.job_type == "retention.purge_expired_jobs":
            with SessionLocal.begin() as session:
                job_retention_service.purge_expired_jobs(
                    session, retention_days=settings.job_retention_days
                )
                job_retention_service.purge_completed_background_jobs(
                    session, retention_days=settings.background_job_retention_days
                )
            return
        raise ValueError(f"unsupported background job type: {job.job_type}")

    async def handle_profile_refresh(self, refresh: ProfileRefresh) -> None:
        """Finish a user-owned rematch after the API has already responded."""
        with SessionLocal.begin() as session:
            matching_service.match_profile(
                session,
                refresh.profile_id,
                seen_since=refresh.seen_since,
            )
            BackgroundJobQueue.enqueue(
                session,
                job_type="notifications.dispatch",
                idempotency_key=(
                    f"notifications:profile-refresh:{refresh.profile_id}:{refresh.requested_at.isoformat()}"
                ),
                correlation_id=f"matching:profile:{refresh.profile_id}",
            )


async def run_worker(app_settings: Settings = settings) -> None:
    stop_event = asyncio.Event()
    restore_signals = _install_signal_handlers(stop_event.set)
    owner = f"worker-{uuid.uuid4().hex}"
    queue = BackgroundJobQueue(SessionLocal)
    logger.info("worker.started", extra={"event": "worker.started", "worker_id": owner})
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            handler = BackgroundJobHandler(client)
            while not stop_event.is_set():
                try:
                    refresh = matching_service.claim_profile_refresh(
                        SessionLocal, app_settings.worker_lease_seconds
                    )
                except Exception as exc:
                    logger.exception(
                        "worker.profile_refresh_claim_failed",
                        extra={
                            "event": "worker.profile_refresh_claim_failed",
                            "worker_id": owner,
                            "exception_class": type(exc).__name__,
                        },
                    )
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(), timeout=app_settings.worker_claim_retry_seconds
                        )
                    except TimeoutError:
                        pass
                    continue
                if refresh is not None:
                    refresh_context: dict[str, Any] = {
                        "event": "worker.profile_refresh",
                        "profile_id": str(refresh.profile_id),
                    }
                    try:
                        await handler.handle_profile_refresh(refresh)
                        matching_service.complete_profile_refresh(SessionLocal, refresh)
                        logger.info("worker.profile_refresh.succeeded", extra=refresh_context)
                    except Exception as exc:
                        # Leave the lease in place. It becomes reclaimable after
                        # the normal worker lease, avoiding a tight retry loop.
                        logger.exception(
                            "worker.profile_refresh.failed",
                            extra={**refresh_context, "exception_class": type(exc).__name__},
                        )
                    continue
                try:
                    job = queue.claim(owner, app_settings.worker_lease_seconds)
                except Exception as exc:
                    # A transient database timeout must not terminate the process.
                    # The durable row remains queued (or lease-reclaimable), so a
                    # short pause lets Postgres recover without losing work.
                    logger.exception(
                        "worker.claim_failed",
                        extra={
                            "event": "worker.claim_failed",
                            "worker_id": owner,
                            "exception_class": type(exc).__name__,
                        },
                    )
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(), timeout=app_settings.worker_claim_retry_seconds
                        )
                    except TimeoutError:
                        pass
                    continue
                if job is None:
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(), timeout=app_settings.worker_poll_interval_seconds
                        )
                    except TimeoutError:
                        pass
                    continue
                context: dict[str, Any] = {
                    "event": "worker.job",
                    "job_id": str(job.id),
                    "job_type": job.job_type,
                    "correlation_id": job.correlation_id,
                    "attempt": job.attempts,
                }
                try:
                    await handler.handle(job)
                    queue.succeed(job.id, owner)
                    logger.info("worker.job.succeeded", extra=context)
                except Exception as exc:
                    queue.fail(job.id, owner, exc)
                    logger.exception(
                        "worker.job.failed",
                        extra={**context, "exception_class": type(exc).__name__},
                    )
    finally:
        restore_signals()
        logger.info("worker.stopped", extra={"event": "worker.stopped", "worker_id": owner})


def _install_signal_handlers(callback: Callable[[], None]) -> Callable[[], None]:
    loop = asyncio.get_running_loop()
    registered: list[signal.Signals] = []
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, callback)
            registered.append(signum)
        except (NotImplementedError, RuntimeError):
            continue

    def restore() -> None:
        for signum in registered:
            loop.remove_signal_handler(signum)

    return restore
