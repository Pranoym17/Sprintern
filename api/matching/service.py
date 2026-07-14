import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.matching.classifier import classify_internship
from api.matching.matcher import MATCHER_VERSION, match_filter
from api.models import InternshipStatus, Job, JobFilter, JobMatch, JobStatus, MatchStatus


class MatchingService:
    def match_all(self, session: Session) -> int:
        jobs = list(session.scalars(select(Job).where(Job.status == JobStatus.ACTIVE)))
        filters = list(session.scalars(select(JobFilter).where(JobFilter.active.is_(True))))
        return sum(self._match_job(session, job, filters) for job in jobs)

    def match_profile(self, session: Session, profile_id: uuid.UUID) -> int:
        jobs = list(session.scalars(select(Job).where(Job.status == JobStatus.ACTIVE)))
        filters = list(
            session.scalars(
                select(JobFilter).where(
                    JobFilter.profile_id == profile_id, JobFilter.active.is_(True)
                )
            )
        )
        return sum(self._match_job(session, job, filters, profile_id) for job in jobs)

    def _match_job(
        self,
        session: Session,
        job: Job,
        filters: list[JobFilter],
        only_profile_id: uuid.UUID | None = None,
    ) -> int:
        job.internship_status = classify_internship(job.title, job.description)
        job.matcher_version = MATCHER_VERSION
        matched_by_profile: defaultdict[uuid.UUID, list[dict[str, object]]] = defaultdict(list)
        if job.internship_status == InternshipStatus.CONFIRMED:
            for job_filter in filters:
                result = match_filter(job, job_filter)
                if result:
                    matched_by_profile[job_filter.profile_id].append(result.reasons)

        statement = select(JobMatch).where(JobMatch.job_id == job.id)
        if only_profile_id:
            statement = statement.where(JobMatch.profile_id == only_profile_id)
        existing = {match.profile_id: match for match in session.scalars(statement)}
        created = 0
        for profile_id, reasons in matched_by_profile.items():
            match = existing.pop(profile_id, None)
            if match:
                match.reasons = reasons
            else:
                session.add(JobMatch(profile_id=profile_id, job_id=job.id, reasons=reasons))
                created += 1
        for unmatched in existing.values():
            if unmatched.status == MatchStatus.MATCHED:
                session.delete(unmatched)
        return created


matching_service = MatchingService()
