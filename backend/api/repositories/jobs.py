import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.models import Job, JobStatus


def get_job(session: Session, job_id: uuid.UUID) -> Job | None:
    statement = select(Job).options(selectinload(Job.sources)).where(Job.id == job_id)
    return session.scalar(statement)


def list_jobs(
    session: Session,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
    query: str | None = None,
) -> list[Job]:
    published_at = func.coalesce(Job.posted_at, Job.first_seen_at)
    statement = (
        select(Job)
        .options(selectinload(Job.sources))
        .where(
            Job.status == JobStatus.ACTIVE,
            Job.first_seen_at >= datetime.now(UTC) - timedelta(days=30),
        )
        .order_by(published_at.desc(), Job.id.desc())
        .limit(limit + 1)
    )
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.location.ilike(pattern),
            )
        )
    if cursor:
        published_at_cursor, item_id = cursor
        statement = statement.where(
            or_(
                published_at < published_at_cursor,
                and_(published_at == published_at_cursor, Job.id < item_id),
            )
        )
    return list(session.scalars(statement))
