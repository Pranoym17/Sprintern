import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import Administrator
from api.database import SessionLocal, get_db
from api.errors import AppError
from api.ingestion.factory import build_adapter
from api.ingestion.http import SourceHTTPError
from api.ingestion.normalization import normalize_job
from api.ingestion.service import IngestionService
from api.models import (
    IngestionRun,
    JobSource,
    JobSourceName,
    SourceAuditLog,
    SourceConfiguration,
    SourceState,
)
from api.observability import request_id_context
from api.rate_limiting import user_rate_limit
from api.schemas.admin_source import (
    AdminAccessResponse,
    AdminRunResponse,
    AdminSourceCreate,
    AdminSourceResponse,
    AdminSourceUpdate,
    PreviewSample,
    SourceAuditResponse,
    SourceDeleteRequest,
    SourcePreviewResponse,
    SourceStateChange,
    TermSummary,
)
from api.schemas.ingestion import IngestionRunRequest, IngestionRunResponse

router = APIRouter(prefix="/admin", tags=["administration"])
Database = Annotated[Session, Depends(get_db)]


def _source_key(owner: str, repository: str, path: str) -> str:
    return f"{owner}/{repository}:{path}"


def _audit(
    session: Session,
    admin_id: uuid.UUID,
    action: str,
    source_id: uuid.UUID | None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        SourceAuditLog(
            source_configuration_id=source_id,
            administrator_id=admin_id,
            action=action,
            details=details or {},
            request_id=request_id_context.get(),
        )
    )


def _get_source(session: Session, source_id: uuid.UUID) -> SourceConfiguration:
    source = session.get(SourceConfiguration, source_id)
    if source is None:
        raise AppError(404, "not_found", "Source configuration not found")
    return source


def _response(session: Session, source: SourceConfiguration) -> AdminSourceResponse:
    state = session.scalar(
        select(SourceState).where(
            SourceState.source == source.source, SourceState.source_key == source.source_key
        )
    )
    return AdminSourceResponse(
        id=source.id,
        source_key=source.source_key,
        owner=source.owner,
        repository=source.repository,
        branch=source.branch,
        path=source.path,
        enabled=source.enabled,
        poll_minutes=source.poll_minutes,
        jitter_seconds=source.jitter_seconds,
        default_term=source.default_term,
        parser_schema=source.parser_schema,
        parser_version=source.parser_version,
        last_validated_at=source.last_validated_at,
        last_succeeded_at=state.last_succeeded_at if state else None,
        last_failed_at=state.last_failed_at if state else None,
        consecutive_failures=state.consecutive_failures if state else 0,
        last_error=state.last_error if state else None,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _ingestion_request(source: SourceConfiguration) -> IngestionRunRequest:
    return IngestionRunRequest(
        source=JobSourceName.GITHUB_REPO,
        owner=source.owner,
        repository=source.repository,
        branch=source.branch,
        path=source.path,
        term=source.default_term,
    )


@router.get("/me", response_model=AdminAccessResponse)
def admin_access(_admin: Administrator) -> AdminAccessResponse:
    return AdminAccessResponse()


@router.get("/sources", response_model=list[AdminSourceResponse])
def list_admin_sources(_admin: Administrator, session: Database) -> list[AdminSourceResponse]:
    sources = list(
        session.scalars(select(SourceConfiguration).order_by(SourceConfiguration.source_key))
    )
    return [_response(session, source) for source in sources]


@router.post(
    "/sources",
    response_model=AdminSourceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(user_rate_limit("admin.sources.create", 20, 3600))],
)
def create_admin_source(
    payload: AdminSourceCreate, admin: Administrator, session: Database
) -> AdminSourceResponse:
    key = _source_key(payload.owner, payload.repository, payload.path)
    if session.scalar(
        select(SourceConfiguration.id).where(
            SourceConfiguration.source == JobSourceName.GITHUB_REPO,
            SourceConfiguration.source_key == key,
        )
    ):
        raise AppError(409, "source_exists", "This repository path is already configured")
    source = SourceConfiguration(
        source=JobSourceName.GITHUB_REPO,
        source_key=key,
        configuration={},
        enabled=False,
        **payload.model_dump(),
    )
    session.add(source)
    session.flush()
    _audit(session, admin.id, "created", source.id, {"source_key": key})
    session.commit()
    session.refresh(source)
    return _response(session, source)


@router.patch("/sources/{source_id}", response_model=AdminSourceResponse)
def update_admin_source(
    source_id: uuid.UUID,
    payload: AdminSourceUpdate,
    admin: Administrator,
    session: Database,
) -> AdminSourceResponse:
    source = _get_source(session, source_id)
    updates = payload.model_dump(exclude_unset=True)
    if any(
        value is None
        for field, value in updates.items()
        if field != "branch" and field != "default_term"
    ):
        raise AppError(422, "validation_error", "Required source fields cannot be null")
    next_owner = updates.get("owner", source.owner)
    next_repository = updates.get("repository", source.repository)
    next_path = updates.get("path", source.path)
    next_key = _source_key(next_owner, next_repository, next_path)
    duplicate = session.scalar(
        select(SourceConfiguration.id).where(
            SourceConfiguration.source == JobSourceName.GITHUB_REPO,
            SourceConfiguration.source_key == next_key,
            SourceConfiguration.id != source.id,
        )
    )
    if duplicate is not None:
        raise AppError(409, "source_exists", "This repository path is already configured")
    before = {field: getattr(source, field) for field in updates}
    for field, value in updates.items():
        setattr(source, field, value)
    source.source_key = next_key
    source.last_validated_at = None
    source.enabled = False
    _audit(
        session,
        admin.id,
        "updated",
        source.id,
        {"changed_fields": sorted(updates), "previous": before},
    )
    session.commit()
    session.refresh(source)
    return _response(session, source)


@router.post("/sources/{source_id}/state", response_model=AdminSourceResponse)
def change_source_state(
    source_id: uuid.UUID,
    payload: SourceStateChange,
    admin: Administrator,
    session: Database,
) -> AdminSourceResponse:
    source = _get_source(session, source_id)
    if payload.enabled and source.last_validated_at is None:
        raise AppError(
            409, "validation_required", "Preview and validate this source before enabling it"
        )
    source.enabled = payload.enabled
    _audit(session, admin.id, "enabled" if payload.enabled else "disabled", source.id)
    session.commit()
    session.refresh(source)
    return _response(session, source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin_source(
    source_id: uuid.UUID,
    payload: SourceDeleteRequest,
    admin: Administrator,
    session: Database,
) -> Response:
    source = _get_source(session, source_id)
    expected = f"DELETE {source.owner}/{source.repository}"
    if payload.confirmation != expected:
        raise AppError(422, "confirmation_required", f"Type {expected} to confirm deletion")
    key = source.source_key
    source.enabled = False
    session.flush()
    _audit(session, admin.id, "deleted", source.id, {"source_key": key})
    session.delete(source)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sources/{source_id}/preview", response_model=SourcePreviewResponse)
async def preview_admin_source(
    source_id: uuid.UUID, admin: Administrator, session: Database
) -> SourcePreviewResponse:
    source = _get_source(session, source_id)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            adapter = build_adapter(_ingestion_request(source), client)
            batch = await adapter.fetch({})
    except SourceHTTPError as exc:
        raise AppError(502, "source_error", str(exc)) from exc
    normalized = []
    errors = list(batch.rejection_errors)
    for row in batch.records:
        try:
            normalized.append(normalize_job(adapter.source, adapter.source_key, row))
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
    external_ids = {item.external_id for item in normalized}
    duplicates = 0
    if external_ids:
        duplicates = len(
            set(
                session.scalars(
                    select(JobSource.external_id).where(
                        JobSource.source == JobSourceName.GITHUB_REPO,
                        JobSource.source_key == source.source_key,
                        JobSource.external_id.in_(external_ids),
                    )
                )
            )
        )
    terms = Counter(item.term or "Unknown" for item in normalized)
    domain_values: set[str] = set()
    for item in normalized:
        if hostname := urlparse(item.apply_url).hostname:
            domain_values.add(hostname)
    domains = sorted(domain_values)
    suspicious = [
        f"{item.company}: {item.title}"
        for item in normalized
        if len(item.title) < 5 or item.title.endswith(("...", "…"))
    ][:25]
    source.last_validated_at = datetime.now(UTC)
    _audit(
        session,
        admin.id,
        "previewed",
        source.id,
        {"accepted": len(normalized), "rejected": len(errors)},
    )
    session.commit()
    return SourcePreviewResponse(
        rows_fetched=len(batch.records) + batch.rejected_count,
        accepted=len(normalized),
        rejected=len(errors),
        duplicate_candidates=duplicates,
        sample_normalized_output=[
            PreviewSample(
                company=item.company,
                title=item.title,
                location=item.location,
                term=item.term,
                application_url=item.apply_url,
                application_domain=urlparse(item.apply_url).hostname,
                canonical_fingerprint=item.canonical_fingerprint,
            )
            for item in normalized[:10]
        ],
        detected_table_schema=source.parser_schema,
        missing_columns=[],
        rejected_rows=errors[:25],
        suspicious_truncated_values=suspicious,
        inferred_terms=[
            TermSummary(term=term, count=count)
            for term, count in sorted(terms.items(), key=lambda item: item[0] or "")
        ],
        application_domains=domains,
    )


@router.post("/sources/{source_id}/ingest", response_model=IngestionRunResponse)
async def ingest_admin_source(
    source_id: uuid.UUID, admin: Administrator, session: Database
) -> object:
    source = _get_source(session, source_id)
    if source.last_validated_at is None:
        raise AppError(409, "validation_required", "Preview this source before ingestion")
    request = _ingestion_request(source)
    _audit(session, admin.id, "ingestion_triggered", source.id)
    session.commit()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await IngestionService(SessionLocal).run(build_adapter(request, client))
    except SourceHTTPError as exc:
        raise AppError(502, "source_error", str(exc)) from exc


@router.get("/sources/{source_id}/runs", response_model=list[AdminRunResponse])
def source_run_history(
    source_id: uuid.UUID, _admin: Administrator, session: Database
) -> list[IngestionRun]:
    source = _get_source(session, source_id)
    state = session.scalar(
        select(SourceState).where(
            SourceState.source == source.source, SourceState.source_key == source.source_key
        )
    )
    if state is None:
        return []
    return list(
        session.scalars(
            select(IngestionRun)
            .where(IngestionRun.source_state_id == state.id)
            .order_by(IngestionRun.started_at.desc())
            .limit(100)
        )
    )


@router.get("/source-audit", response_model=list[SourceAuditResponse])
def source_audit_log(_admin: Administrator, session: Database) -> list[SourceAuditLog]:
    return list(
        session.scalars(
            select(SourceAuditLog).order_by(SourceAuditLog.created_at.desc()).limit(500)
        )
    )
