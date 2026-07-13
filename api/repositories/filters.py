import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import JobFilter


def list_filters(session: Session, profile_id: uuid.UUID) -> list[JobFilter]:
    statement = (
        select(JobFilter).where(JobFilter.profile_id == profile_id).order_by(JobFilter.created_at)
    )
    return list(session.scalars(statement))


def get_filter(session: Session, profile_id: uuid.UUID, filter_id: uuid.UUID) -> JobFilter | None:
    statement = select(JobFilter).where(
        JobFilter.id == filter_id, JobFilter.profile_id == profile_id
    )
    return session.scalar(statement)
