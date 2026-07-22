import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.ingestion import RawSourceJob
from api.ingestion.normalization import normalize_job
from api.ingestion.persistence import JobPersister, PersistenceOutcome
from api.matching.matcher import match_filter
from api.models import ExclusionType, FilterExclusion, Job, JobFilter, JobSourceName, WorkMode


def test_aliases_unrestricted_locations_and_exclusions_are_explainable() -> None:
    job = Job(
        company="Example Labs",
        normalized_company="example labs",
        title="Software Development Engineer Intern",
        normalized_title="software development engineer intern",
        location="Vancouver, Canada",
        normalized_location="vancouver canada",
        work_mode=WorkMode.REMOTE,
        canonical_fingerprint="a" * 64,
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    job_filter = JobFilter(
        id=uuid.uuid4(),
        name="SDE anywhere",
        role_keywords=["SDE"],
        location_keywords=["Everywhere"],
        remote_only=True,
        work_mode=WorkMode.ANY,
    )
    job_filter.exclusions = []

    result = match_filter(job, job_filter)

    assert result is not None
    assert result.reasons["dimensions"]["role"] == "software development engineer"
    assert result.reasons["dimensions"]["work_mode"] == "remote"
    job_filter.exclusions = [
        FilterExclusion(
            kind=ExclusionType.COMPANY,
            value="Example",
            normalized_value="example",
        )
    ]
    assert match_filter(job, job_filter) is None


def test_cross_repository_dedup_and_incomplete_title_state(db_session: Session) -> None:
    now = datetime.now(UTC)
    first_raw = RawSourceJob(
        external_id="first",
        company="Phase 16 Company",
        title="Software Engineer Intern…",
        location="Toronto, ON",
        apply_url="https://employer.example/apply",
    )
    second_raw = first_raw.model_copy(update={"external_id": "second"})
    first = normalize_job(JobSourceName.GITHUB_REPO, f"phase16-{uuid.uuid4()}", first_raw)
    second = normalize_job(JobSourceName.GITHUB_REPO, f"phase16-{uuid.uuid4()}", second_raw)
    persister = JobPersister()

    assert persister.persist(db_session, first, now) == PersistenceOutcome.CREATED
    assert persister.persist(db_session, second, now) == PersistenceOutcome.DUPLICATE
    db_session.flush()
    job = (
        db_session.query(Job)
        .filter(Job.canonical_fingerprint == first.canonical_fingerprint)
        .one()
    )

    assert job.title_incomplete is True
    assert len(job.sources) == 2


def test_application_tables_are_not_publicly_readable(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "SELECT relname, relrowsecurity FROM pg_class "
            "WHERE relname IN ('applications', 'job_interactions', 'share_links')"
        )
    ).all()
    assert {name for name, enabled in rows if enabled} == {
        "applications",
        "job_interactions",
        "share_links",
    }
