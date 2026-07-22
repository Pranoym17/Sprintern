from enum import StrEnum


class NotificationCadence(StrEnum):
    INSTANT = "instant"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class NotificationChannel(StrEnum):
    TELEGRAM = "telegram"
    EMAIL = "email"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSourceName(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    REMOTEOK = "remoteok"
    GITHUB_REPO = "github_repo"
    ASHBY = "ashby"
    WWR = "wwr"


class WorkMode(StrEnum):
    REMOTE = "remote"
    ONSITE = "onsite"
    HYBRID = "hybrid"
    ANY = "any"
    UNKNOWN = "unknown"


class JobStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    EXPIRED = "expired"


class MatchStatus(StrEnum):
    MATCHED = "matched"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class IngestionRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class PollCompleteness(StrEnum):
    COMPLETE = "complete"
    INCREMENTAL = "incremental"
    PARTIAL = "partial"


class InternshipStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"


class DeadlineSource(StrEnum):
    SOURCE = "source"
    INFERRED = "inferred"
    USER = "user"


class ApplicationStage(StrEnum):
    SAVED = "saved"
    PREPARING = "preparing"
    APPLIED = "applied"
    OA = "oa"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ExclusionType(StrEnum):
    KEYWORD = "keyword"
    COMPANY = "company"
    LOCATION = "location"


class ReportReason(StrEnum):
    CLOSED = "closed"
    DUPLICATE = "duplicate"
    SUSPICIOUS = "suspicious"
    INACCURATE = "inaccurate"


class NotificationPriority(StrEnum):
    NORMAL = "normal"
    HIGH = "high"


class ReminderType(StrEnum):
    DEADLINE = "deadline"
    FOLLOW_UP = "follow_up"
    INTERVIEW = "interview"
    SAVED = "saved"
    PREPARING = "preparing"
