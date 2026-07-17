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


async def test_matches_filter_and_counts_are_authoritative(
    api_client: AsyncClient,
    db_session: Session,
    authenticated_user: AuthenticatedUser,
) -> None:
    now = datetime.now(UTC)
    profile = Profile(id=authenticated_user.id, email=authenticated_user.email)
    statuses = [MatchStatus.MATCHED, MatchStatus.APPLIED, MatchStatus.DISMISSED]
    for index, match_status in enumerate(statuses):
        job = Job(
            company=f"Company {index}",
            normalized_company=f"company {index}",
            title="Software Intern",
            normalized_title="software intern",
            canonical_fingerprint=str(index) * 64,
            first_seen_at=now,
            last_seen_at=now,
        )
        profile.matches.append(JobMatch(job=job, status=match_status, reasons=[]))
    db_session.add(profile)
    db_session.commit()

    response = await api_client.get("/matches", params={"status": "applied", "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert [item["status"] for item in body["items"]] == ["applied"]
    assert body["counts"] == {"all": 3, "matched": 1, "applied": 1, "dismissed": 1}


async def test_invalid_cursor_uses_standard_error(api_client: AsyncClient) -> None:
    response = await api_client.get("/jobs", params={"cursor": "not-a-cursor"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "invalid_cursor", "message": "Pagination cursor is invalid"}
    }


async def test_pagination_rejects_out_of_bounds_limits(api_client: AsyncClient) -> None:
    for path in ("/jobs", "/matches"):
        assert (await api_client.get(path, params={"limit": 0})).status_code == 422
        assert (await api_client.get(path, params={"limit": 101})).status_code == 422


async def test_match_ownership_hides_other_users_records(
    api_client: AsyncClient, db_session: Session
) -> None:
    now = datetime.now(UTC)
    other = Profile(id=uuid.uuid4(), email="other@example.com")
    job = Job(
        company="Private",
        normalized_company="private",
        title="Software Intern",
        normalized_title="software intern",
        canonical_fingerprint="e" * 64,
        first_seen_at=now,
        last_seen_at=now,
    )
    match = JobMatch(profile=other, job=job, reasons=[])
    db_session.add(match)
    db_session.commit()

    assert (await api_client.get(f"/matches/{match.id}")).status_code == 404
    assert (
        await api_client.patch(f"/matches/{match.id}", json={"status": "applied"})
    ).status_code == 404


async def test_every_internal_route_requires_service_key(api_client: AsyncClient) -> None:
    requests = [
        ("GET", "/internal/sources/status", None),
        ("GET", "/internal/scheduler/status", None),
        ("POST", "/internal/notifications/dispatch", None),
        ("POST", "/internal/ingestion-runs", {}),
    ]
    for method, path, body in requests:
        response = await api_client.request(method, path, json=body)
        assert response.status_code in {401, 503}, path
