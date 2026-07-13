import httpx

from api.ingestion.adapters import LeverAdapter
from api.ingestion.http import RetryingHTTPClient
from api.models import PollCompleteness, WorkMode


async def test_lever_paginates_and_maps_workplace_type() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        skip = int(request.url.params["skip"])
        if skip == 0:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "lever-1",
                        "text": "Platform Engineering Intern",
                        "categories": {
                            "location": "Remote - Canada",
                            "commitment": "Internship",
                            "team": "Platform",
                        },
                        "descriptionPlain": "Build developer infrastructure.",
                        "workplaceType": "remote",
                        "hostedUrl": "https://jobs.lever.co/example/lever-1",
                        "applyUrl": "https://jobs.lever.co/example/lever-1/apply",
                        "createdAt": 1783944000000,
                    }
                ],
            )
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = LeverAdapter(
            "Example", "example", RetryingHTTPClient(client), region="global", page_size=1
        )
        batch = await adapter.fetch({})

    assert len(requests) == 2
    assert batch.completeness == PollCompleteness.COMPLETE
    assert batch.records[0].work_mode == WorkMode.REMOTE
    assert batch.records[0].posted_at is not None
    assert batch.records[0].raw_metadata["commitment"] == "Internship"


async def test_lever_supports_eu_tenants_and_rejects_bad_rows() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.eu.lever.co"
        return httpx.Response(200, json=[{"id": "broken"}])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await LeverAdapter(
            "Example", "example", RetryingHTTPClient(client), region="eu"
        ).fetch({})

    assert batch.records == []
    assert batch.rejected_count == 1
