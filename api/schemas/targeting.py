import uuid
from datetime import datetime

from pydantic import Field, field_validator

from api.schemas.common import APIModel
from api.schemas.filter import clean_terms, clean_values
from api.schemas.job import JobResponse


class WatchlistCreate(APIModel):
    company: str = Field(min_length=1, max_length=200)
    terms: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    active: bool = True

    _clean_terms = field_validator("terms")(clean_terms)
    _clean_locations = field_validator("locations")(clean_values)


class WatchlistUpdate(APIModel):
    terms: list[str] | None = None
    locations: list[str] | None = None
    active: bool | None = None

    _clean_terms = field_validator("terms")(
        lambda value: clean_terms(value) if value else value
    )
    _clean_locations = field_validator("locations")(
        lambda value: clean_values(value) if value else value
    )


class WatchlistResponse(APIModel):
    id: uuid.UUID
    company: str
    terms: list[str]
    locations: list[str]
    active: bool
    created_at: datetime
    updated_at: datetime


class WatchlistJobs(APIModel):
    items: list[JobResponse]
