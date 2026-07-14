import re
import uuid
from dataclasses import dataclass
from typing import Any

from api.ingestion.normalization import normalize_text
from api.models import Job, JobFilter, WorkMode

MATCHER_VERSION = "keyword-v1"
ROLE_ALIASES = {
    "swe": ("software engineer", "software engineering"),
    "ml": ("machine learning",),
    "ai": ("artificial intelligence",),
    "frontend": ("front end", "frontend"),
    "backend": ("back end", "backend"),
}
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

    if job_filter.location_keywords:
        location = normalize_text(job.location or "")
        location_match = next(
            (
                normalize_text(keyword)
                for keyword in job_filter.location_keywords
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
        },
    )
