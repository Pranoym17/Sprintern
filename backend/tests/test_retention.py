import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import Job, JobMatch, JobStatus, Profile
from api.retention import JobRetentionService


def expired_job(*, fingerprint: str, expired_at: datetime) -> Job:
    return Job(
        company="Expired Co",
        normalized_company="expired co",
        title="Expired Internship",
        normalized_title="expired internship",
        canonical_fingerprint=fingerprint,
        status=JobStatus.EXPIRED,
        first_seen_at=expired_at - timedelta(days=5),
        last_seen_at=expired_at,
        expired_at=expired_at,
    )


def test_retention_purges_only_unretained_expired_source_jobs(db_session: Session) -> None:
    old = datetime.now(UTC) - timedelta(days=181)
    disposable = expired_job(fingerprint="d" * 64, expired_at=old)
    retained = expired_job(fingerprint="r" * 64, expired_at=old)
    recent = expired_job(fingerprint="n" * 64, expired_at=datetime.now(UTC) - timedelta(days=3))
    profile = Profile(id=uuid.uuid4(), email="retained@example.com")
    profile.matches.append(JobMatch(job=retained, reasons=[]))
    db_session.add_all([disposable, profile, recent])
    db_session.flush()

    deleted = JobRetentionService().purge_expired_jobs(db_session, retention_days=180)
    db_session.flush()

    remaining = set(db_session.scalars(select(Job.id)))
    assert deleted == 1
    assert disposable.id not in remaining
    assert retained.id in remaining
    assert recent.id in remaining
