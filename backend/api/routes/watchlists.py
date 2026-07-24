import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.auth import CurrentUser
from api.database import get_user_db
from api.errors import AppError
from api.ingestion.normalization import normalize_text
from api.matching import matching_service
from api.models import CompanyWatchlist, Job
from api.rate_limiting import user_rate_limit
from api.repositories.profiles import get_or_create_profile
from api.schemas.job import PublicJobResponse
from api.schemas.targeting import (
    WatchlistCreate,
    WatchlistJobs,
    WatchlistResponse,
    WatchlistUpdate,
)

router = APIRouter(prefix="/watchlists", tags=["watchlists"])
Database = Annotated[Session, Depends(get_user_db)]


def _owned(session: Session, profile_id: uuid.UUID, watchlist_id: uuid.UUID) -> CompanyWatchlist:
    item = session.scalar(
        select(CompanyWatchlist).where(
            CompanyWatchlist.id == watchlist_id,
            CompanyWatchlist.profile_id == profile_id,
        )
    )
    if item is None:
        raise AppError(404, "not_found", "Company watchlist not found")
    return item


@router.get("", response_model=list[WatchlistResponse])
def list_watchlists(user: CurrentUser, session: Database) -> list[CompanyWatchlist]:
    return list(
        session.scalars(
            select(CompanyWatchlist)
            .where(CompanyWatchlist.profile_id == user.id)
            .order_by(CompanyWatchlist.company)
        )
    )


@router.post(
    "",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_rate_limit("watchlists.create", 30))],
)
def create_watchlist(
    payload: WatchlistCreate, user: CurrentUser, session: Database
) -> CompanyWatchlist:
    get_or_create_profile(session, user.id, user.email)
    normalized = normalize_text(payload.company)
    existing = session.scalar(
        select(CompanyWatchlist).where(
            CompanyWatchlist.profile_id == user.id,
            CompanyWatchlist.normalized_company == normalized,
        )
    )
    if existing:
        raise AppError(409, "already_following", "This company is already followed")
    item = CompanyWatchlist(
        profile_id=user.id,
        normalized_company=normalized,
        **payload.model_dump(),
    )
    session.add(item)
    session.flush()
    matching_service.match_profile(session, user.id)
    session.commit()
    session.refresh(item)
    return item


@router.patch(
    "/{watchlist_id}",
    response_model=WatchlistResponse,
    dependencies=[Depends(user_rate_limit("watchlists.update", 60))],
)
def update_watchlist(
    watchlist_id: uuid.UUID,
    payload: WatchlistUpdate,
    user: CurrentUser,
    session: Database,
) -> CompanyWatchlist:
    item = _owned(session, user.id, watchlist_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise AppError(422, "validation_error", "Watchlist fields cannot be null")
        setattr(item, field, value)
    session.flush()
    matching_service.match_profile(session, user.id)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(watchlist_id: uuid.UUID, user: CurrentUser, session: Database) -> Response:
    session.delete(_owned(session, user.id, watchlist_id))
    session.flush()
    matching_service.match_profile(session, user.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{watchlist_id}/jobs", response_model=WatchlistJobs)
def watchlist_jobs(watchlist_id: uuid.UUID, user: CurrentUser, session: Database) -> WatchlistJobs:
    watchlist = _owned(session, user.id, watchlist_id)
    statement = (
        select(Job)
        .options(selectinload(Job.sources))
        .where(Job.normalized_company == watchlist.normalized_company)
        .order_by(Job.first_seen_at.desc())
        .limit(100)
    )
    jobs = list(session.scalars(statement))
    return WatchlistJobs(items=[PublicJobResponse.model_validate(job) for job in jobs])
