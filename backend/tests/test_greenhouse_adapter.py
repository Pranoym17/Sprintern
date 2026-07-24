import httpx

from api.ingestion.adapters import GreenhouseAdapter
from api.ingestion.http import RetryingHTTPClient
from api.models import PollCompleteness


async def test_greenhouse_maps_complete_board_snapshot() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["content"] == "true"
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 123,
                        "title": "Software Engineering Intern",
                        "location": {"name": "Toronto, Canada"},
                        "absolute_url": "https://boards.greenhouse.io/example/jobs/123",
                        "updated_at": "2026-07-13T12:00:00-04:00",
                        "content": "<p>Build &amp; ship software.</p>",
                        "departments": [{"name": "Engineering"}],
                        "offices": [],
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GreenhouseAdapter("Example", "example", RetryingHTTPClient(client))
        batch = await adapter.fetch({})

    assert batch.completeness == PollCompleteness.COMPLETE
    assert batch.rejected_count == 0
    assert batch.records[0].external_id == "123"
    assert batch.records[0].company == "Example"
    assert batch.records[0].description == "Build & ship software."


async def test_greenhouse_rejects_bad_rows_without_losing_valid_rows() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {"id": 1, "title": "Intern", "absolute_url": "https://example.com/1"},
                    {"id": 2, "title": "Missing URL"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await GreenhouseAdapter("Example", "example", RetryingHTTPClient(client)).fetch({})

    assert len(batch.records) == 1
    assert batch.rejected_count == 1
    assert len(batch.rejection_errors) == 1
