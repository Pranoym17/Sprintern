from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


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
