import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_user_db
from api.errors import AppError
from api.models import WorkMode
from api.repositories.jobs import get_job, list_jobs
from api.repositories.pagination import decode_offset_cursor, encode_offset_cursor
from api.schemas import JobPage, PublicJobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])
Database = Annotated[Session, Depends(get_user_db)]


@router.get("", response_model=JobPage)
def read_jobs(
    _user: CurrentUser,
    session: Database,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: str | None = None,
    query: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    company: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    location: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    term: Annotated[str | None, Query(pattern=r"^(?:Summer|Fall|Winter) \d{4}$")] = None,
    work_mode: WorkMode | None = None,
    posted_within_days: Literal[1, 7, 14, 30] | None = None,
    sort: Literal["newest", "company", "deadline", "relevance"] = "newest",
) -> JobPage:
    offset = decode_offset_cursor(cursor) if cursor else 0
    jobs = list_jobs(
        session,
        limit,
        offset,
        query,
        company,
        location,
        term,
        work_mode,
        posted_within_days,
        sort,
    )
    has_more = len(jobs) > limit
    items = jobs[:limit]
    # Offset cursors keep pagination opaque while supporting several user-selected sort orders.
    next_cursor = encode_offset_cursor(offset + limit) if has_more else None
    return JobPage(
        items=[PublicJobResponse.model_validate(job) for job in items], next_cursor=next_cursor
    )


@router.get("/{job_id}", response_model=PublicJobResponse)
def read_job(job_id: uuid.UUID, _user: CurrentUser, session: Database) -> object:
    job = get_job(session, job_id)
    if job is None:
        raise AppError(404, "not_found", "Job not found")
    return job
