from typing import Any

from pydantic import ValidationError

from api.ingestion.adapters.utils import html_to_text, parse_datetime
from api.ingestion.contracts import PollBatch, RawSourceJob
from api.ingestion.http import RetryingHTTPClient, SourceHTTPError
from api.models import JobSourceName, PollCompleteness, WorkMode


class RemoteOKAdapter:
    source = JobSourceName.REMOTEOK
    source_key = "remoteok"

    def __init__(self, http: RetryingHTTPClient, user_agent: str) -> None:
        self.http = http
        self.user_agent = user_agent

    async def fetch(self, cursor: dict[str, Any]) -> PollBatch:
        del cursor
        payload = await self.http.get_json(
            "https://remoteok.com/api",
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        if not isinstance(payload, list):
            raise SourceHTTPError("RemoteOK returned an unexpected response shape")

        items = [item for item in payload if isinstance(item, dict) and item.get("id")]
        records: list[RawSourceJob] = []
        errors: list[str] = []
        for item in items:
            try:
                records.append(self._map_job(item))
            except (KeyError, TypeError, ValidationError, ValueError) as exc:
                if len(errors) < 25:
                    errors.append(f"RemoteOK row rejected: {exc}")
        return PollBatch(
            records=records,
            completeness=PollCompleteness.COMPLETE,
            rejected_count=len(items) - len(records),
            rejection_errors=errors,
        )

    @staticmethod
    def _map_job(item: dict[str, Any]) -> RawSourceJob:
        source_url = item.get("url") or f"https://remoteok.com/remote-jobs/{item['id']}"
        return RawSourceJob(
            external_id=str(item["id"]),
            company=item["company"],
            title=item["position"],
            location=item.get("location") or "Remote",
            description=html_to_text(item.get("description")),
            work_mode=WorkMode.REMOTE,
            source_url=source_url,
            apply_url=item.get("apply_url") or source_url,
            posted_at=parse_datetime(item.get("date")) or parse_datetime(item.get("epoch")),
            raw_metadata={
                "tags": item.get("tags", []),
                "salary_min": item.get("salary_min"),
                "salary_max": item.get("salary_max"),
                "remoteok_attribution_required": True,
            },
        )
