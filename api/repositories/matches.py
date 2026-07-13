import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.models import Job, JobMatch, MatchStatus


def get_match(session: Session, profile_id: uuid.UUID, match_id: uuid.UUID) -> JobMatch | None:
    statement = (
        select(JobMatch)
        .options(selectinload(JobMatch.job).selectinload(Job.sources))
        .where(JobMatch.id == match_id, JobMatch.profile_id == profile_id)
    )
    return session.scalar(statement)


def list_matches(
    session: Session,
    profile_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
) -> list[JobMatch]:
    statement = (
        select(JobMatch)
        .options(selectinload(JobMatch.job).selectinload(Job.sources))
        .where(JobMatch.profile_id == profile_id)
        .order_by(JobMatch.created_at.desc(), JobMatch.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        created_at, item_id = cursor
        statement = statement.where(
            or_(
                JobMatch.created_at < created_at,
                and_(JobMatch.created_at == created_at, JobMatch.id < item_id),
            )
        )
    return list(session.scalars(statement))


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
