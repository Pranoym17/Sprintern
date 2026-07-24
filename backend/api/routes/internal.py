from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import require_internal_api_key
from api.database import SessionLocal, get_db
from api.errors import AppError
from api.ingestion.factory import build_adapter
from api.ingestion.http import SourceHTTPError
from api.ingestion.service import IngestionService
from api.launch import launch_readiness, operational_status
from api.models import SourceState
from api.notifications.planning import notification_planner
from api.notifications.runtime import build_dispatcher
from api.scheduler.status import scheduler_status
from api.schemas import (
    IngestionRunRequest,
    IngestionRunResponse,
    SchedulerStatusResponse,
    SourceStatusResponse,
)
from api.schemas.common import DispatchResponse
from api.schemas.monitoring import LaunchReadinessResponse, OperationalStatusResponse
from api.settings import settings

router = APIRouter(
    tags=["internal"],
    dependencies=[Depends(require_internal_api_key)],
)
Database = Annotated[Session, Depends(get_db)]


@router.get("/sources/status", response_model=list[SourceStatusResponse])
def read_source_status(session: Database) -> object:
    return list(
        session.scalars(select(SourceState).order_by(SourceState.source, SourceState.source_key))
    )


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
def read_scheduler_status(session: Database) -> SchedulerStatusResponse:
    return scheduler_status(session, settings.scheduler_heartbeat_interval_seconds)


@router.get("/launch/readiness", response_model=LaunchReadinessResponse)
def read_launch_readiness(session: Database) -> LaunchReadinessResponse:
    return launch_readiness(session=session)


@router.get("/monitoring/status", response_model=OperationalStatusResponse)
async def read_operational_status(session: Database) -> OperationalStatusResponse:
    async with httpx.AsyncClient(timeout=10.0) as client:
        return await operational_status(session, client)


@router.post("/ingestion-runs", response_model=IngestionRunResponse, status_code=201)
async def create_ingestion_run(payload: IngestionRunRequest) -> object:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            run = await IngestionService(SessionLocal).run(build_adapter(payload, client))
    except SourceHTTPError as exc:
        # The service has already persisted the failed run; operators need a stable
        # integration error, not an internal traceback.
        raise AppError(502, "source_error", str(exc)) from exc
    return run


@router.post("/notifications/dispatch", response_model=DispatchResponse)
async def dispatch_notifications(limit: int = 100) -> DispatchResponse:
    with SessionLocal() as session:
        notification_planner.plan_events(session)
        session.commit()
    async with httpx.AsyncClient(timeout=10.0) as client:
        sent = await build_dispatcher(client).dispatch_due(limit=min(max(limit, 1), 500))
    return DispatchResponse(sent_deliveries=sent)
