import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.models import (
    Job,
    JobFilter,
    JobMatch,
    JobSource,
    JobSourceName,
    NotificationCadence,
    NotificationChannel,
    NotificationDelivery,
    Profile,
)


def make_job(now: datetime, fingerprint: str = "a" * 64) -> Job:
    return Job(
        company="Example Corp",
        normalized_company="example corp",
        title="Software Engineering Intern",
        normalized_title="software engineering intern",
        location="Toronto, ON",
        normalized_location="toronto on",
        canonical_fingerprint=fingerprint,
        first_seen_at=now,
        last_seen_at=now,
    )


def test_profile_preferences_and_job_source_round_trip(db_session: Session) -> None:
    now = datetime.now(UTC)
    profile = Profile(id=uuid.uuid4(), email="student@example.com")
    profile.filters.append(
        JobFilter(
            name="Summer backend",
            role_keywords=["backend", "software"],
            location_keywords=["Toronto"],
            terms=["Summer 2027"],
        )
    )
    job = make_job(now)
    job.sources.append(
        JobSource(
            source=JobSourceName.GREENHOUSE,
            source_key="example",
            external_id="example-123",
            source_url="https://example.com/jobs/123",
            apply_url="https://example.com/jobs/123/apply",
            raw_metadata={"department": "Engineering"},
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    db_session.add_all([profile, job])
    db_session.commit()

    assert profile.filters[0].role_keywords == ["backend", "software"]
    assert job.sources[0].raw_metadata == {"department": "Engineering"}
    assert job.first_seen_at.tzinfo is not None


def test_source_identity_is_unique(db_session: Session) -> None:
    now = datetime.now(UTC)
    first_job = make_job(now, "a" * 64)
    second_job = make_job(now, "b" * 64)
    for job in (first_job, second_job):
        job.sources.append(
            JobSource(
                source=JobSourceName.LEVER,
                source_key="example",
                external_id="duplicate-id",
                apply_url="https://example.com/apply",
                first_seen_at=now,
                last_seen_at=now,
            )
        )
    db_session.add_all([first_job, second_job])

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_match_and_delivery_are_idempotent(db_session: Session) -> None:
    now = datetime.now(UTC)
    profile = Profile(id=uuid.uuid4(), email="student@example.com")
    job = make_job(now)
    match = JobMatch(profile=profile, job=job, reasons=[{"kind": "role", "value": "software"}])
    match.deliveries.append(
        NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            cadence=NotificationCadence.INSTANT,
            recipient="student@example.com",
            idempotency_key="first",
        )
    )
    match.deliveries.append(
        NotificationDelivery(
            channel=NotificationChannel.EMAIL,
            cadence=NotificationCadence.INSTANT,
            recipient="student@example.com",
            idempotency_key="second",
        )
    )
    db_session.add(match)

    with pytest.raises(IntegrityError):
        db_session.commit()
