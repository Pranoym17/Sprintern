import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.models import Job, JobStatus, WorkMode

JobBoardSort = Literal["newest", "company", "deadline", "relevance"]


def get_job(session: Session, job_id: uuid.UUID) -> Job | None:
    statement = (
        select(Job)
        .options(selectinload(Job.sources))
        .where(
            Job.id == job_id,
            Job.status == JobStatus.ACTIVE,
            func.lower(func.coalesce(Job.term, "")) != "summer 2026",
        )
    )
    return session.scalar(statement)


def list_jobs(
    session: Session,
    limit: int,
    offset: int,
    query: str | None = None,
    company: str | None = None,
    location: str | None = None,
    term: str | None = None,
    work_mode: WorkMode | None = None,
    posted_within_days: int | None = None,
    sort: JobBoardSort = "newest",
) -> list[Job]:
    published_at = func.coalesce(Job.posted_at, Job.first_seen_at)
    statement = (
        select(Job)
        .options(selectinload(Job.sources))
        .where(
            Job.status == JobStatus.ACTIVE,
            func.lower(func.coalesce(Job.term, "")) != "summer 2026",
        )
    )
    if posted_within_days is not None:
        statement = statement.where(
            Job.first_seen_at >= datetime.now(UTC) - timedelta(days=posted_within_days)
        )
    if query:
        search = query.strip()
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.location.ilike(pattern),
            )
        )
    if company:
        statement = statement.where(Job.company.ilike(f"%{company.strip()}%"))
    if location:
        statement = statement.where(Job.location.ilike(f"%{location.strip()}%"))
    if term:
        statement = statement.where(Job.term == term)
    if work_mode and work_mode not in {WorkMode.ANY, WorkMode.UNKNOWN}:
        statement = statement.where(Job.work_mode == work_mode)

    ordering: tuple[Any, ...]
    if sort == "company":
        ordering = (Job.normalized_company.asc(), published_at.desc(), Job.id.desc())
    elif sort == "deadline":
        ordering = (Job.deadline_at.asc().nullslast(), published_at.desc(), Job.id.desc())
    elif sort == "relevance" and query:
        search = query.strip().casefold()
        relevance = func.greatest(
            func.similarity(Job.normalized_title, search),
            func.similarity(Job.normalized_company, search),
            func.similarity(func.coalesce(Job.normalized_location, ""), search),
        )
        ordering = (relevance.desc(), published_at.desc(), Job.id.desc())
    else:
        ordering = (published_at.desc(), Job.id.desc())
    return list(session.scalars(statement.order_by(*ordering).offset(offset).limit(limit + 1)))
