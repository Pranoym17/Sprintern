import csv
import hashlib
import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from api.auth import CurrentUser
from api.database import get_db
from api.errors import AppError
from api.ingestion.normalization import normalize_text
from api.models import (
    Application,
    ApplicationEvent,
    ApplicationStage,
    Job,
    JobFilter,
    JobMatch,
    ReminderEvent,
    ReminderType,
    WeeklyGoal,
)
from api.rate_limiting import user_rate_limit
from api.repositories.profiles import get_or_create_profile
from api.schemas.application import (
    ApplicationCorrection,
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
    CSVImportRequest,
    CSVImportResponse,
    CSVImportRow,
    WeeklyGoalUpdate,
    WeeklyProgress,
)

router = APIRouter(tags=["applications"])
Database = Annotated[Session, Depends(get_db)]


def _query() -> Any:
    return select(Application).options(
        selectinload(Application.job).selectinload(Job.sources),
        selectinload(Application.events),
    )


def _owned(session: Session, profile_id: uuid.UUID, application_id: uuid.UUID) -> Application:
    application = session.scalar(
        _query().where(Application.id == application_id, Application.profile_id == profile_id)
    )
    if application is None:
        raise AppError(404, "not_found", "Application not found")
    return cast(Application, application)


def _event(
    application: Application, profile_id: uuid.UUID, event_type: str, data: dict[str, Any]
) -> None:
    application.events.append(
        ApplicationEvent(profile_id=profile_id, event_type=event_type, data=data)
    )


def _sync_reminders(session: Session, application: Application) -> None:
    schedules = {
        ReminderType.DEADLINE: application.deadline_at,
        ReminderType.FOLLOW_UP: application.follow_up_at,
        ReminderType.INTERVIEW: application.interview_at,
    }
    if application.stage == ApplicationStage.SAVED:
        schedules[ReminderType.SAVED] = application.updated_at + timedelta(days=7)
    elif application.stage == ApplicationStage.PREPARING:
        schedules[ReminderType.PREPARING] = application.updated_at + timedelta(days=3)
    for stage_kind in (ReminderType.SAVED, ReminderType.PREPARING):
        if stage_kind not in schedules:
            session.execute(
                delete(ReminderEvent).where(
                    ReminderEvent.application_id == application.id,
                    ReminderEvent.kind == stage_kind,
                    ReminderEvent.sent_at.is_(None),
                )
            )
    for kind, due_at in schedules.items():
        session.execute(
            delete(ReminderEvent).where(
                ReminderEvent.application_id == application.id,
                ReminderEvent.kind == kind,
                ReminderEvent.sent_at.is_(None),
            )
        )
        if due_at:
            session.add(
                ReminderEvent(
                    profile_id=application.profile_id,
                    application_id=application.id,
                    kind=kind,
                    due_at=due_at,
                    idempotency_key=f"application:{application.id}:{kind.value}:{due_at.isoformat()}",
                )
            )


@router.get("/applications", response_model=list[ApplicationResponse])
def list_applications(
    user: CurrentUser,
    session: Database,
    stage_filter: Annotated[ApplicationStage | None, Query(alias="stage")] = None,
) -> list[Application]:
    statement = _query().where(Application.profile_id == user.id)
    if stage_filter:
        statement = statement.where(Application.stage == stage_filter)
    return list(session.scalars(statement.order_by(Application.updated_at.desc()).limit(500)))


@router.post(
    "/applications",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_rate_limit("applications.create", 60))],
)
def create_application(
    payload: ApplicationCreate, user: CurrentUser, session: Database
) -> Application:
    get_or_create_profile(session, user.id, user.email)
    job = session.get(Job, payload.job_id)
    if job is None:
        raise AppError(404, "not_found", "Job not found")
    existing = session.scalar(
        _query().where(Application.profile_id == user.id, Application.job_id == job.id)
    )
    if existing:
        raise AppError(409, "already_tracked", "This job is already in your tracker")
    values = payload.model_dump()
    if payload.stage == ApplicationStage.APPLIED and not payload.applied_at:
        values["applied_at"] = datetime.now(UTC)
    application = Application(profile_id=user.id, **values)
    _event(application, user.id, "created", {"stage": payload.stage.value})
    session.add(application)
    session.flush()
    _sync_reminders(session, application)
    session.commit()
    return _owned(session, user.id, application.id)


@router.patch("/applications/{application_id}", response_model=ApplicationResponse)
def update_application(
    application_id: uuid.UUID,
    payload: ApplicationUpdate,
    user: CurrentUser,
    session: Database,
) -> Application:
    application = _owned(session, user.id, application_id)
    changes: dict[str, dict[str, Any]] = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "stage" and value is None:
            raise AppError(422, "invalid_stage", "Application stage cannot be empty")
        before = getattr(application, field)
        if before != value:
            changes[field] = {
                "from": before.isoformat()
                if isinstance(before, datetime)
                else getattr(before, "value", before),
                "to": value.isoformat()
                if isinstance(value, datetime)
                else getattr(value, "value", value),
            }
            setattr(application, field, value)
    if application.stage == ApplicationStage.APPLIED and application.applied_at is None:
        application.applied_at = datetime.now(UTC)
    if changes:
        event_type = "stage_changed" if "stage" in changes else "details_updated"
        _event(application, user.id, event_type, {"changes": changes})
    session.flush()
    _sync_reminders(session, application)
    session.commit()
    return _owned(session, user.id, application.id)


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: uuid.UUID, user: CurrentUser, session: Database) -> Response:
    session.delete(_owned(session, user.id, application_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/applications/{application_id}/events/{event_id}/corrections",
    response_model=ApplicationResponse,
)
def correct_application_event(
    application_id: uuid.UUID,
    event_id: uuid.UUID,
    payload: ApplicationCorrection,
    user: CurrentUser,
    session: Database,
) -> Application:
    application = _owned(session, user.id, application_id)
    original = session.scalar(
        select(ApplicationEvent).where(
            ApplicationEvent.id == event_id,
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.profile_id == user.id,
        )
    )
    if original is None:
        raise AppError(404, "not_found", "Timeline event not found")
    application.events.append(
        ApplicationEvent(
            profile_id=user.id,
            event_type="correction",
            data={"note": payload.note},
            corrected_event_id=original.id,
        )
    )
    session.commit()
    return _owned(session, user.id, application.id)


def _manual_job(session: Session, row: dict[str, str]) -> Job:
    company = row.get("company", "").strip()
    title = row.get("title", "").strip()
    location = row.get("location", "").strip() or None
    fingerprint = hashlib.sha256(
        (
            f"manual|{normalize_text(company)}|{normalize_text(title)}|"
            f"{normalize_text(location or '')}"
        ).encode()
    ).hexdigest()
    job = session.scalar(select(Job).where(Job.canonical_fingerprint == fingerprint))
    if job:
        return job
    now = datetime.now(UTC)
    job = Job(
        company=company,
        normalized_company=normalize_text(company),
        title=title,
        normalized_title=normalize_text(title),
        location=location,
        normalized_location=normalize_text(location) if location else None,
        canonical_fingerprint=fingerprint,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(job)
    session.flush()
    return job


@router.post(
    "/imports/applications/csv",
    response_model=CSVImportResponse,
    dependencies=[Depends(user_rate_limit("applications.import", 10, 3600))],
)
def import_applications(
    payload: CSVImportRequest, user: CurrentUser, session: Database
) -> CSVImportResponse:
    get_or_create_profile(session, user.id, user.email)
    reader = csv.DictReader(io.StringIO(payload.csv_text))
    columns = reader.fieldnames or []
    required = {"company", "title"}
    if not required.issubset(payload.mapping):
        raise AppError(422, "mapping_required", "Map company and title columns")
    missing_columns = sorted(set(payload.mapping.values()) - set(columns))
    if missing_columns:
        raise AppError(
            422,
            "invalid_mapping",
            f"Mapped columns were not found: {', '.join(missing_columns)}",
        )
    errors: list[CSVImportRow] = []
    valid = imported = duplicates = 0
    for number, source in enumerate(reader, start=2):
        row = {target: source.get(column, "") for target, column in payload.mapping.items()}
        if not row.get("company", "").strip() or not row.get("title", "").strip():
            errors.append(
                CSVImportRow(row=number, status="invalid", message="Company and title are required")
            )
            continue
        valid += 1
        import_key = hashlib.sha256(
            "|".join(
                row.get(field, "").strip().casefold()
                for field in ("company", "title", "applied_at")
            ).encode()
        ).hexdigest()
        if session.scalar(
            select(Application.id).where(
                Application.profile_id == user.id, Application.import_key == import_key
            )
        ):
            duplicates += 1
            continue
        if payload.dry_run:
            continue
        job = _manual_job(session, row)
        stage_value = row.get("stage", "saved").strip().casefold()
        try:
            stage = ApplicationStage(stage_value)
        except ValueError:
            stage = ApplicationStage.SAVED
        applied_at = None
        if row.get("applied_at", "").strip():
            try:
                applied_at = datetime.fromisoformat(
                    row["applied_at"].strip().replace("Z", "+00:00")
                )
            except ValueError:
                errors.append(
                    CSVImportRow(
                        row=number,
                        status="invalid",
                        message="Applied date must use ISO 8601 format",
                    )
                )
                valid -= 1
                continue
        application = Application(
            profile_id=user.id,
            job_id=job.id,
            stage=stage,
            notes=row.get("notes") or None,
            application_url=row.get("application_url") or None,
            applied_at=applied_at,
            import_key=import_key,
        )
        _event(application, user.id, "imported", {"row": number})
        session.add(application)
        imported += 1
    if not payload.dry_run:
        session.commit()
    return CSVImportResponse(
        total_rows=valid + len(errors),
        valid_rows=valid,
        imported_rows=imported,
        duplicate_rows=duplicates,
        errors=errors,
        detected_columns=columns,
    )


@router.get("/exports/applications.csv")
def export_applications_csv(user: CurrentUser, session: Database) -> Response:
    applications = list_applications(user, session)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "company",
            "title",
            "location",
            "stage",
            "applied_at",
            "follow_up_at",
            "interview_at",
            "notes",
            "application_url",
        ]
    )
    for item in applications:
        writer.writerow(
            [
                item.job.company,
                item.job.title,
                item.job.location or "",
                item.stage.value,
                item.applied_at or "",
                item.follow_up_at or "",
                item.interview_at or "",
                item.notes or "",
                item.application_url or "",
            ]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sprintern-applications.csv"},
    )


def _csv_response(filename: str, rows: list[list[Any]]) -> Response:
    output = io.StringIO()
    csv.writer(output).writerows(rows)
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/exports/matches.csv")
def export_matches_csv(user: CurrentUser, session: Database) -> Response:
    matches = list(
        session.scalars(
            select(JobMatch)
            .options(selectinload(JobMatch.job))
            .where(JobMatch.profile_id == user.id)
            .order_by(JobMatch.created_at.desc())
        )
    )
    return _csv_response(
        "sprintern-matches.csv",
        [["company", "title", "location", "status", "matched_at"]]
        + [
            [
                item.job.company,
                item.job.title,
                item.job.location or "",
                item.status.value,
                item.created_at,
            ]
            for item in matches
        ],
    )


@router.get("/exports/filters.csv")
def export_filters_csv(user: CurrentUser, session: Database) -> Response:
    filters = list(session.scalars(select(JobFilter).where(JobFilter.profile_id == user.id)))
    return _csv_response(
        "sprintern-filters.csv",
        [["name", "roles", "locations", "terms", "work_mode", "active"]]
        + [
            [
                item.name,
                ";".join(item.role_keywords),
                ";".join(item.location_keywords),
                ";".join(item.terms),
                item.work_mode.value,
                item.active,
            ]
            for item in filters
        ],
    )


@router.get("/exports/timeline.csv")
def export_timeline_csv(user: CurrentUser, session: Database) -> Response:
    events = list(
        session.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.profile_id == user.id)
            .order_by(ApplicationEvent.created_at)
        )
    )
    return _csv_response(
        "sprintern-timeline.csv",
        [["application_id", "event", "created_at", "data"]]
        + [
            [item.application_id, item.event_type, item.created_at, str(item.data)]
            for item in events
        ],
    )


@router.get("/goals/weekly", response_model=WeeklyProgress)
def weekly_progress(user: CurrentUser, session: Database) -> WeeklyProgress:
    goal = session.scalar(select(WeeklyGoal).where(WeeklyGoal.profile_id == user.id))
    if goal is None:
        goal = WeeklyGoal(profile_id=user.id)
        session.add(goal)
        session.flush()
    now = datetime.now(UTC)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    applied = (
        session.scalar(
            select(func.count(Application.id)).where(
                Application.profile_id == user.id, Application.applied_at >= week_start
            )
        )
        or 0
    )
    interviews = (
        session.scalar(
            select(func.count(Application.id)).where(
                Application.profile_id == user.id, Application.stage == ApplicationStage.INTERVIEW
            )
        )
        or 0
    )
    offers = (
        session.scalar(
            select(func.count(Application.id)).where(
                Application.profile_id == user.id, Application.stage == ApplicationStage.OFFER
            )
        )
        or 0
    )
    week_bucket = func.date_trunc("week", Application.applied_at).label("week_start")
    weekly_counts = list(
        session.execute(
            select(week_bucket, func.count(Application.id))
            .where(Application.profile_id == user.id, Application.applied_at.is_not(None))
            .group_by(week_bucket)
            .order_by(week_bucket.desc())
        )
    )
    streak = best = 0
    for _, count in reversed(weekly_counts):
        streak = streak + 1 if goal.target > 0 and count >= goal.target else 0
        best = max(best, streak)
    current = 0
    for _, count in weekly_counts:
        if goal.target <= 0 or count < goal.target:
            break
        current += 1
    session.commit()
    return WeeklyProgress(
        target=goal.target,
        applied=int(applied),
        interviews=int(interviews),
        offers=int(offers),
        current_streak=current,
        best_streak=best,
        reminders_enabled=goal.reminders_enabled,
        streaks_enabled=goal.streaks_enabled,
    )


@router.put("/goals/weekly", response_model=WeeklyProgress)
def update_weekly_goal(
    payload: WeeklyGoalUpdate, user: CurrentUser, session: Database
) -> WeeklyProgress:
    get_or_create_profile(session, user.id, user.email)
    goal = session.scalar(select(WeeklyGoal).where(WeeklyGoal.profile_id == user.id))
    if goal is None:
        goal = WeeklyGoal(profile_id=user.id)
        session.add(goal)
    for field, value in payload.model_dump().items():
        setattr(goal, field, value)
    session.commit()
    return weekly_progress(user, session)
