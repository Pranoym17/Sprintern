import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict

from api.ingestion.contracts import RawSourceJob
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


class NormalizedJob(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: JobSourceName
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
    raw_metadata: dict[str, object]
    canonical_fingerprint: str


def normalize_text(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


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


def normalize_job(source: JobSourceName, raw: RawSourceJob) -> NormalizedJob:
    normalized_company = normalize_text(raw.company)
    normalized_title = normalize_text(raw.title)
    normalized_location = normalize_text(raw.location) if raw.location else None
    fingerprint_input = "|".join(
        [
            normalized_company,
            normalized_title,
            normalized_location or "",
            normalize_text(raw.term or ""),
        ]
    )
    metadata = json.loads(json.dumps(raw.raw_metadata, default=str))
    if len(json.dumps(metadata).encode()) > MAX_RAW_METADATA_BYTES:
        raise ValueError("raw metadata exceeds 100 KB")
    posted_at = raw.posted_at
    if posted_at and posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    return NormalizedJob(
        source=source,
        external_id=raw.external_id.strip(),
        company=raw.company.strip(),
        normalized_company=normalized_company,
        title=raw.title.strip(),
        normalized_title=normalized_title,
        location=raw.location.strip() if raw.location else None,
        normalized_location=normalized_location,
        term=raw.term.strip() if raw.term else None,
        description=raw.description,
        work_mode=raw.work_mode,
        source_url=canonicalize_url(str(raw.source_url)) if raw.source_url else None,
        apply_url=canonicalize_url(str(raw.apply_url)),
        posted_at=posted_at,
        raw_metadata=metadata,
        canonical_fingerprint=hashlib.sha256(fingerprint_input.encode()).hexdigest(),
    )


def utc_now() -> datetime:
    return datetime.now(UTC)
