import base64

import httpx

from api.ingestion.adapters import GitHubRepositoryAdapter
from api.ingestion.http import RetryingHTTPClient, SourceHTTPError
from api.models import PollCompleteness

README = "\n".join(
    [
        "# Internships",
        "",
        "| Company | Role | Location | Application | Date Posted |",
        "| ------- | ---- | -------- | ----------- | ----------- |",
        "| Example | Software Engineering Intern | Toronto, ON | "
        "[Apply](https://example.com/apply?utm_source=github) | 2026-07-13 |",
        "| ↳ | Data Engineering Intern | Remote | "
        "[Apply](https://example.com/data) | 2026-07-13 |",
        "| Closed Co | Backend Intern | New York | 🔒 Closed | 2026-07-12 |",
    ]
)

CURRENT_REPOSITORY_STYLE_README = "\n".join(
    [
        "# Summer 2027 Internships",
        "",
        "| Company | Role | Location | Application/Link | Date Posted |",
        "| ------- | ---- | -------- | ---------------- | ----------- |",
        "| Example | Software Engineer Intern | Toronto, ON</br>Remote | "
        '<a href="https://example.com/apply"><img alt="Apply"></a> | Jul 09 |',
        "| ↳ | Data Engineer Intern | New York, NY | "
        '<a href="https://example.com/data"><img alt="Apply"></a> | Jul 08 |',
        "| Closed Co | Backend Intern | Chicago, IL | 🔒 | Jul 07 |",
    ]
)


async def test_github_skips_unchanged_commit() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path.endswith("/commits")
        return httpx.Response(200, json=[{"sha": "abc123"}])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GitHubRepositoryAdapter(
            "owner", "internships", RetryingHTTPClient(client), token="github-token"
        )
        batch = await adapter.fetch({"sha": "abc123"})

    assert calls == 1
    assert batch.records == []
    assert batch.completeness == PollCompleteness.INCREMENTAL
    assert batch.next_cursor == {"sha": "abc123"}


async def test_github_parses_supported_table_and_inherited_company() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
        assert request.headers["Authorization"] == "Bearer github-token"
        if request.url.path.endswith("/commits"):
            return httpx.Response(200, json=[{"sha": "new-sha"}])
        assert request.url.params["ref"] == "new-sha"
        return httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(README.encode()).decode()},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GitHubRepositoryAdapter(
            "owner",
            "internships",
            RetryingHTTPClient(client),
            token="github-token",
            term="Summer 2027",
        )
        batch = await adapter.fetch({})

    assert len(batch.records) == 2
    assert batch.records[0].company == "Example"
    assert batch.records[1].company == "Example"
    assert batch.records[0].term == "Summer 2027"
    assert batch.records[0].posted_at is not None
    assert batch.next_cursor == {"sha": "new-sha"}


async def test_github_parses_current_repository_table_style() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits"):
            return httpx.Response(200, json=[{"sha": "new-sha"}])
        return httpx.Response(
            200,
            json={
                "encoding": "base64",
                "content": base64.b64encode(CURRENT_REPOSITORY_STYLE_README.encode()).decode(),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GitHubRepositoryAdapter(
            "vanshb03",
            "Summer2027-Internships",
            RetryingHTTPClient(client),
            branch="dev",
            term="Summer 2027",
        )
        batch = await adapter.fetch({})

    assert len(batch.records) == 2
    assert str(batch.records[0].apply_url) == "https://example.com/apply"
    assert batch.records[0].location == "Toronto, ON Remote"
    assert batch.records[1].company == "Example"
    assert batch.rejected_count == 0


async def test_github_fails_visibly_when_table_schema_changes() -> None:
    invalid_readme = "| Name | Notes |\n| --- | --- |\n| Example | No job columns |"

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits"):
            return httpx.Response(200, json=[{"sha": "new-sha"}])
        return httpx.Response(
            200,
            json={
                "encoding": "base64",
                "content": base64.b64encode(invalid_readme.encode()).decode(),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GitHubRepositoryAdapter("owner", "repo", RetryingHTTPClient(client))
        try:
            await adapter.fetch({})
        except SourceHTTPError as exc:
            assert "no supported internship table schema" in str(exc)
        else:
            raise AssertionError("schema changes must fail the poll")
