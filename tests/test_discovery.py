import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.auth import AuthenticatedUser
from api.models import Job, JobMatch, JobSource, JobSourceName, Profile


def discovery_job(db_session: Session, user: AuthenticatedUser) -> Job:
    now = datetime.now(UTC)
    profile = Profile(id=user.id, email=user.email)
    job = Job(
        company="Phase Seventeen Robotics",
        normalized_company="phase seventeen robotics",
        title="Software Engineer Intern",
        normalized_title="software engineer intern",
        location="Toronto, Canada",
        normalized_location="toronto canada",
        canonical_fingerprint=uuid.uuid4().hex.ljust(64, "0"),
        first_seen_at=now,
        last_seen_at=now,
    )
    job.sources.append(
        JobSource(
            source=JobSourceName.GITHUB_REPO,
            source_key="phase17/test:README.md",
            external_id=uuid.uuid4().hex,
            apply_url="https://employer.example/phase17",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    match = JobMatch(
        profile=profile,
        job=job,
        reasons=[{"dimensions": {"role": "software engineer"}}],
    )
    db_session.add_all([profile, job, match])
    db_session.commit()
    return job


async def test_search_interactions_reports_and_private_share(
    api_client: httpx.AsyncClient,
    db_session: Session,
    authenticated_user: AuthenticatedUser,
) -> None:
    job = discovery_job(db_session, authenticated_user)

    search = await api_client.get("/matches?query=robtoics&sort=relevance")
    assert search.status_code == 200
    assert [item["job"]["id"] for item in search.json()["items"]] == [str(job.id)]

    bookmark = await api_client.patch(
        f"/jobs/{job.id}/interaction", json={"bookmarked": True}
    )
    assert bookmark.status_code == 200
    assert bookmark.json()["bookmarked_at"] is not None
    report = await api_client.post(f"/jobs/{job.id}/reports", json={"reason": "closed"})
    assert report.status_code == 201

    shared = await api_client.post(
        f"/jobs/{job.id}/shares", json={"expires_in_hours": 1}
    )
    assert shared.status_code == 201
    token = shared.json()["url"].rsplit("/", 1)[-1]
    public = await api_client.get(f"/shared/jobs/{token}")
    assert public.status_code == 200
    assert public.json()["job"]["company"] == "Phase Seventeen Robotics"
    assert "reasons" not in public.json()


async def test_discovery_mutations_are_ownership_scoped(
    api_client: httpx.AsyncClient, db_session: Session
) -> None:
    other = AuthenticatedUser(id=uuid.uuid4(), email="other@example.com")
    job = discovery_job(db_session, other)

    response = await api_client.patch(
        f"/jobs/{job.id}/interaction", json={"hidden": True}
    )

    assert response.status_code == 404


def test_search_query_plan_can_use_full_text_index(db_session: Session) -> None:
    db_session.execute(text("SET LOCAL enable_seqscan = off"))
    plan = "\n".join(
        row[0]
        for row in db_session.execute(
            text(
                "EXPLAIN SELECT id FROM jobs WHERE "
                "to_tsvector('english', title || ' ' || company || ' ' || coalesce(location, '')) "
                "@@ websearch_to_tsquery('english', 'software')"
            )
        )
    )

    assert "ix_jobs_discovery_fts" in plan
