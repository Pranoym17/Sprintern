import re
import uuid
from dataclasses import dataclass
from typing import Any

from api.ingestion.normalization import normalize_text
from api.models import ExclusionType, Job, JobFilter, WorkMode

MATCHER_VERSION = "keyword-v2"
ROLE_ALIASES = {
    "swe": ("software engineer", "software engineering", "software developer"),
    "sde": ("software developer", "software development engineer", "software engineer"),
    "pm": ("product manager", "product management"),
    "qa": ("quality assurance", "test engineer", "software tester"),
    "devops": ("devops", "site reliability", "platform engineer", "sre"),
    "ml": ("machine learning", "ml engineer"),
    "ds": ("data scientist", "data science"),
    "ai": ("artificial intelligence",),
    "frontend": ("front end", "frontend"),
    "backend": ("back end", "backend"),
}
UNRESTRICTED_LOCATIONS = {"all", "any", "everywhere"}
SEASONS = ("winter", "spring", "summer", "fall", "autumn")


@dataclass(frozen=True)
class FilterMatch:
    filter_id: uuid.UUID
    reasons: dict[str, Any]


def _matches_phrase(text: str, keyword: str) -> str | None:
    normalized_keyword = normalize_text(keyword)
    candidates = (normalized_keyword, *ROLE_ALIASES.get(normalized_keyword, ()))
    for candidate in candidates:
        if f" {candidate} " in f" {text} ":
            return candidate
    return None


def canonical_term(value: str | None) -> str | None:
    normalized = normalize_text(value or "")
    year = re.search(r"\b20\d{2}\b", normalized)
    season = next((item for item in SEASONS if f" {item} " in f" {normalized} "), None)
    if not year and not season:
        return normalized or None
    return " ".join(item for item in (season, year.group(0) if year else None) if item)


def match_filter(job: Job, job_filter: JobFilter) -> FilterMatch | None:
    if job_filter.active is False:
        return None
    dimensions: dict[str, str] = {}
    excluded: list[dict[str, str]] = []

    # Exclusions are hard gates before positive scoring. Recording the exact gate keeps
    # previews and debugging explainable even as aliases expand over time.
    searchable = normalize_text(" ".join((job.title, job.description or "")))
    company = normalize_text(job.company)
    location = normalize_text(job.location or "")
    for exclusion in job_filter.exclusions:
        target = {
            ExclusionType.KEYWORD: searchable,
            ExclusionType.COMPANY: company,
            ExclusionType.LOCATION: location,
        }[exclusion.kind]
        if _matches_phrase(target, exclusion.normalized_value):
            excluded.append({"kind": exclusion.kind.value, "value": exclusion.value})
    if excluded:
        return None

    if job_filter.remote_only and job.work_mode != WorkMode.REMOTE:
        return None
    if job_filter.remote_only:
        dimensions["work_mode"] = WorkMode.REMOTE.value

    if job_filter.role_keywords:
        title = normalize_text(job.title)
        role = next(
            (
                matched
                for keyword in job_filter.role_keywords
                if (matched := _matches_phrase(title, keyword))
            ),
            None,
        )
        if role is None:
            return None
        dimensions["role"] = role

    restricted_locations = [
        value
        for value in job_filter.location_keywords
        if normalize_text(value) not in UNRESTRICTED_LOCATIONS
    ]
    if restricted_locations:
        location_match = next(
            (
                normalize_text(keyword)
                for keyword in restricted_locations
                if _matches_phrase(location, keyword)
                or (normalize_text(keyword) == "remote" and job.work_mode == WorkMode.REMOTE)
            ),
            None,
        )
        if location_match is None:
            return None
        dimensions["location"] = location_match

    if job_filter.terms:
        job_term = canonical_term(job.term)
        term_match = next(
            (term for term in job_filter.terms if canonical_term(term) == job_term), None
        )
        if term_match is None:
            return None
        dimensions["term"] = canonical_term(term_match) or term_match

    if job_filter.work_mode != WorkMode.ANY:
        if job.work_mode != job_filter.work_mode:
            return None
        dimensions["work_mode"] = job_filter.work_mode.value

    return FilterMatch(
        filter_id=job_filter.id,
        reasons={
            "filter_id": str(job_filter.id),
            "filter_name": job_filter.name,
            "matcher_version": MATCHER_VERSION,
            "dimensions": dimensions,
            "positive": [{"kind": kind, "value": value} for kind, value in dimensions.items()],
            "negative": excluded,
        },
    )
