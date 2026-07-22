from dataclasses import dataclass
from enum import StrEnum


class DeliveryOutcome(StrEnum):
    SENT = "sent"
    TRANSIENT_FAILURE = "transient_failure"
    PERMANENT_FAILURE = "permanent_failure"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class NotificationMessage:
    recipient: str
    subject: str
    text: str
    html: str
    apply_url: str
    idempotency_key: str
    unsubscribe_url: str | None = None


@dataclass(frozen=True)
class ProviderResult:
    outcome: DeliveryOutcome
    provider_message_id: str | None = None
    error: str | None = None
    retry_after_seconds: float | None = None
