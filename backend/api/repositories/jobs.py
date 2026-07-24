import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from api.models import Job, JobStatus


def get_job(session: Session, job_id: uuid.UUID) -> Job | None:
    statement = select(Job).options(selectinload(Job.sources)).where(Job.id == job_id)
    return session.scalar(statement)


def list_jobs(
    session: Session,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None,
) -> list[Job]:
    statement = (
        select(Job)
        .options(selectinload(Job.sources))
        .where(Job.status == JobStatus.ACTIVE)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        created_at, item_id = cursor
        statement = statement.where(
            or_(Job.created_at < created_at, and_(Job.created_at == created_at, Job.id < item_id))
        )
    return list(session.scalars(statement))
