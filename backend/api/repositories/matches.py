import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.models import (
    CompanyWatchlist,
    Job,
    JobInteraction,
    JobMatch,
    JobStatus,
    MatchStatus,
    WorkMode,
)

MatchSort = Literal["newest", "company", "relevance", "deadline"]
Collection = Literal[
    "toronto",
    "remote",
    "canadian",
    "new-week",
    "closing-soon",
    "reopened",
    "followed-companies",
    "strongest",
    "recently-viewed",
]


def get_match(session: Session, profile_id: uuid.UUID, match_id: uuid.UUID) -> JobMatch | None:
    statement = (
        select(JobMatch)
        .options(
            selectinload(JobMatch.job).selectinload(Job.sources),
            selectinload(JobMatch.deliveries),
        )
        .where(JobMatch.id == match_id, JobMatch.profile_id == profile_id)
    )
    return session.scalar(statement)


def list_matches(
    session: Session,
    profile_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
    status: MatchStatus | None = None,
    query: str = "",
    sort: MatchSort = "newest",
    page: int = 1,
    collection: Collection | None = None,
    include_hidden: bool = False,
) -> list[JobMatch]:
    search = query.strip()
    vector = func.to_tsvector(
        "english",
        func.concat_ws(" ", Job.title, Job.company, func.coalesce(Job.location, "")),
    )
    ts_query = func.websearch_to_tsquery("english", search)
    typo_score = func.greatest(
        func.similarity(Job.normalized_title, search.casefold()),
        func.similarity(Job.normalized_company, search.casefold()),
        func.similarity(func.coalesce(Job.normalized_location, ""), search.casefold()),
        func.word_similarity(
            search.casefold(),
            func.concat_ws(
                " ",
                Job.normalized_title,
                Job.normalized_company,
                func.coalesce(Job.normalized_location, ""),
            ),
        ),
    )
    statement = (
        select(JobMatch)
        .options(
            selectinload(JobMatch.job).selectinload(Job.sources),
            selectinload(JobMatch.deliveries),
        )
        .join(Job, Job.id == JobMatch.job_id)
        .where(
            JobMatch.profile_id == profile_id,
            or_(Job.status == JobStatus.ACTIVE, JobMatch.status == MatchStatus.APPLIED),
        )
    )
    if not include_hidden:
        statement = statement.where(
            ~exists().where(
                JobInteraction.profile_id == profile_id,
                JobInteraction.job_id == Job.id,
                JobInteraction.hidden_at.is_not(None),
            )
        )
    if status is not None:
        statement = statement.where(JobMatch.status == status)
    if search:
        statement = statement.where(or_(vector.op("@@")(ts_query), typo_score >= 0.2))
    if collection == "toronto":
        statement = statement.where(Job.normalized_location.contains("toronto"))
    elif collection == "remote":
        statement = statement.where(Job.work_mode == WorkMode.REMOTE)
    elif collection == "canadian":
        statement = statement.where(
            or_(
                Job.normalized_location.contains("canada"),
                Job.normalized_location.contains(" ontario"),
            )
        )
    elif collection == "new-week":
        statement = statement.where(Job.first_seen_at >= datetime.now(UTC) - timedelta(days=7))
    elif collection == "closing-soon":
        statement = statement.where(
            Job.deadline_at >= datetime.now(UTC),
            Job.deadline_at <= datetime.now(UTC) + timedelta(days=7),
        )
    elif collection == "reopened":
        statement = statement.where(Job.reopened_at.is_not(None))
    elif collection == "followed-companies":
        statement = statement.where(
            exists().where(
                CompanyWatchlist.profile_id == profile_id,
                CompanyWatchlist.active.is_(True),
                CompanyWatchlist.normalized_company == Job.normalized_company,
            )
        )
    elif collection == "recently-viewed":
        statement = statement.where(
            exists().where(
                JobInteraction.profile_id == profile_id,
                JobInteraction.job_id == Job.id,
                JobInteraction.last_viewed_at.is_not(None),
            )
        )

    ordering: tuple[Any, ...]
    if collection == "recently-viewed":
        interaction_view = (
            select(JobInteraction.last_viewed_at)
            .where(
                JobInteraction.profile_id == profile_id,
                JobInteraction.job_id == Job.id,
            )
            .scalar_subquery()
        )
        ordering = (interaction_view.desc().nullslast(), Job.id.desc())
    elif sort == "company":
        ordering = (Job.normalized_company.asc(), Job.id.desc())
    elif sort == "deadline":
        ordering = (Job.deadline_at.asc().nullslast(), Job.id.desc())
    elif sort == "relevance" or collection == "strongest":
        relevance = func.ts_rank_cd(vector, ts_query) + typo_score
        if not search:
            relevance = func.jsonb_array_length(JobMatch.reasons)
        ordering = (relevance.desc(), JobMatch.created_at.desc(), Job.id.desc())
    else:
        ordering = (
            func.coalesce(Job.posted_at, Job.first_seen_at).desc(),
            JobMatch.created_at.desc(),
            JobMatch.id.desc(),
        )

    if cursor and page == 1 and not search and sort == "newest" and collection is None:
        created_at, item_id = cursor
        statement = statement.where(
            or_(
                JobMatch.created_at < created_at,
                and_(JobMatch.created_at == created_at, JobMatch.id < item_id),
            )
        )
    statement = statement.order_by(*ordering).offset((page - 1) * limit).limit(limit + 1)
    return list(session.scalars(statement))


def match_status_counts(session: Session, profile_id: uuid.UUID) -> tuple[int, int, int, int]:
    visible = or_(Job.status == JobStatus.ACTIVE, JobMatch.status == MatchStatus.APPLIED)
    statement = (
        select(
            func.count(JobMatch.id),
            func.count(JobMatch.id).filter(JobMatch.status == MatchStatus.MATCHED),
            func.count(JobMatch.id).filter(JobMatch.status == MatchStatus.APPLIED),
            func.count(JobMatch.id).filter(JobMatch.status == MatchStatus.DISMISSED),
        )
        .join(Job, Job.id == JobMatch.job_id)
        .where(JobMatch.profile_id == profile_id, visible)
    )
    all_count, matched, applied, dismissed = session.execute(statement).one()
    return int(all_count), int(matched), int(applied), int(dismissed)


def analytics_summary(session: Session, profile_id: uuid.UUID) -> tuple[int, int, float | None]:
    statement = select(
        func.count(JobMatch.id),
        func.count(JobMatch.id).filter(JobMatch.status == MatchStatus.APPLIED),
        func.avg(func.extract("epoch", JobMatch.applied_at - JobMatch.created_at)).filter(
            JobMatch.applied_at.is_not(None)
        ),
    ).where(JobMatch.profile_id == profile_id)
    matched, applied, average = session.execute(statement).one()
    return int(matched), int(applied), float(average) if average is not None else None
