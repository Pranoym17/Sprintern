import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_user_db
from api.errors import AppError
from api.repositories.jobs import get_job, list_jobs
from api.repositories.pagination import decode_cursor, encode_cursor
from api.schemas import JobPage, JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])
Database = Annotated[Session, Depends(get_user_db)]


@router.get("", response_model=JobPage)
def read_jobs(
    _user: CurrentUser,
    session: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: str | None = None,
) -> JobPage:
    jobs = list_jobs(session, limit, decode_cursor(cursor) if cursor else None)
    has_more = len(jobs) > limit
    items = jobs[:limit]
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more else None
    return JobPage(
        items=[JobResponse.model_validate(job) for job in items], next_cursor=next_cursor
    )


@router.get("/{job_id}", response_model=JobResponse)
def read_job(job_id: uuid.UUID, _user: CurrentUser, session: Database) -> object:
    job = get_job(session, job_id)
    if job is None:
        raise AppError(404, "not_found", "Job not found")
    return job
