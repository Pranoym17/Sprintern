from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


INTERNAL_ORIGIN_KEYS = {
    "external_id",
    "raw_metadata",
    "source",
    "source_key",
    "source_url",
    "sources",
}


def strip_internal_origin(value: Any) -> Any:
    """Defend the public serialization boundary even for historical JSON payloads."""
    if isinstance(value, dict):
        return {
            key: strip_internal_origin(item)
            for key, item in value.items()
            if str(key).casefold() not in INTERNAL_ORIGIN_KEYS
        }
    if isinstance(value, list):
        return [strip_internal_origin(item) for item in value]
    return value


class ErrorDetail(APIModel):
    code: str
    message: str
    request_id: str
    details: Any = None


class ErrorResponse(APIModel):
    error: ErrorDetail


class HealthResponse(APIModel):
    status: str


class DispatchResponse(APIModel):
    sent_deliveries: int = Field(ge=0)
