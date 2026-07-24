from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from api.ingestion.normalization import NormalizedJob
from api.models import DeadlineSource, Job, JobChangeEvent, JobSource, JobStatus


class PersistenceOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    DUPLICATE = "duplicate"


class JobPersister:
    def __init__(self, repost_threshold_days: int = 30) -> None:
        self.repost_threshold = timedelta(days=repost_threshold_days)

    def persist(
        self, session: Session, candidate: NormalizedJob, seen_at: datetime
    ) -> PersistenceOutcome:
        source_record = session.scalar(
            select(JobSource)
            .options(joinedload(JobSource.job))
            .where(
                JobSource.source == candidate.source,
                JobSource.source_key == candidate.source_key,
                JobSource.external_id == candidate.external_id,
            )
            .order_by(JobSource.occurrence.desc())
            .limit(1)
        )
        if source_record:
            reposted = (
                source_record.job.status == JobStatus.EXPIRED
                and seen_at - source_record.last_seen_at >= self.repost_threshold
            )
            if not reposted:
                self._update_existing(session, source_record, candidate, seen_at)
                return PersistenceOutcome.UPDATED
            next_occurrence = source_record.occurrence + 1
        else:
            next_occurrence = 1

        cutoff = seen_at - self.repost_threshold
        compatible_term = (
            or_(Job.term == candidate.term, Job.term.is_(None))
            if candidate.term
            else Job.id.is_not(None)
        )
        canonical_job = session.scalar(
            select(Job)
            .where(
                or_(
                    Job.canonical_fingerprint == candidate.canonical_fingerprint,
                    (
                        (Job.normalized_company == candidate.normalized_company)
                        & (Job.normalized_title == candidate.normalized_title)
                        & (Job.normalized_location == candidate.normalized_location)
                        & compatible_term
                    ),
                ),
                Job.first_seen_at >= cutoff,
            )
            .order_by(Job.first_seen_at.desc())
            .limit(1)
        )
        if canonical_job:
            canonical_job.last_seen_at = seen_at
            if canonical_job.term is None and candidate.term:
                canonical_job.term = candidate.term
                canonical_job.canonical_fingerprint = candidate.canonical_fingerprint
            canonical_job.sources.append(
                self._source_record(candidate, seen_at, occurrence=next_occurrence)
            )
            return PersistenceOutcome.DUPLICATE

        job = Job(
            company=candidate.company,
            normalized_company=candidate.normalized_company,
            title=candidate.title,
            normalized_title=candidate.normalized_title,
            location=candidate.location,
            normalized_location=candidate.normalized_location,
            term=candidate.term,
            description=candidate.description,
            work_mode=candidate.work_mode,
            canonical_fingerprint=candidate.canonical_fingerprint,
            status=JobStatus.ACTIVE,
            posted_at=candidate.posted_at,
            deadline_at=candidate.deadline_at,
            deadline_source=DeadlineSource.SOURCE if candidate.deadline_at else None,
            title_incomplete=self._title_is_incomplete(candidate.title),
            latitude=candidate.latitude,
            longitude=candidate.longitude,
            first_seen_at=seen_at,
            last_seen_at=seen_at,
        )
        job.sources.append(self._source_record(candidate, seen_at, occurrence=next_occurrence))
        session.add(job)
        return PersistenceOutcome.CREATED

    @staticmethod
    def _source_record(
        candidate: NormalizedJob, seen_at: datetime, *, occurrence: int
    ) -> JobSource:
        return JobSource(
            source=candidate.source,
            source_key=candidate.source_key,
            external_id=candidate.external_id,
            occurrence=occurrence,
            source_url=candidate.source_url,
            apply_url=candidate.apply_url,
            raw_metadata=candidate.raw_metadata,
            first_seen_at=seen_at,
            last_seen_at=seen_at,
        )

    @staticmethod
    def _title_is_incomplete(title: str) -> bool:
        stripped = title.strip()
        return (
            stripped.endswith(("...", "…", "-", "/"))
            or stripped.count("(") > stripped.count(")")
            or stripped.count("[") > stripped.count("]")
        )

    def _update_existing(
        self,
        session: Session,
        source_record: JobSource,
        candidate: NormalizedJob,
        seen_at: datetime,
    ) -> None:
        job = source_record.job
        tracked = {
            "company": (job.company, candidate.company),
            "title": (job.title, candidate.title),
            "location": (job.location, candidate.location),
            "term": (job.term, candidate.term),
            "apply_url": (source_record.apply_url, candidate.apply_url),
            "deadline_at": (
                job.deadline_at.isoformat() if job.deadline_at else None,
                candidate.deadline_at.isoformat() if candidate.deadline_at else None,
            ),
        }
        changes = {
            field: {"from": before, "to": after}
            for field, (before, after) in tracked.items()
            if before != after
        }
        was_inactive = job.status != JobStatus.ACTIVE or not source_record.active
        if changes:
            session.add(JobChangeEvent(job_id=job.id, event_type="updated", changes=changes))
        if was_inactive:
            session.add(JobChangeEvent(job_id=job.id, event_type="reopened", changes={}))
            job.reopened_at = seen_at
        source_record.source_url = candidate.source_url
        source_record.apply_url = candidate.apply_url
        source_record.raw_metadata = candidate.raw_metadata
        source_record.last_seen_at = seen_at
        source_record.missing_snapshot_count = 0
        source_record.missing_since = None
        source_record.active = True
        job.company = candidate.company
        job.normalized_company = candidate.normalized_company
        job.title = candidate.title
        job.normalized_title = candidate.normalized_title
        job.location = candidate.location
        job.normalized_location = candidate.normalized_location
        job.term = candidate.term
        job.description = candidate.description
        job.work_mode = candidate.work_mode
        job.posted_at = candidate.posted_at
        if candidate.deadline_at:
            job.deadline_at = candidate.deadline_at
            job.deadline_source = DeadlineSource.SOURCE
        job.title_incomplete = self._title_is_incomplete(candidate.title)
        job.latitude = candidate.latitude
        job.longitude = candidate.longitude
        job.last_seen_at = seen_at
        job.status = JobStatus.ACTIVE
        job.expired_at = None
