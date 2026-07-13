from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ErrorDetail(APIModel):
    code: str
    message: str


class ErrorResponse(APIModel):
    error: ErrorDetail
