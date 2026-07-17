import html
import re
from datetime import UTC, datetime
from typing import Any

TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")


def html_to_text(value: str | None) -> str | None:
    if not value:
        return None
    text = TAG_PATTERN.sub(" ", value)
    return WHITESPACE_PATTERN.sub(" ", html.unescape(text)).strip() or None


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=UTC)
    if isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
        except ValueError:
            for date_format in ("%b %d, %Y", "%B %d, %Y"):
                try:
                    return datetime.strptime(normalized, date_format).replace(tzinfo=UTC)
                except ValueError:
                    continue
            return None
    return None
