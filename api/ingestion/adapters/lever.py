from typing import Any, Literal

from pydantic import ValidationError

from api.ingestion.adapters.utils import html_to_text, parse_datetime
from api.ingestion.contracts import PollBatch, RawSourceJob
from api.ingestion.http import RetryingHTTPClient, SourceHTTPError
from api.models import JobSourceName, PollCompleteness, WorkMode

WORK_MODES = {
    "remote": WorkMode.REMOTE,
    "hybrid": WorkMode.HYBRID,
    "on-site": WorkMode.ONSITE,
}


class LeverAdapter:
    source = JobSourceName.LEVER

    def __init__(
        self,
        company: str,
        site: str,
        http: RetryingHTTPClient,
        *,
        region: Literal["global", "eu"] = "global",
        page_size: int = 100,
    ) -> None:
        self.company = company.strip()
        self.site = site.strip()
        self.http = http
        self.base_url = "https://api.eu.lever.co" if region == "eu" else "https://api.lever.co"
        self.page_size = page_size

    @property
    def source_key(self) -> str:
        return f"{self.base_url}:{self.site}"

    async def fetch(self, cursor: dict[str, Any]) -> PollBatch:
        del cursor  # Lever is treated as a complete paginated snapshot.
        items: list[dict[str, Any]] = []
        for page in range(100):
            payload = await self.http.get_json(
                f"{self.base_url}/v0/postings/{self.site}",
                params={"mode": "json", "skip": page * self.page_size, "limit": self.page_size},
            )
            if not isinstance(payload, list):
                raise SourceHTTPError("Lever returned an unexpected response shape")
            items.extend(payload)
            if len(payload) < self.page_size:
                break
        else:
            raise SourceHTTPError("Lever pagination exceeded the safety limit")

        records: list[RawSourceJob] = []
        errors: list[str] = []
        for item in items:
            try:
                records.append(self._map_job(item))
            except (KeyError, TypeError, ValidationError, ValueError) as exc:
                if len(errors) < 25:
                    errors.append(f"Lever row rejected: {exc}")
        return PollBatch(
            records=records,
            completeness=PollCompleteness.COMPLETE,
            rejected_count=len(items) - len(records),
            rejection_errors=errors,
        )

    def _map_job(self, item: dict[str, Any]) -> RawSourceJob:
        categories = item.get("categories") or {}
        hosted_url = item["hostedUrl"]
        description = item.get("descriptionPlain") or html_to_text(item.get("description"))
        workplace_type = item.get("workplaceType")
        return RawSourceJob(
            external_id=str(item["id"]),
            company=self.company,
            title=item["text"],
            location=categories.get("location"),
            description=description,
            work_mode=(
                WORK_MODES.get(workplace_type, WorkMode.UNKNOWN)
                if isinstance(workplace_type, str)
                else WorkMode.UNKNOWN
            ),
            source_url=hosted_url,
            apply_url=item.get("applyUrl") or hosted_url,
            posted_at=parse_datetime(item.get("createdAt")),
            raw_metadata={
                "commitment": categories.get("commitment"),
                "department": categories.get("department"),
                "team": categories.get("team"),
                "all_locations": categories.get("allLocations", []),
                "lists": item.get("lists", []),
            },
        )
