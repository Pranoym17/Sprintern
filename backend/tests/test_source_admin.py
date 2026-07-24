import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import AnyHttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from api.auth import AuthenticatedUser
from api.ingestion import PollBatch, RawSourceJob
from api.ingestion.http import SourceHTTPError
from api.ingestion.service import IngestionService
from api.models import (
    JobSource,
    JobSourceName,
    ParserAlert,
    PollCompleteness,
    SourceAuditLog,
)
from api.scheduler.source_registry import (
    load_runtime_source_config,
    seed_source_configurations,
)
from api.settings import settings


class PreviewAdapter:
    source = JobSourceName.GITHUB_REPO
    source_key = "admin/repository:README.md"

    async def fetch(self, _cursor: dict[str, Any]) -> PollBatch:
        return PollBatch(
            records=[
                RawSourceJob(
                    external_id="preview-1",
                    company="Preview Company",
                    title="Software Intern",
                    location="Toronto, Canada",
                    term="Summer 2027",
                    apply_url=AnyHttpUrl("https://jobs.example.com/apply/1"),
                )
            ],
            completeness=PollCompleteness.INCREMENTAL,
            next_cursor={"sha": "preview"},
            detected_schema="github_markdown_table:v1",
        )


class FailingAdapter:
    source = JobSourceName.GITHUB_REPO
    source_key = "broken/repository:README.md"

    async def fetch(self, _cursor: dict[str, Any]) -> PollBatch:
        raise SourceHTTPError("GitHub file has no supported internship table schema")


class EmptyChangedAdapter:
    source = JobSourceName.GITHUB_REPO
    source_key = "empty/repository:README.md"

    async def fetch(self, _cursor: dict[str, Any]) -> PollBatch:
        return PollBatch(
            records=[],
            completeness=PollCompleteness.INCREMENTAL,
            next_cursor={"sha": "new"},
        )


@pytest.fixture
def source_factory(db_session: Session) -> sessionmaker[Session]:
    return sessionmaker(
        bind=db_session.get_bind(),
        class_=Session,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


async def test_source_admin_requires_allowlisted_supabase_user(
    api_client: httpx.AsyncClient,
    authenticated_user: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "admin_user_ids_value", "")
    denied = await api_client.get("/admin/sources")
    assert denied.status_code == 403

    monkeypatch.setattr(settings, "admin_user_ids_value", str(authenticated_user.id))
    allowed = await api_client.get("/admin/me")
    assert allowed.status_code == 200
    assert allowed.json() == {"administrator": True}


async def test_admin_preview_is_read_only_and_required_before_enable(
    api_client: httpx.AsyncClient,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.routes import admin_sources

    monkeypatch.setattr(settings, "admin_user_ids_value", str(authenticated_user.id))
    monkeypatch.setattr(admin_sources, "build_adapter", lambda *_: PreviewAdapter())
    created = await api_client.post(
        "/admin/sources",
        json={
            "owner": "admin",
            "repository": "repository",
            "branch": "main",
            "path": "README.md",
            "poll_minutes": 60,
            "jitter_seconds": 30,
            "default_term": None,
            "parser_schema": "github_markdown_table",
            "parser_version": "1",
        },
    )
    assert created.status_code == 201
    source_id = created.json()["id"]
    premature = await api_client.post(
        f"/admin/sources/{source_id}/state",
        json={"enabled": True, "confirmation": "ENABLE"},
    )
    assert premature.status_code == 409
    jobs_before = db_session.scalar(select(func.count(JobSource.id)))
    preview = await api_client.post(f"/admin/sources/{source_id}/preview")
    jobs_after = db_session.scalar(select(func.count(JobSource.id)))
    assert preview.status_code == 200
    assert preview.json()["accepted"] == 1
    assert preview.json()["validation_passed"] is True
    assert preview.json()["detected_table_schema"] == "github_markdown_table:v1"
    assert preview.json()["application_domains"] == ["jobs.example.com"]
    assert jobs_after == jobs_before

    enabled = await api_client.post(
        f"/admin/sources/{source_id}/state",
        json={"enabled": True, "confirmation": "ENABLE"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert (
        db_session.scalar(
            select(func.count(SourceAuditLog.id)).where(
                SourceAuditLog.source_configuration_id == uuid.UUID(source_id)
            )
        )
        == 3
    )


async def test_admin_cannot_enable_a_preview_with_no_valid_rows(
    api_client: httpx.AsyncClient,
    authenticated_user: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api.routes import admin_sources

    monkeypatch.setattr(settings, "admin_user_ids_value", str(authenticated_user.id))
    monkeypatch.setattr(admin_sources, "build_adapter", lambda *_: EmptyChangedAdapter())
    created = await api_client.post(
        "/admin/sources",
        json={"owner": "empty", "repository": "repository"},
    )
    source_id = created.json()["id"]

    preview = await api_client.post(f"/admin/sources/{source_id}/preview")
    assert preview.status_code == 200
    assert preview.json()["validation_passed"] is False
    assert preview.json()["validation_errors"] == [
        "No valid internship rows were detected"
    ]

    enabled = await api_client.post(
        f"/admin/sources/{source_id}/state",
        json={"enabled": True, "confirmation": "ENABLE"},
    )
    assert enabled.status_code == 409


def test_toml_only_seeds_an_empty_database(
    db_session: Session,
    source_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "sources.toml"
    config_path.write_text(
        '[[github]]\nowner="seed"\nrepository="repo"\nenabled=true\npoll_minutes=45\n',
        encoding="utf-8",
    )
    assert seed_source_configurations(db_session, config_path) == 1
    runtime = load_runtime_source_config(source_factory, config_path)
    assert runtime.enabled_github[0].owner == "seed"
    assert runtime.enabled_github[0].poll_minutes == 45
    assert seed_source_configurations(db_session, config_path) == 0


async def test_parser_alerts_cover_missing_tables_and_zero_acceptance(
    db_session: Session,
    source_factory: sessionmaker[Session],
) -> None:
    service = IngestionService(source_factory)
    with pytest.raises(SourceHTTPError):
        await service.run(FailingAdapter())
    await service.run(EmptyChangedAdapter())
    alerts = list(db_session.scalars(select(ParserAlert).where(ParserAlert.resolved_at.is_(None))))
    assert {alert.source_key for alert in alerts} == {
        "broken/repository:README.md",
        "empty/repository:README.md",
    }
