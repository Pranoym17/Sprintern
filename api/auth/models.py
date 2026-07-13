import uuid

from pydantic import BaseModel, ConfigDict


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    email: str | None = None
