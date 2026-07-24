import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from api.auth import CurrentUser
from api.database import get_db, get_user_db
from api.errors import AppError
from api.models import (
    Application,
    ApplicationEvent,
    ApplicationStage,
    Job,
    JobInteraction,
    JobMatch,
    JobReport,
    ShareLink,
)
from api.rate_limiting import user_rate_limit
from api.schemas.discovery import (
    InteractionResponse,
    InteractionUpdate,
    JobReportCreate,
    JobReportResponse,
    PublicJobResponse,
    ShareCreate,
    ShareResponse,
)
from api.schemas.job import JobResponse
from api.settings import settings

router = APIRouter(tags=["discovery"])
UserDatabase = Annotated[Session, Depends(get_user_db)]
SystemDatabase = Annotated[Session, Depends(get_db)]


def _owned_job(session: Session, profile_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = session.scalar(
        select(Job)
        .options(selectinload(Job.sources))
        .join(JobMatch, JobMatch.job_id == Job.id)
        .where(Job.id == job_id, JobMatch.profile_id == profile_id)
    )
    if job is None:
        raise AppError(404, "not_found", "Job not found")
    return job


def _interaction(session: Session, profile_id: uuid.UUID, job_id: uuid.UUID) -> JobInteraction:
    interaction = session.scalar(
        select(JobInteraction).where(
            JobInteraction.profile_id == profile_id, JobInteraction.job_id == job_id
        )
    )
    if interaction is None:
        interaction = JobInteraction(profile_id=profile_id, job_id=job_id)
        session.add(interaction)
    return interaction


@router.get("/job-interactions", response_model=list[InteractionResponse])
def list_interactions(user: CurrentUser, session: UserDatabase) -> list[JobInteraction]:
    return list(
        session.scalars(
            select(JobInteraction)
            .where(JobInteraction.profile_id == user.id)
            .order_by(JobInteraction.last_viewed_at.desc().nullslast())
            .limit(500)
        )
    )


@router.patch(
    "/jobs/{job_id}/interaction",
    response_model=InteractionResponse,
    dependencies=[Depends(user_rate_limit("jobs.interaction", 120))],
)
def update_interaction(
    job_id: uuid.UUID, payload: InteractionUpdate, user: CurrentUser, session: UserDatabase
) -> object:
    _owned_job(session, user.id, job_id)
    interaction = _interaction(session, user.id, job_id)
    now = datetime.now(UTC)
    if payload.bookmarked is not None:
        interaction.bookmarked_at = now if payload.bookmarked else None
        if payload.bookmarked:
            application = session.scalar(
                select(Application).where(
                    Application.profile_id == user.id,
                    Application.job_id == job_id,
                )
            )
            if application is None:
                application = Application(
                    profile_id=user.id, job_id=job_id, stage=ApplicationStage.SAVED
                )
                session.add(application)
                session.flush()
                session.add(
                    ApplicationEvent(
                        application_id=application.id,
                        profile_id=user.id,
                        event_type="saved",
                        data={"trigger": "bookmark"},
                    )
                )
    if payload.hidden is not None:
        interaction.hidden_at = now if payload.hidden else None
    if "not_interested_reason" in payload.model_fields_set:
        interaction.not_interested_reason = payload.not_interested_reason
        if payload.not_interested_reason:
            interaction.hidden_at = now
    if "deadline_override_at" in payload.model_fields_set:
        interaction.deadline_override_at = payload.deadline_override_at
    session.commit()
    session.refresh(interaction)
    return interaction


@router.post(
    "/jobs/{job_id}/view",
    response_model=InteractionResponse,
    dependencies=[Depends(user_rate_limit("jobs.view", 240))],
)
def record_view(job_id: uuid.UUID, user: CurrentUser, session: UserDatabase) -> object:
    _owned_job(session, user.id, job_id)
    interaction = _interaction(session, user.id, job_id)
    now = datetime.now(UTC)
    interaction.first_viewed_at = interaction.first_viewed_at or now
    interaction.last_viewed_at = now
    interaction.view_count += 1
    session.commit()
    session.refresh(interaction)
    return interaction


@router.post(
    "/jobs/{job_id}/reports",
    response_model=JobReportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_rate_limit("jobs.report", 20, 3600))],
)
def report_job(
    job_id: uuid.UUID,
    payload: JobReportCreate,
    response: Response,
    user: CurrentUser,
    session: UserDatabase,
) -> object:
    _owned_job(session, user.id, job_id)
    report = session.scalar(
        select(JobReport).where(
            JobReport.profile_id == user.id,
            JobReport.job_id == job_id,
            JobReport.reason == payload.reason,
        )
    )
    if report is None:
        report = JobReport(profile_id=user.id, job_id=job_id, **payload.model_dump())
        session.add(report)
        response.status_code = status.HTTP_201_CREATED
    else:
        report.details = payload.details
        response.status_code = status.HTTP_200_OK
    session.commit()
    session.refresh(report)
    return report


@router.post(
    "/jobs/{job_id}/shares",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_rate_limit("jobs.share", 20, 3600))],
)
def create_share(
    job_id: uuid.UUID, payload: ShareCreate, user: CurrentUser, session: UserDatabase
) -> ShareResponse:
    _owned_job(session, user.id, job_id)
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(hours=payload.expires_in_hours)
    share = ShareLink(
        profile_id=user.id,
        job_id=job_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=expires_at,
    )
    session.add(share)
    session.commit()
    return ShareResponse(
        id=share.id,
        url=f"{settings.frontend_url.rstrip('/')}/shared/{token}",
        expires_at=expires_at,
    )


@router.delete(
    "/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(user_rate_limit("jobs.share.revoke", 30, 3600))],
)
def revoke_share(share_id: uuid.UUID, user: CurrentUser, session: UserDatabase) -> Response:
    share = session.scalar(
        select(ShareLink).where(ShareLink.id == share_id, ShareLink.profile_id == user.id)
    )
    if share is None:
        raise AppError(404, "not_found", "Share link not found")
    share.revoked_at = datetime.now(UTC)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/public/jobs/{job_id}", response_model=PublicJobResponse)
def public_job(job_id: uuid.UUID, session: SystemDatabase) -> PublicJobResponse:
    job = session.scalar(select(Job).options(selectinload(Job.sources)).where(Job.id == job_id))
    if job is None:
        raise AppError(404, "not_found", "Job not found")
    return PublicJobResponse(job=JobResponse.model_validate(job))


@router.get("/shared/jobs/{token}", response_model=PublicJobResponse)
def private_shared_job(token: str, session: SystemDatabase) -> PublicJobResponse:
    share = session.scalar(
        select(ShareLink).where(
            ShareLink.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            ShareLink.revoked_at.is_(None),
            ShareLink.expires_at > datetime.now(UTC),
        )
    )
    if share is None:
        raise AppError(404, "not_found", "Share link is invalid or expired")
    job = session.scalar(
        select(Job).options(selectinload(Job.sources)).where(Job.id == share.job_id)
    )
    if job is None:
        raise AppError(404, "not_found", "Job not found")
    return PublicJobResponse(job=JobResponse.model_validate(job), shared_until=share.expires_at)


@router.get("/jobs/{job_id}/similar", response_model=list[JobResponse])
def similar_jobs(
    job_id: uuid.UUID, user: CurrentUser, session: UserDatabase
) -> list[JobResponse]:
    job = _owned_job(session, user.id, job_id)
    similarity = (
        func.similarity(Job.normalized_title, job.normalized_title) * 3
        + cast(Job.normalized_company == job.normalized_company, Integer) * 2
        + cast(Job.term == job.term, Integer)
    )
    jobs = list(
        session.scalars(
            select(Job)
            .options(selectinload(Job.sources))
            .join(JobMatch, JobMatch.job_id == Job.id)
            .where(
                JobMatch.profile_id == user.id,
                Job.id != job.id,
                or_(
                    Job.normalized_company == job.normalized_company,
                    func.similarity(Job.normalized_title, job.normalized_title) >= 0.25,
                ),
            )
            .order_by(similarity.desc(), Job.first_seen_at.desc())
            .limit(6)
        )
    )
    return [JobResponse.model_validate(item) for item in jobs]
