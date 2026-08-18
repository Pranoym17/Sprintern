import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

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


@dataclass(frozen=True)
class ProfileRefresh:
    profile_id: uuid.UUID
    requested_at: datetime
    locked_at: datetime
    seen_since: datetime | None


class MatchingService:
    @staticmethod
    def enqueue_profile_refresh(
        session: Session,
        profile_id: uuid.UUID,
        *,
        seen_since: datetime | None = None,
    ) -> None:
        """Request user-triggered rematching outside the filter write transaction.

        Matching a profile can touch many jobs and deliveries. Keeping that work
        out of create/update/delete requests prevents a filter row from being
        locked long enough for a second user action to time out. The marker is
        stored on the owned profile instead of the global queue so the API role
        never needs permission to inspect or mutate worker-owned records.
        """
        profile = session.get(Profile, profile_id)
        if profile is None:
            return
        if profile.match_refresh_requested_at is None:
            profile.match_refresh_seen_since = seen_since
        elif seen_since is None:
            # A deletion or broad filter edit needs a full pass to remove any
            # matches that are no longer justified by the user's rules.
            profile.match_refresh_seen_since = None
        elif profile.match_refresh_seen_since is not None:
            profile.match_refresh_seen_since = min(profile.match_refresh_seen_since, seen_since)
        profile.match_refresh_requested_at = datetime.now(UTC)

    @staticmethod
    def claim_profile_refresh(
        session_factory: sessionmaker[Session], lease_seconds: int
    ) -> ProfileRefresh | None:
        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=lease_seconds)
        with session_factory.begin() as session:
            profile = session.scalar(
                select(Profile)
                .where(
                    Profile.match_refresh_requested_at.is_not(None),
                    or_(
                        Profile.match_refresh_locked_at.is_(None),
                        Profile.match_refresh_locked_at < stale_before,
                    ),
                )
                .order_by(Profile.match_refresh_requested_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if profile is None or profile.match_refresh_requested_at is None:
                return None
            profile.match_refresh_locked_at = now
            return ProfileRefresh(
                profile_id=profile.id,
                requested_at=profile.match_refresh_requested_at,
                locked_at=now,
                seen_since=profile.match_refresh_seen_since,
            )

    @staticmethod
    def complete_profile_refresh(
        session_factory: sessionmaker[Session], refresh: ProfileRefresh
    ) -> None:
        with session_factory.begin() as session:
            profile = session.get(Profile, refresh.profile_id)
            if profile is None or profile.match_refresh_locked_at != refresh.locked_at:
                return
            profile.match_refresh_locked_at = None
            if profile.match_refresh_requested_at == refresh.requested_at:
                profile.match_refresh_requested_at = None
                profile.match_refresh_seen_since = None

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
