import httpx

from api.ingestion.adapters import RemoteOKAdapter
from api.ingestion.http import RetryingHTTPClient
from api.models import PollCompleteness, WorkMode


async def test_remoteok_skips_metadata_and_preserves_attribution() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "Sprintern/test contact@example.com"
        return httpx.Response(
            200,
            json=[
                {"last_updated": 1783944000, "legal": "Please link back to Remote OK"},
                {
                    "id": "remote-1",
                    "company": "Example",
                    "position": "Backend Engineering Intern",
                    "location": "Worldwide",
                    "description": "<p>Build APIs.</p>",
                    "tags": ["python", "internship"],
                    "date": "2026-07-13T12:00:00+00:00",
                    "url": "https://remoteok.com/remote-jobs/remote-1",
                    "apply_url": "https://example.com/apply",
                },
            ],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await RemoteOKAdapter(
            RetryingHTTPClient(client), "Sprintern/test contact@example.com"
        ).fetch({})

    assert batch.completeness == PollCompleteness.COMPLETE
    assert len(batch.records) == 1
    assert batch.records[0].work_mode == WorkMode.REMOTE
    assert batch.records[0].raw_metadata["remoteok_attribution_required"] is True
    assert str(batch.records[0].source_url) == "https://remoteok.com/remote-jobs/remote-1"


async def test_remoteok_rejects_invalid_jobs() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"legal": "metadata"}, {"id": "missing-fields"}])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await RemoteOKAdapter(RetryingHTTPClient(client), "Sprintern/test").fetch({})

    assert batch.records == []
    assert batch.rejected_count == 1
