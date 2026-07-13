import base64
import hashlib
import re
from typing import Any

from pydantic import ValidationError

from api.ingestion.adapters.utils import html_to_text, parse_datetime
from api.ingestion.contracts import PollBatch, RawSourceJob
from api.ingestion.http import RetryingHTTPClient, SourceHTTPError
from api.models import JobSourceName, PollCompleteness

MARKDOWN_LINK = re.compile(r"\[[^]]*]\((https?://[^)\s]+)[^)]*\)")
HTML_LINK = re.compile(r"href=[\"'](https?://[^\"']+)", re.IGNORECASE)
RAW_LINK = re.compile(r"https?://[^\s<>|)]+")
SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
CLOSED_MARKERS = {"closed", "filled", "expired", "🔒"}

HEADER_ALIASES = {
    "company": {"company", "employer"},
    "title": {"role", "title", "position"},
    "location": {"location", "locations"},
    "url": {"application", "apply", "link", "application link"},
    "date": {"date", "date posted", "posted", "posting date"},
}


class GitHubRepositoryAdapter:
    source = JobSourceName.GITHUB_REPO

    def __init__(
        self,
        owner: str,
        repository: str,
        http: RetryingHTTPClient,
        *,
        path: str = "README.md",
        branch: str | None = None,
        token: str | None = None,
        term: str | None = None,
    ) -> None:
        self.owner = owner
        self.repository = repository
        self.path = path
        self.branch = branch
        self.http = http
        self.token = token
        self.term = term

    @property
    def source_key(self) -> str:
        return f"{self.owner}/{self.repository}:{self.path}"

    async def fetch(self, cursor: dict[str, Any]) -> PollBatch:
        headers = self._headers()
        params: dict[str, Any] = {"path": self.path, "per_page": 1}
        if self.branch:
            params["sha"] = self.branch
        commits = await self.http.get_json(
            f"https://api.github.com/repos/{self.owner}/{self.repository}/commits",
            headers=headers,
            params=params,
        )
        if not isinstance(commits, list) or not commits or not isinstance(commits[0], dict):
            raise SourceHTTPError("GitHub returned no commit for the configured file")
        commit_sha = commits[0].get("sha")
        if not isinstance(commit_sha, str):
            raise SourceHTTPError("GitHub commit response did not include a SHA")
        if cursor.get("sha") == commit_sha:
            return PollBatch(
                records=[],
                completeness=PollCompleteness.INCREMENTAL,
                next_cursor={"sha": commit_sha},
            )

        content = await self.http.get_json(
            f"https://api.github.com/repos/{self.owner}/{self.repository}/contents/{self.path}",
            headers=headers,
            params={"ref": commit_sha},
        )
        markdown = self._decode_content(content)
        records, errors = self._parse_tables(markdown, commit_sha)
        return PollBatch(
            records=records,
            completeness=PollCompleteness.INCREMENTAL,
            next_cursor={"sha": commit_sha},
            rejected_count=len(errors),
            rejection_errors=errors[:25],
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _decode_content(payload: Any) -> str:
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise SourceHTTPError("GitHub contents response was not base64 file content")
        try:
            return base64.b64decode(payload["content"]).decode("utf-8")
        except (KeyError, ValueError, UnicodeDecodeError) as exc:
            raise SourceHTTPError("GitHub file content could not be decoded") from exc

    def _parse_tables(self, markdown: str, commit_sha: str) -> tuple[list[RawSourceJob], list[str]]:
        lines = markdown.splitlines()
        records: list[RawSourceJob] = []
        errors: list[str] = []
        previous_company: str | None = None
        found_table = False
        index = 0
        while index + 1 < len(lines):
            headers = self._split_row(lines[index])
            separator = self._split_row(lines[index + 1])
            if (
                headers
                and len(headers) == len(separator)
                and all(SEPARATOR_CELL.match(cell.replace(" ", "")) for cell in separator)
            ):
                columns = self._column_map(headers)
                if {"company", "title", "url"}.issubset(columns):
                    found_table = True
                    index += 2
                    while index < len(lines):
                        cells = self._split_row(lines[index])
                        if not cells or len(cells) != len(headers):
                            break
                        try:
                            record, previous_company = self._map_row(
                                cells, columns, previous_company, commit_sha
                            )
                            if record:
                                records.append(record)
                        except (TypeError, ValueError, ValidationError) as exc:
                            if len(errors) < 25:
                                errors.append(f"GitHub table row {index + 1} rejected: {exc}")
                        index += 1
                    continue
            index += 1
        if not found_table:
            raise SourceHTTPError("GitHub file has no supported internship table schema")
        return records, errors

    @staticmethod
    def _split_row(line: str) -> list[str]:
        stripped = line.strip()
        if "|" not in stripped:
            return []
        return [
            cell.replace("\\|", "|").strip() for cell in re.split(r"(?<!\\)\|", stripped.strip("|"))
        ]

    @staticmethod
    def _column_map(headers: list[str]) -> dict[str, int]:
        result: dict[str, int] = {}
        for index, header in enumerate(headers):
            normalized = (html_to_text(header) or "").lower().strip()
            for name, aliases in HEADER_ALIASES.items():
                if normalized in aliases:
                    result[name] = index
        return result

    def _map_row(
        self,
        cells: list[str],
        columns: dict[str, int],
        previous_company: str | None,
        commit_sha: str,
    ) -> tuple[RawSourceJob | None, str | None]:
        company_text = html_to_text(cells[columns["company"]]) or ""
        if company_text.strip() in {"↳", "↪", ""}:
            company = previous_company
        else:
            company = company_text.strip("*~ ")
        if not company:
            raise ValueError("company is missing and cannot be inherited")

        title = (html_to_text(cells[columns["title"]]) or "").strip("*~ ")
        url_cell = cells[columns["url"]]
        if any(marker in url_cell.lower() for marker in CLOSED_MARKERS):
            return None, company
        apply_url = self._extract_url(url_cell)
        if not apply_url:
            raise ValueError("application URL is missing")
        location = html_to_text(cells[columns["location"]]) if "location" in columns else None
        posted_at = parse_datetime(cells[columns["date"]]) if "date" in columns else None
        external_id = hashlib.sha256(apply_url.encode()).hexdigest()
        source_url = (
            f"https://github.com/{self.owner}/{self.repository}/blob/{commit_sha}/{self.path}"
        )
        return (
            RawSourceJob(
                external_id=external_id,
                company=company,
                title=title,
                location=location,
                term=self.term,
                source_url=source_url,
                apply_url=apply_url,
                posted_at=posted_at,
                raw_metadata={"commit_sha": commit_sha, "repository": self.source_key},
            ),
            company,
        )

    @staticmethod
    def _extract_url(value: str) -> str | None:
        for pattern in (MARKDOWN_LINK, HTML_LINK, RAW_LINK):
            match = pattern.search(value)
            if match:
                return match.group(1) if match.lastindex else match.group(0)
        return None
