import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from api.auth import CurrentUser
from api.database import get_db
from api.errors import AppError
from api.ingestion.normalization import normalize_text
from api.matching import matching_service
from api.models import ExclusionType, FilterExclusion, JobFilter
from api.rate_limiting import user_rate_limit
from api.repositories.filters import get_filter, list_filters
from api.repositories.profiles import get_or_create_profile
from api.schemas import FilterCreate, FilterResponse, FilterUpdate

router = APIRouter(prefix="/filters", tags=["filters"])
Database = Annotated[Session, Depends(get_db)]

EXCLUSION_FIELDS = {
    "excluded_keywords": ExclusionType.KEYWORD,
    "excluded_companies": ExclusionType.COMPANY,
    "excluded_locations": ExclusionType.LOCATION,
}


def _replace_exclusions(job_filter: JobFilter, values: dict[str, Any]) -> None:
    supplied = {field: values.pop(field) for field in EXCLUSION_FIELDS if field in values}
    if not supplied:
        return
    retained = [
        item
        for item in job_filter.exclusions
        if item.kind not in {EXCLUSION_FIELDS[k] for k in supplied}
    ]
    for field, entries in supplied.items():
        retained.extend(
            FilterExclusion(
                kind=EXCLUSION_FIELDS[field], value=value, normalized_value=normalize_text(value)
            )
            for value in entries
        )
    job_filter.exclusions = retained


@router.get("", response_model=list[FilterResponse])
def read_filters(user: CurrentUser, session: Database) -> object:
    return list_filters(session, user.id)


@router.post(
    "",
    response_model=FilterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_rate_limit("filters.create", 20))],
)
def create_filter(
    payload: FilterCreate, response: Response, user: CurrentUser, session: Database
) -> object:
    get_or_create_profile(session, user.id, user.email)
    values = payload.model_dump()
    exclusions = {field: values.pop(field) for field in EXCLUSION_FIELDS}
    job_filter = JobFilter(profile_id=user.id, **values)
    _replace_exclusions(job_filter, exclusions)
    session.add(job_filter)
    session.flush()
    matching_service.match_profile(session, user.id)
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


@router.patch(
    "/{filter_id}",
    response_model=FilterResponse,
    dependencies=[Depends(user_rate_limit("filters.update", 30))],
)
def update_filter(
    filter_id: uuid.UUID, payload: FilterUpdate, user: CurrentUser, session: Database
) -> object:
    job_filter = get_filter(session, user.id, filter_id)
    if job_filter is None:
        raise AppError(404, "not_found", "Filter not found")
    updates = payload.model_dump(exclude_unset=True)
    if any(value is None for value in updates.values()):
        raise AppError(422, "validation_error", "Filter fields cannot be null")
    _replace_exclusions(job_filter, updates)
    for field, value in updates.items():
        setattr(job_filter, field, value)
    session.flush()
    matching_service.match_profile(session, user.id)
    session.commit()
    session.refresh(job_filter)
    return job_filter


@router.delete(
    "/{filter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(user_rate_limit("filters.delete", 20))],
)
def delete_filter(filter_id: uuid.UUID, user: CurrentUser, session: Database) -> Response:
    job_filter = get_filter(session, user.id, filter_id)
    if job_filter is None:
        raise AppError(404, "not_found", "Filter not found")
    session.delete(job_filter)
    session.flush()
    matching_service.match_profile(session, user.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
