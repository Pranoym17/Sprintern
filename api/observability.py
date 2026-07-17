import contextvars
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_SENSITIVE_KEY = re.compile(r"(authorization|api.?key|secret|token|password|cookie)", re.I)
_BEARER_VALUE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
_TELEGRAM_TOKEN = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
_configured_secrets: tuple[str, ...] = ()


def _redact(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): _redact(item, str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if not isinstance(value, str):
        return value
    redacted = _BEARER_VALUE.sub("Bearer [REDACTED]", value)
    redacted = _TELEGRAM_TOKEN.sub("[REDACTED]", redacted)
    for secret in _configured_secrets:
        redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def redact_text(value: str) -> str:
    return str(_redact(value))


class JsonFormatter(logging.Formatter):
    """Emit machine-readable events without request bodies or provider credentials."""

    _reserved = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
            "request_id": getattr(record, "request_id", request_id_context.get()),
        }
        for key, value in record.__dict__.items():
            if key not in self._reserved and not key.startswith("_"):
                payload[key] = value
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(_redact(payload), separators=(",", ":"), default=str)


def configure_logging(*, secrets: list[str] | None = None, level: int = logging.INFO) -> None:
    global _configured_secrets
    _configured_secrets = tuple(secret for secret in (secrets or []) if len(secret) >= 8)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
