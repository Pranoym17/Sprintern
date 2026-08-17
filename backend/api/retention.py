"""Retention for disposable source records without erasing user-owned history."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.orm import Session

from api.models import (
    Application,
    BackgroundJob,
    Job,
    JobInteraction,
    JobMatch,
    JobReport,
    JobStatus,
    ShareLink,
)


class JobRetentionService:
    def purge_expired_jobs(self, session: Session, *, retention_days: int) -> int:
        """Purge old source records only when no user has retained the job.

        Applications, bookmarks, hidden jobs, matches, reports, and share links
        are user data. Keeping any of them means the job is not merely raw source
        data and must survive the retention sweep.
        """
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        protected = or_(
            exists(select(Application.id).where(Application.job_id == Job.id)),
            exists(select(JobInteraction.id).where(JobInteraction.job_id == Job.id)),
            exists(select(JobMatch.id).where(JobMatch.job_id == Job.id)),
            exists(select(JobReport.id).where(JobReport.job_id == Job.id)),
            exists(select(ShareLink.id).where(ShareLink.job_id == Job.id)),
        )
        deleted = session.scalars(
            delete(Job)
            .where(
                Job.status == JobStatus.EXPIRED,
                Job.expired_at.is_not(None),
                Job.expired_at < cutoff,
                ~protected,
            )
            .returning(Job.id)
        )
        return len(list(deleted))

    def purge_completed_background_jobs(
        self,
        session: Session,
        *,
        retention_days: int,
        batch_size: int = 500,
    ) -> int:
        """Bound queue history without touching work that may still retry.

        Queue rows are operational diagnostics, not user data. Keeping a short
        window is enough for investigation and prevents completed history from
        slowing queue claims or adding unnecessary write amplification.
        """
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        identifiers = list(
            session.scalars(
                select(BackgroundJob.id)
                .where(
                    BackgroundJob.status.in_(("succeeded", "dead")),
                    BackgroundJob.finished_at.is_not(None),
                    BackgroundJob.finished_at < cutoff,
                )
                .order_by(BackgroundJob.finished_at)
                .limit(batch_size)
            )
        )
        if not identifiers:
            return 0
        session.execute(delete(BackgroundJob).where(BackgroundJob.id.in_(identifiers)))
        return len(identifiers)


job_retention_service = JobRetentionService()
