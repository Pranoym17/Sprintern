import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_db
from api.errors import AppError
from api.models import JobFilter
from api.repositories.filters import get_filter, list_filters
from api.repositories.profiles import get_or_create_profile
from api.schemas import FilterCreate, FilterResponse, FilterUpdate

router = APIRouter(prefix="/filters", tags=["filters"])
Database = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[FilterResponse])
def read_filters(user: CurrentUser, session: Database) -> object:
    return list_filters(session, user.id)


@router.post("", response_model=FilterResponse, status_code=status.HTTP_201_CREATED)
def create_filter(
    payload: FilterCreate, response: Response, user: CurrentUser, session: Database
) -> object:
    get_or_create_profile(session, user.id, user.email)
    job_filter = JobFilter(profile_id=user.id, **payload.model_dump())
    session.add(job_filter)
    session.commit()
    session.refresh(job_filter)
    response.headers["Location"] = f"/filters/{job_filter.id}"
    return job_filter


@router.get("/{filter_id}", response_model=FilterResponse)
def read_filter(filter_id: uuid.UUID, user: CurrentUser, session: Database) -> object:
    job_filter = get_filter(session, user.id, filter_id)
    if job_filter is None:
        raise AppError(404, "not_found", "Filter not found")
    return job_filter


@router.patch("/{filter_id}", response_model=FilterResponse)
def update_filter(
    filter_id: uuid.UUID, payload: FilterUpdate, user: CurrentUser, session: Database
) -> object:
    job_filter = get_filter(session, user.id, filter_id)
    if job_filter is None:
        raise AppError(404, "not_found", "Filter not found")
    updates = payload.model_dump(exclude_unset=True)
    if any(value is None for value in updates.values()):
        raise AppError(422, "validation_error", "Filter fields cannot be null")
    for field, value in updates.items():
        setattr(job_filter, field, value)
    session.commit()
    session.refresh(job_filter)
    return job_filter


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_filter(filter_id: uuid.UUID, user: CurrentUser, session: Database) -> Response:
    job_filter = get_filter(session, user.id, filter_id)
    if job_filter is None:
        raise AppError(404, "not_found", "Filter not found")
    session.delete(job_filter)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
