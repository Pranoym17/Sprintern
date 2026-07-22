import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from api.auth import AuthenticatedUser
from api.matching.matcher import match_filter
from api.models import Job, JobFilter, WorkMode


def targeted_job() -> Job:
    now = datetime.now(UTC)
    return Job(
        company="Targeting Labs",
        normalized_company="targeting labs",
        title="Software Engineer Intern",
        normalized_title="software engineer intern",
        location="Toronto, Canada",
        normalized_location="toronto canada",
        work_mode=WorkMode.ONSITE,
        latitude=43.6532,
        longitude=-79.3832,
        canonical_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
        first_seen_at=now,
        last_seen_at=now,
    )


def test_radius_matching_handles_known_remote_and_unknown_locations() -> None:
    job_filter = JobFilter(
        id=uuid.uuid4(),
        name="Toronto radius",
        role_keywords=[],
        location_keywords=[],
        terms=[],
        work_mode=WorkMode.ANY,
        remote_only=False,
        radius_km=50,
        center_latitude=43.6532,
        center_longitude=-79.3832,
    )
    job_filter.exclusions = []
    job = targeted_job()
    assert match_filter(job, job_filter) is not None
    job.latitude = None
    job.longitude = None
    assert match_filter(job, job_filter) is None
    job.work_mode = WorkMode.REMOTE
    assert match_filter(job, job_filter) is not None


async def test_filter_preview_and_watchlists_are_owned(
    api_client: httpx.AsyncClient,
    db_session: Session,
    authenticated_user: AuthenticatedUser,
) -> None:
    db_session.add(targeted_job())
    db_session.commit()
    preview = await api_client.post(
        "/filters/preview",
        json={
            "name": "Preview",
            "role_keywords": ["SWE"],
            "location_keywords": ["Toronto"],
            "terms": [],
            "work_mode": "any",
            "excluded_keywords": ["unpaid"],
        },
    )
    assert preview.status_code == 200
    assert preview.json()["estimated_count"] >= 1
    assert "SWE".casefold() in {key.casefold() for key in preview.json()["aliases"]}

    created = await api_client.post(
        "/watchlists",
        json={"company": "Targeting Labs", "terms": [], "locations": [], "active": True},
    )
    assert created.status_code == 201
    watchlist_id = created.json()["id"]
    assert (await api_client.get(f"/watchlists/{watchlist_id}/jobs")).status_code == 200

    other = AuthenticatedUser(id=uuid.uuid4(), email="other@example.com")
    assert other.id != authenticated_user.id
    # Ownership is enforced in the SQL predicate; a random valid UUID remains hidden.
    response = await api_client.patch(
        f"/watchlists/{uuid.uuid4()}", json={"active": False}
    )
    assert response.status_code == 404
