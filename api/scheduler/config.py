import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GitHubSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    enabled: bool = True
    owner: str = Field(min_length=1, max_length=100)
    repository: str = Field(min_length=1, max_length=100)
    path: str = Field(default="README.md", min_length=1, max_length=500)
    branch: str | None = Field(default=None, min_length=1, max_length=255)
    term: str | None = Field(default=None, min_length=1, max_length=100)
    poll_minutes: int = Field(default=15, ge=5, le=1440)
    jitter_seconds: int = Field(default=30, ge=0, le=300)

    @property
    def source_key(self) -> str:
        return f"{self.owner}/{self.repository}:{self.path}"

    @property
    def job_id(self) -> str:
        return f"ingest:github:{self.source_key}"


class SchedulerSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    github: list[GitHubSourceConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_enabled_sources(self) -> "SchedulerSourceConfig":
        enabled = [source for source in self.github if source.enabled]
        if not enabled:
            raise ValueError("at least one scheduled source must be enabled")
        source_keys = [source.source_key.casefold() for source in enabled]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("enabled scheduled sources must be unique")
        return self

    @property
    def enabled_github(self) -> list[GitHubSourceConfig]:
        return [source for source in self.github if source.enabled]


def load_source_config(path: str | Path) -> SchedulerSourceConfig:
    config_path = Path(path)
    try:
        with config_path.open("rb") as config_file:
            payload: dict[str, Any] = tomllib.load(config_file)
    except FileNotFoundError as exc:
        raise ValueError(f"scheduler source config not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"scheduler source config is invalid TOML: {config_path}") from exc
    return SchedulerSourceConfig.model_validate(payload)
