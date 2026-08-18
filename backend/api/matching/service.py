import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.jobs import BackgroundJobQueue
from api.matching.classifier import classify_internship
from api.matching.matcher import MATCHER_VERSION, match_filter
from api.models import (
    CompanyWatchlist,
    InternshipStatus,
    Job,
    JobFilter,
    JobMatch,
    JobStatus,
    MatchStatus,
    Profile,
)
from api.notifications.planning import notification_planner


class MatchingService:
    @staticmethod
    def enqueue_profile_refresh(
        session: Session,
        profile_id: uuid.UUID,
        *,
        seen_since: datetime | None = None,
    ) -> None:
        """Queue user-triggered rematching outside the filter write transaction.

        Matching a profile can touch many jobs and deliveries. Keeping that work
        out of create/update/delete requests prevents a filter row from being
        locked long enough for a second user action to time out.
        """
        payload: dict[str, str] = {"profile_id": str(profile_id)}
        if seen_since is not None:
            payload["seen_since"] = seen_since.isoformat()
        BackgroundJobQueue.enqueue(
            session,
            job_type="matching.profile",
            idempotency_key=f"matching:profile:{profile_id}:{uuid.uuid4()}",
            payload=payload,
            correlation_id=f"matching:profile:{profile_id}",
        )

    def match_all(self, session: Session) -> int:
        jobs = list(session.scalars(select(Job).where(Job.status == JobStatus.ACTIVE)))
        filters = list(
            session.scalars(
                select(JobFilter)
                .options(selectinload(JobFilter.exclusions))
                .where(JobFilter.active.is_(True))
            )
        )
        watchlists = list(
            session.scalars(select(CompanyWatchlist).where(CompanyWatchlist.active.is_(True)))
        )
        return sum(self._match_job(session, job, filters, watchlists=watchlists) for job in jobs)

    def match_fingerprints(self, session: Session, fingerprints: list[str]) -> int:
        """Match only postings whose user-visible matching fields changed."""
        if not fingerprints:
            return 0
        jobs = list(
            session.scalars(
                select(Job).where(
                    Job.status == JobStatus.ACTIVE,
                    Job.canonical_fingerprint.in_(set(fingerprints)),
                )
            )
        )
        filters = list(
            session.scalars(
                select(JobFilter)
                .options(selectinload(JobFilter.exclusions))
                .where(JobFilter.active.is_(True))
            )
        )
        watchlists = list(
            session.scalars(select(CompanyWatchlist).where(CompanyWatchlist.active.is_(True)))
        )
        return sum(self._match_job(session, job, filters, watchlists=watchlists) for job in jobs)

    def match_profile(
        self,
        session: Session,
        profile_id: uuid.UUID,
        *,
        seen_since: datetime | None = None,
    ) -> int:
        jobs_statement = select(Job).where(Job.status == JobStatus.ACTIVE)
        if seen_since is not None:
            jobs_statement = jobs_statement.where(Job.first_seen_at >= seen_since)
        jobs = list(session.scalars(jobs_statement))
        filters = list(
            session.scalars(
                select(JobFilter)
                .options(selectinload(JobFilter.exclusions))
                .where(JobFilter.profile_id == profile_id, JobFilter.active.is_(True))
            )
        )
        watchlists = list(
            session.scalars(
                select(CompanyWatchlist).where(
                    CompanyWatchlist.profile_id == profile_id,
                    CompanyWatchlist.active.is_(True),
                )
            )
        )
        return sum(self._match_job(session, job, filters, profile_id, watchlists) for job in jobs)

    def _match_job(
        self,
        session: Session,
        job: Job,
        filters: list[JobFilter],
        only_profile_id: uuid.UUID | None = None,
        watchlists: list[CompanyWatchlist] | None = None,
    ) -> int:
        # A user updating a filter runs through the restricted API role and
        # must not mutate a shared job row. Classification is persisted by the
        # worker's global matching pass; per-profile backfill only manages that
        # user's matches and notification plans.
        internship_status = classify_internship(job.title, job.description)
        if only_profile_id is None:
            job.internship_status = internship_status
            job.matcher_version = MATCHER_VERSION
        matched_by_profile: defaultdict[uuid.UUID, list[dict[str, object]]] = defaultdict(list)
        if internship_status == InternshipStatus.CONFIRMED:
            for job_filter in filters:
                result = match_filter(job, job_filter)
                if result:
                    matched_by_profile[job_filter.profile_id].append(result.reasons)
            for watchlist in watchlists or []:
                term_matches = not watchlist.terms or job.term in watchlist.terms
                location = (job.normalized_location or "").casefold()
                location_matches = not watchlist.locations or any(
                    item.casefold() in location for item in watchlist.locations
                )
                if (
                    job.normalized_company == watchlist.normalized_company
                    and term_matches
                    and location_matches
                ):
                    matched_by_profile[watchlist.profile_id].append(
                        {
                            "watchlist_id": str(watchlist.id),
                            "watchlist_company": watchlist.company,
                            "matcher_version": MATCHER_VERSION,
                            "dimensions": {"company": watchlist.company},
                            "positive": [{"kind": "company", "value": watchlist.company}],
                            "negative": [],
                        }
                    )

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
                match = JobMatch(profile_id=profile_id, job_id=job.id, reasons=reasons)
                session.add(match)
                created += 1
            profile = session.get(Profile, profile_id)
            if profile:
                notification_planner.plan_match(session, match, profile)
        for unmatched in existing.values():
            if unmatched.status == MatchStatus.MATCHED:
                session.delete(unmatched)
        return created


matching_service = MatchingService()
