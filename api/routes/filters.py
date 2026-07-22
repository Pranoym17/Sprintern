import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.auth import CurrentUser
from api.database import get_db
from api.errors import AppError
from api.ingestion.normalization import normalize_text
from api.matching import matching_service
from api.matching.matcher import ROLE_ALIASES, match_filter
from api.models import (
    ExclusionType,
    FilterExclusion,
    FilterNotificationOverride,
    Job,
    JobFilter,
    JobStatus,
)
from api.notifications.planning import notification_planner
from api.rate_limiting import user_rate_limit
from api.repositories.filters import get_filter, list_filters
from api.repositories.profiles import get_or_create_profile
from api.schemas import FilterCreate, FilterResponse, FilterUpdate
from api.schemas.filter import (
    FilterNotificationResponse,
    FilterNotificationUpdate,
    FilterPreviewExample,
    FilterPreviewResponse,
)

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


@router.post(
    "/preview",
    response_model=FilterPreviewResponse,
    dependencies=[Depends(user_rate_limit("filters.preview", 60))],
)
def preview_filter(
    payload: FilterCreate, user: CurrentUser, session: Database
) -> FilterPreviewResponse:
    values = payload.model_dump()
    exclusions = {field: values.pop(field) for field in EXCLUSION_FIELDS}
    exclusion_summary = {field: list(items) for field, items in exclusions.items()}
    candidate = JobFilter(id=uuid.uuid4(), profile_id=user.id, **values)
    _replace_exclusions(candidate, exclusions.copy())
    jobs = list(
        session.scalars(
            select(Job)
            .options(selectinload(Job.sources))
            .where(Job.status == JobStatus.ACTIVE)
            .order_by(Job.first_seen_at.desc())
            .limit(5000)
        )
    )
    matches = [(job, result) for job in jobs if (result := match_filter(job, candidate))]
    warnings: list[str] = []
    if not matches:
        warnings.append("No current jobs match; this filter may be too narrow.")
    elif len(matches) > 500:
        warnings.append("This filter is broad and may produce many alerts.")
    if payload.radius_km and any(
        job.latitude is None for job in jobs if job.work_mode.value != "remote"
    ):
        warnings.append("Jobs with unknown physical locations cannot pass a radius filter.")
    aliases = {
        keyword: list(ROLE_ALIASES.get(keyword.casefold(), ()))
        for keyword in payload.role_keywords
        if keyword.casefold() in ROLE_ALIASES
    }
    return FilterPreviewResponse(
        estimated_count=len(matches),
        examples=[
            FilterPreviewExample(
                id=job.id,
                company=job.company,
                title=job.title,
                location=job.location,
                reasons=result.reasons,
            )
            for job, result in matches[:5]
        ],
        warnings=warnings,
        aliases=aliases,
        exclusions=exclusion_summary,
    )


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
    nullable = {"radius_km", "center_latitude", "center_longitude"}
    if any(value is None for field, value in updates.items() if field not in nullable):
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


@router.get("/{filter_id}/notifications", response_model=FilterNotificationResponse)
def read_filter_notifications(
    filter_id: uuid.UUID, user: CurrentUser, session: Database
) -> FilterNotificationResponse:
    if get_filter(session, user.id, filter_id) is None:
        raise AppError(404, "not_found", "Filter not found")
    override = session.get(FilterNotificationOverride, filter_id)
    return FilterNotificationResponse(
        filter_id=filter_id,
        email_enabled=override.email_enabled if override else None,
        telegram_enabled=override.telegram_enabled if override else None,
        cadence=override.cadence if override else None,
        priority=override.priority if override else "normal",
        uses_profile_defaults=override is None,
    )


@router.put("/{filter_id}/notifications", response_model=FilterNotificationResponse)
def update_filter_notifications(
    filter_id: uuid.UUID,
    payload: FilterNotificationUpdate,
    user: CurrentUser,
    session: Database,
) -> FilterNotificationResponse:
    if get_filter(session, user.id, filter_id) is None:
        raise AppError(404, "not_found", "Filter not found")
    override = session.get(FilterNotificationOverride, filter_id)
    if override is None:
        override = FilterNotificationOverride(filter_id=filter_id, profile_id=user.id)
        session.add(override)
    for field, value in payload.model_dump().items():
        setattr(override, field, value)
    session.flush()
    notification_planner.backfill_profile(session, user.id)
    session.commit()
    return FilterNotificationResponse(
        filter_id=filter_id,
        **payload.model_dump(),
        uses_profile_defaults=False,
    )
