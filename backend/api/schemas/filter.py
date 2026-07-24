import re
import uuid
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from api.models.enums import (
    ExclusionType,
    NotificationCadence,
    NotificationPriority,
    WorkMode,
)
from api.schemas.common import APIModel


def clean_values(values: list[str]) -> list[str]:
    cleaned = list(dict.fromkeys(value.strip() for value in values if value.strip()))
    if len(cleaned) > 25:
        raise ValueError("at most 25 values are allowed")
    if any(len(value) > 100 for value in cleaned):
        raise ValueError("values must be at most 100 characters")
    return cleaned


def clean_terms(values: list[str]) -> list[str]:
    cleaned = clean_values(values)
    if any(re.fullmatch(r"(?:Summer|Fall|Winter) \d{4}", value) is None for value in cleaned):
        raise ValueError("terms must use Summer, Fall, or Winter followed by a four-digit year")
    return cleaned


class FilterCreate(APIModel):
    name: str = Field(min_length=1, max_length=100)
    role_keywords: list[str] = Field(default_factory=list)
    location_keywords: list[str] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    work_mode: WorkMode = WorkMode.ANY
    active: bool = True
    remote_only: bool = False
    radius_km: int | None = Field(default=None, ge=1, le=500)
    center_latitude: float | None = Field(default=None, ge=-90, le=90)
    center_longitude: float | None = Field(default=None, ge=-180, le=180)
    excluded_keywords: list[str] = Field(default_factory=list)
    excluded_companies: list[str] = Field(default_factory=list)
    excluded_locations: list[str] = Field(default_factory=list)

    _clean_roles = field_validator("role_keywords")(clean_values)
    _clean_locations = field_validator("location_keywords")(clean_values)
    _clean_terms = field_validator("terms")(clean_terms)
    _clean_excluded_keywords = field_validator("excluded_keywords")(clean_values)
    _clean_excluded_companies = field_validator("excluded_companies")(clean_values)
    _clean_excluded_locations = field_validator("excluded_locations")(clean_values)

    @model_validator(mode="after")
    def validate_radius_center(self) -> "FilterCreate":
        if self.radius_km is not None and (
            self.center_latitude is None or self.center_longitude is None
        ):
            raise ValueError("radius filters require a recognized center location")
        return self


class FilterUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role_keywords: list[str] | None = None
    location_keywords: list[str] | None = None
    terms: list[str] | None = None
    work_mode: WorkMode | None = None
    active: bool | None = None
    remote_only: bool | None = None
    radius_km: int | None = Field(default=None, ge=1, le=500)
    center_latitude: float | None = Field(default=None, ge=-90, le=90)
    center_longitude: float | None = Field(default=None, ge=-180, le=180)
    excluded_keywords: list[str] | None = None
    excluded_companies: list[str] | None = None
    excluded_locations: list[str] | None = None

    _clean_roles = field_validator("role_keywords")(
        lambda value: clean_values(value) if value else value
    )
    _clean_locations = field_validator("location_keywords")(
        lambda value: clean_values(value) if value else value
    )
    _clean_terms = field_validator("terms")(lambda value: clean_terms(value) if value else value)
    _clean_excluded_keywords = field_validator("excluded_keywords")(
        lambda value: clean_values(value) if value else value
    )
    _clean_excluded_companies = field_validator("excluded_companies")(
        lambda value: clean_values(value) if value else value
    )
    _clean_excluded_locations = field_validator("excluded_locations")(
        lambda value: clean_values(value) if value else value
    )

    @model_validator(mode="after")
    def validate_radius_center(self) -> "FilterUpdate":
        if self.radius_km is not None and (
            self.center_latitude is None or self.center_longitude is None
        ):
            raise ValueError("radius filters require a recognized center location")
        return self


class FilterExclusionResponse(APIModel):
    kind: ExclusionType
    value: str


class FilterResponse(APIModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    name: str
    role_keywords: list[str]
    location_keywords: list[str]
    terms: list[str]
    work_mode: WorkMode
    active: bool
    remote_only: bool
    radius_km: int | None
    center_latitude: float | None
    center_longitude: float | None
    exclusions: list[FilterExclusionResponse]
    created_at: datetime
    updated_at: datetime


class FilterPreviewExample(APIModel):
    id: uuid.UUID
    company: str
    title: str
    location: str | None
    reasons: dict[str, object]


class FilterPreviewResponse(APIModel):
    estimated_count: int
    examples: list[FilterPreviewExample]
    warnings: list[str]
    aliases: dict[str, list[str]]
    exclusions: dict[str, list[str]]


class FilterNotificationUpdate(APIModel):
    email_enabled: bool | None = None
    telegram_enabled: bool | None = None
    cadence: NotificationCadence | None = None
    priority: NotificationPriority = NotificationPriority.NORMAL


class FilterNotificationResponse(FilterNotificationUpdate):
    filter_id: uuid.UUID
    uses_profile_defaults: bool
