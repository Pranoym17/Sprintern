import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.auth import AuthenticatedUser
from api.models import ApplicationEvent, Job, JobSource, JobSourceName, ReminderEvent


def tracker_job(db_session: Session) -> Job:
    now = datetime.now(UTC)
    job = Job(
        company="Tracker Systems",
        normalized_company="tracker systems",
        title="Backend Engineer Intern",
        normalized_title="backend engineer intern",
        location="Toronto, Canada",
        normalized_location="toronto canada",
        canonical_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
        first_seen_at=now,
        last_seen_at=now,
    )
    job.sources.append(
        JobSource(
            source=JobSourceName.GITHUB_REPO,
            source_key="tracker/test:README.md",
            external_id=uuid.uuid4().hex,
            apply_url="https://employer.example/apply",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    db_session.add(job)
    db_session.commit()
    return job


async def test_tracker_preserves_timeline_and_idempotent_reminders(
    api_client: httpx.AsyncClient,
    db_session: Session,
    authenticated_user: AuthenticatedUser,
) -> None:
    job = tracker_job(db_session)
    created = await api_client.post("/applications", json={"job_id": str(job.id)})
    assert created.status_code == 201
    application_id = created.json()["id"]
    assert created.json()["stage"] == "saved"

    due_at = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    payload = {"stage": "applied", "follow_up_at": due_at, "notes": "Applied directly"}
    first = await api_client.patch(f"/applications/{application_id}", json=payload)
    second = await api_client.patch(f"/applications/{application_id}", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["applied_at"] is not None
    assert len(first.json()["events"]) == 2
    reminder_count = db_session.scalar(
        select(func.count(ReminderEvent.id)).where(
            ReminderEvent.application_id == uuid.UUID(application_id)
        )
    )
    assert reminder_count == 1

    event_id = first.json()["events"][0]["id"]
    corrected = await api_client.post(
        f"/applications/{application_id}/events/{event_id}/corrections",
        json={"note": "Imported date was approximate"},
    )
    assert corrected.status_code == 200
    assert any(event["corrected_event_id"] == event_id for event in corrected.json()["events"])


async def test_tracker_enforces_ownership(
    api_client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    tracker_job(db_session)
    response = await api_client.patch(f"/applications/{uuid.uuid4()}", json={"stage": "offer"})
    assert response.status_code == 404


async def test_csv_import_preview_retry_and_exports_are_user_scoped(
    api_client: httpx.AsyncClient,
    db_session: Session,
    authenticated_user: AuthenticatedUser,
) -> None:
    csv_text = (
        "Company,Role,Stage,Applied\nImport Co,Platform Intern,applied,2026-07-20T12:00:00Z\n"
    )
    payload = {
        "csv_text": csv_text,
        "mapping": {
            "company": "Company",
            "title": "Role",
            "stage": "Stage",
            "applied_at": "Applied",
        },
        "dry_run": True,
    }
    preview = await api_client.post("/imports/applications/csv", json=payload)
    assert preview.status_code == 200
    assert preview.json()["valid_rows"] == 1
    assert preview.json()["imported_rows"] == 0

    payload["dry_run"] = False
    imported = await api_client.post("/imports/applications/csv", json=payload)
    repeated = await api_client.post("/imports/applications/csv", json=payload)
    assert imported.json()["imported_rows"] == 1
    assert repeated.json()["duplicate_rows"] == 1

    applications = await api_client.get("/exports/applications.csv")
    timeline = await api_client.get("/exports/timeline.csv")
    assert applications.status_code == timeline.status_code == 200
    assert "Import Co" in applications.text
    assert "imported" in timeline.text
    assert (
        db_session.scalar(
            select(func.count(ApplicationEvent.id)).where(
                ApplicationEvent.profile_id == authenticated_user.id
            )
        )
        == 1
    )


async def test_weekly_goal_can_be_configured(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.put(
        "/goals/weekly",
        json={"target": 8, "reminders_enabled": True, "streaks_enabled": False},
    )
    assert response.status_code == 200
    assert response.json()["target"] == 8
    assert response.json()["reminders_enabled"] is True
    assert response.json()["streaks_enabled"] is False
