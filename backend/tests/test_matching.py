import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.matching import MatchingService, canonical_term, classify_internship, match_filter
from api.models import (
    InternshipStatus,
    Job,
    JobFilter,
    JobMatch,
    JobStatus,
    Profile,
    WorkMode,
)


def job(title: str, **values: object) -> Job:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "company": "Example",
        "normalized_company": "example",
        "title": title,
        "normalized_title": title.lower(),
        "canonical_fingerprint": uuid.uuid4().hex.ljust(64, "0"),
        "first_seen_at": now,
        "last_seen_at": now,
    }
    defaults.update(values)
    return Job(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        ("Software Engineering Intern", None, InternshipStatus.CONFIRMED),
        ("Data Science Co-op", None, InternshipStatus.CONFIRMED),
        ("Senior Software Engineer", None, InternshipStatus.REJECTED),
        ("Senior Engineering Intern", None, InternshipStatus.AMBIGUOUS),
        (
            "Early Career Program",
            "Candidates must be currently enrolled in university.",
            InternshipStatus.CONFIRMED,
        ),
        ("Early Career Program", None, InternshipStatus.AMBIGUOUS),
    ],
)
def test_internship_classification(
    title: str, description: str | None, expected: InternshipStatus
) -> None:
    assert classify_internship(title, description) == expected


def test_filter_uses_and_between_dimensions_and_aliases() -> None:
    profile_id = uuid.uuid4()
    candidate = job(
        "Software Engineering Intern",
        location="Montréal, QC",
        term="2027 Summer",
        work_mode=WorkMode.HYBRID,
    )
    job_filter = JobFilter(
        id=uuid.uuid4(),
        profile_id=profile_id,
        name="SWE Montreal",
        role_keywords=["swe"],
        location_keywords=["Montreal"],
        terms=["Summer 2027"],
        work_mode=WorkMode.HYBRID,
    )

    result = match_filter(candidate, job_filter)

    assert result is not None
    assert result.reasons["dimensions"] == {
        "role": "software engineering",
        "location": "montreal",
        "term": "summer 2027",
        "work_mode": "hybrid",
    }
    assert canonical_term("2027 Fall") == "fall 2027"


def test_keyword_boundaries_prevent_partial_word_matches() -> None:
    candidate = job("Communications Intern")
    job_filter = JobFilter(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        name="C language",
        role_keywords=["c"],
    )

    assert match_filter(candidate, job_filter) is None


def test_unrestricted_filter_choices_cover_unknown_roles_locations_and_terms() -> None:
    candidate = job(
        "Photonics Research Intern",
        location="Dresden, Germany",
        term=None,
    )
    job_filter = JobFilter(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        name="Everything",
        role_keywords=["Any role or field"],
        location_keywords=["Anywhere"],
        terms=[],
        work_mode=WorkMode.ANY,
    )

    assert match_filter(candidate, job_filter) is not None
    assert canonical_term("Spring 2027") == "winter 2027"
    assert canonical_term("Autumn 2027") == "fall 2027"


def test_matching_service_aggregates_filters_and_is_idempotent(db_session: Session) -> None:
    profile = Profile(id=uuid.uuid4(), email="student@example.com")
    profile.filters.extend(
        [
            JobFilter(name="Software", role_keywords=["software"]),
            JobFilter(name="Intern title", role_keywords=["intern"]),
        ]
    )
    candidate = job("Software Engineering Intern")
    db_session.add_all([profile, candidate])
    db_session.flush()
    service = MatchingService()

    first_count = service.match_all(db_session)
    db_session.flush()
    second_count = service.match_all(db_session)
    db_session.flush()
    matches = list(db_session.scalars(select(JobMatch)))

    assert first_count == 1
    assert second_count == 0
    assert len(matches) == 1
    assert len(matches[0].reasons) == 2
    assert candidate.internship_status == InternshipStatus.CONFIRMED


def test_profile_backfill_can_limit_matches_to_last_seven_days(db_session: Session) -> None:
    now = datetime.now(UTC)
    profile = Profile(id=uuid.uuid4(), email="recent@example.com")
    profile.filters.append(JobFilter(name="Software", role_keywords=["software"]))
    recent = job("Software Engineering Intern", first_seen_at=now - timedelta(days=2))
    old = job("Software Developer Intern", first_seen_at=now - timedelta(days=8))
    db_session.add_all([profile, recent, old])
    db_session.flush()

    created = MatchingService().match_profile(
        db_session,
        profile.id,
        seen_since=now - timedelta(days=7),
    )
    db_session.flush()

    matches = list(db_session.scalars(select(JobMatch)))
    assert created == 1
    assert [match.job_id for match in matches] == [recent.id]


def test_ambiguous_and_inactive_jobs_do_not_create_matches(db_session: Session) -> None:
    profile = Profile(id=uuid.uuid4(), email="student@example.com")
    profile.filters.append(JobFilter(name="Any role"))
    ambiguous = job("Early Career Program")
    expired = job("Software Intern", status=JobStatus.EXPIRED)
    db_session.add_all([profile, ambiguous, expired])
    db_session.flush()

    MatchingService().match_all(db_session)
    db_session.flush()

    assert list(db_session.scalars(select(JobMatch))) == []
    assert ambiguous.internship_status == InternshipStatus.AMBIGUOUS
