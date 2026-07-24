import asyncio
import hashlib
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker

from api.ingestion.contracts import SourceAdapter
from api.ingestion.lifecycle import JobLifecycleService
from api.ingestion.normalization import normalize_job
from api.ingestion.persistence import JobPersister, PersistenceOutcome
from api.matching import matching_service
from api.models import (
    IngestionRun,
    IngestionRunStatus,
    ParserAlert,
    PollCompleteness,
    SourceState,
)
from api.observability import redact_text


class IngestionService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        persister: JobPersister | None = None,
        lifecycle: JobLifecycleService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.persister = persister or JobPersister()
        self.lifecycle = lifecycle or JobLifecycleService()
        self._locks: defaultdict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)

    async def run(self, adapter: SourceAdapter) -> IngestionRun:
        lock = self._locks[(adapter.source.value, adapter.source_key)]
        if lock.locked():
            return self._record_skipped(adapter)
        async with lock:
            with self._distributed_lock(adapter) as acquired:
                if not acquired:
                    return self._record_skipped(adapter)
                return await self._run_locked(adapter)

    async def _run_locked(self, adapter: SourceAdapter) -> IngestionRun:
        state_id, run_id, cursor = self._record_start(adapter)
        try:
            batch = await adapter.fetch(cursor)
            seen_at = datetime.now(UTC)
            normalized = []
            seen_source_ids: set[str] = set()
            source_duplicates = 0
            rejected = batch.rejected_count
            errors = list(batch.rejection_errors)
            for raw in batch.records:
                try:
                    candidate = normalize_job(adapter.source, adapter.source_key, raw)
                    if candidate.external_id in seen_source_ids:
                        source_duplicates += 1
                        continue
                    seen_source_ids.add(candidate.external_id)
                    normalized.append(candidate)
                except (TypeError, ValueError) as exc:
                    rejected += 1
                    if len(errors) < 25:
                        errors.append(str(exc))

            with self.session_factory() as session:
                state = session.get_one(SourceState, state_id)
                run = session.get_one(IngestionRun, run_id)
                previous_accepted = session.scalar(
                    select(IngestionRun.accepted_count)
                    .where(
                        IngestionRun.source_state_id == state_id,
                        IngestionRun.id != run_id,
                        IngestionRun.status == IngestionRunStatus.SUCCEEDED,
                    )
                    .order_by(IngestionRun.started_at.desc())
                    .limit(1)
                )
                for alert in session.scalars(
                    select(ParserAlert).where(
                        ParserAlert.source_key == adapter.source_key,
                        ParserAlert.resolved_at.is_(None),
                    )
                ):
                    alert.resolved_at = seen_at
                fetched = len(batch.records) + batch.rejected_count
                issues: list[tuple[str, str]] = []
                if batch.next_cursor != cursor and not normalized:
                    issues.append(
                        ("accepted_zero", "Accepted rows fell to zero after the source changed")
                    )
                if fetched and rejected / fetched >= 0.5:
                    issues.append(
                        ("high_rejection_ratio", "At least half of fetched rows were rejected")
                    )
                if previous_accepted and len(normalized) > 0:
                    ratio = len(normalized) / previous_accepted
                    if ratio < 0.3 or ratio > 3.0:
                        issues.append(
                            ("abnormal_job_count", "Accepted job count changed abnormally")
                        )
                for category, message in issues:
                    self._upsert_parser_alert(session, adapter.source_key, category, message)
                outcomes = {outcome: 0 for outcome in PersistenceOutcome}
                outcomes[PersistenceOutcome.DUPLICATE] = source_duplicates
                for candidate in normalized:
                    outcomes[self.persister.persist(session, candidate, seen_at)] += 1
                if batch.completeness == PollCompleteness.COMPLETE:
                    lifecycle_result = self.lifecycle.apply_complete_snapshot(
                        session,
                        adapter.source,
                        adapter.source_key,
                        {candidate.external_id for candidate in normalized},
                        seen_at,
                    )
                    if lifecycle_result.suspicious_empty_snapshot:
                        errors.append("Empty snapshot ignored for lifecycle safety")
                matching_service.match_all(session)
                state.cursor = batch.next_cursor
                state.consecutive_failures = 0
                state.backoff_until = None
                state.last_succeeded_at = seen_at
                state.last_error = None
                run.status = IngestionRunStatus.SUCCEEDED
                run.completeness = batch.completeness
                run.finished_at = seen_at
                run.fetched_count = len(batch.records) + batch.rejected_count
                run.accepted_count = len(normalized)
                run.rejected_count = rejected
                run.created_count = outcomes[PersistenceOutcome.CREATED]
                run.updated_count = outcomes[PersistenceOutcome.UPDATED]
                run.duplicate_count = outcomes[PersistenceOutcome.DUPLICATE]
                run.error = "; ".join(errors) if errors else None
                session.commit()
                session.refresh(run)
                session.expunge(run)
                return run
        except Exception as exc:
            self._record_failure(state_id, run_id, exc)
            raise

    @contextmanager
    def _distributed_lock(self, adapter: SourceAdapter) -> Iterator[bool]:
        lock_name = f"{adapter.source.value}:{adapter.source_key}"
        lock_key = int.from_bytes(
            hashlib.blake2b(lock_name.encode(), digest_size=8).digest(),
            byteorder="big",
            signed=True,
        )
        with self.session_factory() as session:
            bind = session.get_bind()
            if bind.dialect.name != "postgresql" or isinstance(bind, Connection):
                yield True
                return
            acquired = bool(
                session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key})
            )
            try:
                yield acquired
            finally:
                if acquired:
                    session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})

    def _record_start(self, adapter: SourceAdapter) -> tuple[Any, Any, dict[str, Any]]:
        now = datetime.now(UTC)
        with self.session_factory() as session:
            state = session.scalar(
                select(SourceState).where(
                    SourceState.source == adapter.source,
                    SourceState.source_key == adapter.source_key,
                )
            )
            if state is None:
                state = SourceState(source=adapter.source, source_key=adapter.source_key)
                session.add(state)
                session.flush()
            state.last_started_at = now
            run = IngestionRun(
                source_state_id=state.id,
                status=IngestionRunStatus.RUNNING,
                started_at=now,
            )
            session.add(run)
            session.commit()
            return state.id, run.id, dict(state.cursor)

    def _record_skipped(self, adapter: SourceAdapter) -> IngestionRun:
        state_id, run_id, _cursor = self._record_start(adapter)
        with self.session_factory() as session:
            run = session.get_one(IngestionRun, run_id)
            run.status = IngestionRunStatus.SKIPPED
            run.finished_at = datetime.now(UTC)
            run.error = "A run for this source is already active"
            session.commit()
            session.refresh(run)
            session.expunge(run)
            return run

    def _record_failure(self, state_id: Any, run_id: Any, exc: Exception) -> None:
        now = datetime.now(UTC)
        message = redact_text(f"{type(exc).__name__}: {exc}")[:2000]
        with self.session_factory() as session:
            state = session.get_one(SourceState, state_id)
            run = session.get_one(IngestionRun, run_id)
            state.consecutive_failures += 1
            delay_seconds = min(60 * (2 ** (state.consecutive_failures - 1)), 3600)
            state.backoff_until = now + timedelta(seconds=delay_seconds)
            state.last_failed_at = now
            state.last_error = message
            lowered = message.casefold()
            if "no supported internship table schema" in lowered:
                self._upsert_parser_alert(
                    session,
                    state.source_key,
                    "table_disappeared",
                    "A previously supported internship table could not be found",
                )
            elif state.consecutive_failures >= 3:
                self._upsert_parser_alert(
                    session,
                    state.source_key,
                    "repeated_source_error",
                    "The source failed repeatedly and requires attention",
                )
            run.status = IngestionRunStatus.FAILED
            run.finished_at = now
            run.error = message
            session.commit()

    @staticmethod
    def _upsert_parser_alert(
        session: Session, source_key: str, category: str, message: str
    ) -> None:
        fingerprint = hashlib.sha256(f"{source_key}:{category}".encode()).hexdigest()
        alert = session.scalar(
            select(ParserAlert).where(
                ParserAlert.source_key == source_key,
                ParserAlert.fingerprint == fingerprint,
            )
        )
        if alert is None:
            session.add(
                ParserAlert(
                    source_key=source_key,
                    fingerprint=fingerprint,
                    message=message,
                )
            )
        else:
            alert.message = message
            alert.occurrences += 1
            alert.resolved_at = None
