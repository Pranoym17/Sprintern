from typing import Any

from pydantic import ValidationError

from api.ingestion.adapters.utils import html_to_text, parse_datetime
from api.ingestion.contracts import PollBatch, RawSourceJob
from api.ingestion.http import RetryingHTTPClient, SourceHTTPError
from api.models import JobSourceName, PollCompleteness


class GreenhouseAdapter:
    source = JobSourceName.GREENHOUSE

    def __init__(self, company: str, board_token: str, http: RetryingHTTPClient) -> None:
        self.company = company.strip()
        self.board_token = board_token.strip()
        self.http = http

    @property
    def source_key(self) -> str:
        return self.board_token

    async def fetch(self, cursor: dict[str, Any]) -> PollBatch:
        del cursor  # Greenhouse returns a complete board snapshot.
        payload = await self.http.get_json(
            f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs",
            params={"content": "true"},
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise SourceHTTPError("Greenhouse returned an unexpected response shape")

        records: list[RawSourceJob] = []
        errors: list[str] = []
        for item in payload["jobs"]:
            try:
                records.append(self._map_job(item))
            except (KeyError, TypeError, ValidationError, ValueError) as exc:
                if len(errors) < 25:
                    errors.append(f"Greenhouse row rejected: {exc}")
        return PollBatch(
            records=records,
            completeness=PollCompleteness.COMPLETE,
            rejected_count=len(payload["jobs"]) - len(records),
            rejection_errors=errors,
        )

    def _map_job(self, item: dict[str, Any]) -> RawSourceJob:
        location = item.get("location") or {}
        absolute_url = item["absolute_url"]
        return RawSourceJob(
            external_id=str(item["id"]),
            company=self.company,
            title=item["title"],
            location=location.get("name"),
            description=html_to_text(item.get("content")),
            source_url=absolute_url,
            apply_url=absolute_url,
            posted_at=parse_datetime(item.get("updated_at")),
            raw_metadata={
                "departments": item.get("departments", []),
                "offices": item.get("offices", []),
                "metadata": item.get("metadata"),
            },
        )
