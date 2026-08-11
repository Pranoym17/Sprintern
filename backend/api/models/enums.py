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


class RoleCategory(StrEnum):
    """The small, stable role taxonomy exposed to students."""

    ALL = "all"
    SOFTWARE_ENGINEERING = "software_engineering"
    AI_ML_DATA = "ai_ml_data"
    CLOUD_INFRASTRUCTURE_SECURITY = "cloud_infrastructure_security"
    HARDWARE_EMBEDDED_SILICON = "hardware_embedded_silicon"
    PRODUCT_DESIGN_RESEARCH = "product_design_research"
    QUANT_FINANCE = "quant_finance"
    BUSINESS_OPERATIONS_PEOPLE = "business_operations_people"
    OTHER_TECHNICAL = "other_technical"


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
