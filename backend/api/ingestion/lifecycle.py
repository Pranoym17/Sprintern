from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from api.models import Job, JobChangeEvent, JobSource, JobSourceName, JobStatus


@dataclass(frozen=True)
class LifecycleResult:
    stale_jobs: int = 0
    expired_jobs: int = 0
    suspicious_empty_snapshot: bool = False


class JobLifecycleService:
    def __init__(self, *, stale_after_misses: int = 2, expire_after_misses: int = 3) -> None:
        if stale_after_misses < 1 or expire_after_misses <= stale_after_misses:
            raise ValueError("expiry threshold must be greater than stale threshold")
        self.stale_after_misses = stale_after_misses
        self.expire_after_misses = expire_after_misses

    def apply_complete_snapshot(
        self,
        session: Session,
        source: JobSourceName,
        source_key: str,
        seen_external_ids: set[str],
        observed_at: datetime,
    ) -> LifecycleResult:
        tracked = list(
            session.scalars(
                select(JobSource).where(
                    JobSource.source == source,
                    JobSource.source_key == source_key,
                    or_(JobSource.active.is_(True), JobSource.missing_snapshot_count > 0),
                )
            )
        )
        if not seen_external_ids and any(item.active for item in tracked):
            return LifecycleResult(suspicious_empty_snapshot=True)

        affected_job_ids = set()
        for source_record in tracked:
            if source_record.external_id in seen_external_ids:
                continue
            source_record.missing_snapshot_count += 1
            source_record.missing_since = source_record.missing_since or observed_at
            if source_record.missing_snapshot_count >= self.stale_after_misses:
                source_record.active = False
            affected_job_ids.add(source_record.job_id)

        stale = 0
        expired = 0
        for job_id in affected_job_ids:
            job = session.scalar(
                select(Job).options(selectinload(Job.sources)).where(Job.id == job_id)
            )
            if job is None or any(item.active for item in job.sources):
                continue
            if all(item.missing_snapshot_count >= self.expire_after_misses for item in job.sources):
                if job.status != JobStatus.EXPIRED:
                    expired += 1
                    session.add(JobChangeEvent(job_id=job.id, event_type="expired", changes={}))
                job.status = JobStatus.EXPIRED
                job.expired_at = observed_at
            else:
                if job.status != JobStatus.STALE:
                    stale += 1
                    session.add(JobChangeEvent(job_id=job.id, event_type="stale", changes={}))
                job.status = JobStatus.STALE
        return LifecycleResult(stale_jobs=stale, expired_jobs=expired)
