import uuid
from datetime import datetime

from pydantic import Field, field_validator

from api.models.enums import WorkMode
from api.schemas.common import APIModel


def clean_values(values: list[str]) -> list[str]:
    cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
    if len(cleaned) > 25:
        raise ValueError("at most 25 values are allowed")
    if any(len(value) > 100 for value in cleaned):
        raise ValueError("values must be at most 100 characters")
    return cleaned


class FilterCreate(APIModel):
    name: str = Field(min_length=1, max_length=100)
    role_keywords: list[str] = Field(default_factory=list)
    location_keywords: list[str] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    work_mode: WorkMode = WorkMode.ANY
    active: bool = True

    _clean_roles = field_validator("role_keywords")(clean_values)
    _clean_locations = field_validator("location_keywords")(clean_values)
    _clean_terms = field_validator("terms")(clean_values)


class FilterUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role_keywords: list[str] | None = None
    location_keywords: list[str] | None = None
    terms: list[str] | None = None
    work_mode: WorkMode | None = None
    active: bool | None = None

    _clean_roles = field_validator("role_keywords")(
        lambda value: clean_values(value) if value else value
    )
    _clean_locations = field_validator("location_keywords")(
        lambda value: clean_values(value) if value else value
    )
    _clean_terms = field_validator("terms")(lambda value: clean_values(value) if value else value)


class FilterResponse(APIModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    name: str
    role_keywords: list[str]
    location_keywords: list[str]
    terms: list[str]
    work_mode: WorkMode
    active: bool
    created_at: datetime
    updated_at: datetime
