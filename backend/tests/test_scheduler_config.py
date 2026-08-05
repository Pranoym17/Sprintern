from pathlib import Path

import pytest
from pydantic import ValidationError

from api.scheduler.config import SchedulerSourceConfig, load_source_config


def write_config(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_loads_enabled_github_source(tmp_path: Path) -> None:
    path = write_config(
        tmp_path / "sources.toml",
        """
[[github]]
owner = "vanshb03"
repository = "Summer2027-Internships"
branch = "dev"
term = "Summer 2027"
""",
    )

    config = load_source_config(path)

    assert len(config.enabled_github) == 1
    assert config.enabled_github[0].poll_minutes == 10
    assert config.enabled_github[0].jitter_seconds == 0
    assert config.enabled_github[0].source_key == ("vanshb03/Summer2027-Internships:README.md")


def test_rejects_duplicate_enabled_sources() -> None:
    with pytest.raises(ValidationError, match="must be unique"):
        SchedulerSourceConfig.model_validate(
            {
                "github": [
                    {"owner": "Owner", "repository": "Repo"},
                    {"owner": "owner", "repository": "repo"},
                ]
            }
        )


def test_ignores_disabled_source_when_checking_uniqueness() -> None:
    config = SchedulerSourceConfig.model_validate(
        {
            "github": [
                {"owner": "owner", "repository": "repo"},
                {"owner": "owner", "repository": "repo", "enabled": False},
            ]
        }
    )

    assert len(config.enabled_github) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"github": [{"owner": "", "repository": "repo"}]},
        {"github": [{"owner": "owner", "repository": "repo", "poll_minutes": 0}]},
        {"github": [{"owner": "owner", "repository": "repo", "unexpected": True}]},
    ],
)
def test_rejects_invalid_source_configuration(payload: object) -> None:
    with pytest.raises(ValidationError):
        SchedulerSourceConfig.model_validate(payload)


def test_reports_missing_and_malformed_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        load_source_config(tmp_path / "missing.toml")

    malformed = write_config(tmp_path / "bad.toml", "[[github]\n")
    with pytest.raises(ValueError, match="invalid TOML"):
        load_source_config(malformed)


def test_fallback_registry_has_unique_exact_ten_minute_active_sources() -> None:
    config = load_source_config(Path(__file__).parents[1] / "config" / "sources.toml")
    keys = [source.source_key for source in config.enabled_github]

    assert len(keys) == len(set(key.casefold() for key in keys))
    assert all(source.poll_minutes == 10 for source in config.enabled_github)
    assert all(source.jitter_seconds == 0 for source in config.enabled_github)
    assert keys.count("vanshb03/Summer2027-Internships:README.md") == 1
    assert keys.count("negarprh/Canadian-Tech-Internships-2026:README-2027.md") == 1
    assert keys.count("speedyapply/2027-SWE-College-Jobs:README.md") == 1
