import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.orm import Session

from api.auth import AuthenticatedUser
from api.models import Job, JobFilter, JobMatch, MatchStatus, Profile


async def test_profile_bootstrap_and_filter_crud(api_client: AsyncClient) -> None:
    profile_response = await api_client.get("/users/me")
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == "student@example.com"

    create_response = await api_client.post(
        "/filters",
        json={
            "name": "Backend internships",
            "role_keywords": [" backend ", "backend", "software"],
            "terms": ["Summer 2027"],
        },
    )
    assert create_response.status_code == 201
    assert create_response.headers["location"].startswith("/filters/")
    created = create_response.json()
    assert created["role_keywords"] == ["backend", "software"]

    update_response = await api_client.patch(f"/filters/{created['id']}", json={"active": False})
    assert update_response.status_code == 200
    assert update_response.json()["active"] is False

    delete_response = await api_client.delete(f"/filters/{created['id']}")
    assert delete_response.status_code == 204
    assert (await api_client.get("/filters")).json() == []


async def test_filter_ownership_returns_not_found(
    api_client: AsyncClient, db_session: Session
) -> None:
    other = Profile(id=uuid.uuid4(), email="other@example.com")
    db_session.add(other)
    db_session.commit()

    other_filter = JobFilter(profile_id=other.id, name="Private")
    db_session.add(other_filter)
    db_session.commit()

    response = await api_client.get(f"/filters/{other_filter.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_match_applied_and_analytics(
    api_client: AsyncClient,
    db_session: Session,
    authenticated_user: AuthenticatedUser,
) -> None:
    now = datetime.now(UTC)
    profile = Profile(id=authenticated_user.id, email=authenticated_user.email)
    job = Job(
        company="Example",
        normalized_company="example",
        title="Software Intern",
        normalized_title="software intern",
        canonical_fingerprint="f" * 64,
        first_seen_at=now,
        last_seen_at=now,
    )
    match = JobMatch(profile=profile, job=job, reasons=[{"kind": "role", "value": "software"}])
    db_session.add(match)
    db_session.commit()

    response = await api_client.patch(
        f"/matches/{match.id}", json={"status": MatchStatus.APPLIED.value}
    )
    summary = await api_client.get("/analytics/summary")

    assert response.status_code == 200
    assert response.json()["applied_at"] is not None
    assert summary.json()["matched_count"] == 1
    assert summary.json()["applied_count"] == 1


async def test_invalid_cursor_uses_standard_error(api_client: AsyncClient) -> None:
    response = await api_client.get("/jobs", params={"cursor": "not-a-cursor"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "invalid_cursor", "message": "Pagination cursor is invalid"}
    }
