import re
import uuid
from dataclasses import dataclass
from typing import Any, cast

from api.ingestion.normalization import normalize_text
from api.locations import distance_km
from api.models import ExclusionType, Job, JobFilter, WorkMode

MATCHER_VERSION = "keyword-v2"
ROLE_ALIASES = {
    "software engineering": ("software engineer", "software developer", "software development"),
    "software developer": ("software engineer", "software development engineer"),
    "backend engineering": ("backend engineer", "back end engineer", "backend developer"),
    "frontend engineering": ("frontend engineer", "front end engineer", "frontend developer"),
    "full stack engineering": ("full stack engineer", "fullstack engineer", "full stack developer"),
    "mobile engineering": ("mobile engineer", "mobile developer"),
    "cloud engineering": ("cloud engineer", "cloud infrastructure"),
    "site reliability engineering": ("site reliability engineer", "sre"),
    "infrastructure engineering": ("infrastructure engineer", "platform engineer"),
    "systems engineering": ("systems engineer", "system engineer"),
    "network engineering": ("network engineer", "networking engineer"),
    "data science": ("data scientist", "data science"),
    "data analytics": ("data analyst", "analytics"),
    "data engineering": ("data engineer", "data platform"),
    "machine learning": ("machine learning", "ml engineer", "ml scientist"),
    "artificial intelligence": ("artificial intelligence", "ai engineer", "ai research"),
    "applied science": ("applied scientist", "applied science"),
    "research science": ("research scientist", "research science"),
    "computer vision": ("computer vision", "vision engineer", "vision scientist"),
    "natural language processing": ("natural language processing", "nlp engineer", "nlp scientist"),
    "embedded systems": ("embedded", "embedded systems"),
    "firmware engineering": ("firmware engineer", "firmware developer"),
    "hardware engineering": ("hardware engineer", "hardware design"),
    "electrical engineering": ("electrical engineer", "electronics engineer"),
    "asic engineering": ("asic", "asic engineer"),
    "fpga engineering": ("fpga", "fpga engineer"),
    "silicon engineering": ("silicon engineer", "silicon design"),
    "verification engineering": ("verification engineer", "design verification"),
    "mechanical engineering": ("mechanical engineer",),
    "product management": ("product manager", "product management"),
    "program management": ("program manager", "program management"),
    "project management": ("project manager", "project management"),
    "ux design": ("ux designer", "user experience designer"),
    "ui design": ("ui designer", "interface designer"),
    "product design": ("product designer", "product design"),
    "ux research": ("ux researcher", "user research"),
    "business analysis": ("business analyst", "business analysis"),
    "quantitative research": ("quantitative researcher", "quant researcher"),
    "quantitative trading": ("quantitative trader", "quant trader"),
    "human resources": ("human resources", "people operations", "hr intern"),
    "customer success": ("customer success", "customer experience"),
    "supply chain": ("supply chain", "logistics"),
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
UNRESTRICTED_ROLES = {"all", "any", "any role", "any role or field"}
UNRESTRICTED_LOCATIONS = {"all", "any", "anywhere", "any location", "everywhere"}
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
    if season == "spring":
        season = "winter"
    elif season == "autumn":
        season = "fall"
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

    if job_filter.radius_km is not None:
        center = (job_filter.center_latitude, job_filter.center_longitude)
        coordinates = (job.latitude, job.longitude)
        if job.work_mode == WorkMode.REMOTE:
            dimensions["radius"] = "remote"
        elif None in center or None in coordinates:
            return None
        else:
            distance = distance_km(
                (cast(float, center[0]), cast(float, center[1])),
                (cast(float, coordinates[0]), cast(float, coordinates[1])),
            )
            if distance > job_filter.radius_km:
                return None
            dimensions["radius"] = f"{round(distance)} km"

    restricted_roles = [
        value
        for value in job_filter.role_keywords
        if normalize_text(value) not in UNRESTRICTED_ROLES
    ]
    if restricted_roles:
        title = normalize_text(job.title)
        role = next(
            (
                matched
                for keyword in restricted_roles
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
