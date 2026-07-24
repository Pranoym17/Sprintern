import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict

from api.ingestion.contracts import RawSourceJob
from api.locations import coordinates_for_location
from api.models import JobSourceName, WorkMode

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "ref",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}
MAX_RAW_METADATA_BYTES = 100_000
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class NormalizedJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: JobSourceName
    source_key: str
    external_id: str
    company: str
    normalized_company: str
    title: str
    normalized_title: str
    location: str | None
    normalized_location: str | None
    term: str | None
    description: str | None
    work_mode: WorkMode
    source_url: str | None
    apply_url: str
    posted_at: datetime | None
    deadline_at: datetime | None
    raw_metadata: dict[str, object]
    canonical_fingerprint: str
    latitude: float | None
    longitude: float | None


def normalize_text(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def clean_external_text(value: str) -> str:
    """Remove control characters that should never reach logs, HTML, or PostgreSQL."""
    return CONTROL_CHARACTERS.sub("", value).strip()


def canonicalize_url(value: str) -> str:
    parts = urlsplit(value)
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query)
            if key.lower() not in TRACKING_PARAMETERS
        )
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ""))


def normalize_job(source: JobSourceName, source_key: str, raw: RawSourceJob) -> NormalizedJob:
    company = clean_external_text(raw.company)
    title = clean_external_text(raw.title)
    location = clean_external_text(raw.location) if raw.location else None
    term = clean_external_text(raw.term) if raw.term else None
    description = clean_external_text(raw.description) if raw.description else None
    if not company or not title:
        raise ValueError("company and title must contain visible text")
    normalized_company = normalize_text(company)
    normalized_title = normalize_text(title)
    normalized_location = normalize_text(location) if location else None
    fingerprint_input = "|".join(
        [
            normalized_company,
            normalized_title,
            normalized_location or "",
            normalize_text(term or ""),
        ]
    )
    metadata = json.loads(json.dumps(raw.raw_metadata, default=str))
    if len(json.dumps(metadata).encode()) > MAX_RAW_METADATA_BYTES:
        raise ValueError("raw metadata exceeds 100 KB")
    posted_at = raw.posted_at
    if posted_at and posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    deadline_at = raw.deadline_at
    if deadline_at and deadline_at.tzinfo is None:
        deadline_at = deadline_at.replace(tzinfo=UTC)
    coordinates = coordinates_for_location(raw.location)
    return NormalizedJob(
        source=source,
        source_key=source_key,
        external_id=clean_external_text(raw.external_id),
        company=company,
        normalized_company=normalized_company,
        title=title,
        normalized_title=normalized_title,
        location=location,
        normalized_location=normalized_location,
        term=term,
        description=description,
        work_mode=raw.work_mode,
        source_url=canonicalize_url(str(raw.source_url)) if raw.source_url else None,
        apply_url=canonicalize_url(str(raw.apply_url)),
        posted_at=posted_at,
        deadline_at=deadline_at,
        raw_metadata=metadata,
        canonical_fingerprint=hashlib.sha256(fingerprint_input.encode()).hexdigest(),
        latitude=coordinates[0] if coordinates else None,
        longitude=coordinates[1] if coordinates else None,
    )


def utc_now() -> datetime:
    return datetime.now(UTC)
