import base64
import json
import uuid
from datetime import datetime

from api.errors import AppError


def encode_cursor(created_at: datetime, item_id: uuid.UUID) -> str:
    payload = json.dumps({"created_at": created_at.isoformat(), "id": str(item_id)}).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        return datetime.fromisoformat(payload["created_at"]), uuid.UUID(payload["id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise AppError(400, "invalid_cursor", "Pagination cursor is invalid") from exc
