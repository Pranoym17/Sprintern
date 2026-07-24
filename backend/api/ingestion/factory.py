import httpx

from api.ingestion.adapters import (
    GitHubRepositoryAdapter,
    GreenhouseAdapter,
    LeverAdapter,
    RemoteOKAdapter,
    SourceAdapter,
)
from api.ingestion.http import RetryingHTTPClient
from api.models import JobSourceName
from api.schemas.ingestion import IngestionRunRequest
from api.settings import settings


def build_adapter(request: IngestionRunRequest, client: httpx.AsyncClient) -> SourceAdapter:
    http = RetryingHTTPClient(client)
    if request.source == JobSourceName.GREENHOUSE:
        return GreenhouseAdapter(request.company or "", request.board_token or "", http)
    if request.source == JobSourceName.LEVER:
        return LeverAdapter(
            request.company or "",
            request.site or "",
            http,
            region=request.region,
        )
    if request.source == JobSourceName.REMOTEOK:
        return RemoteOKAdapter(http, settings.source_user_agent)
    if request.source == JobSourceName.GITHUB_REPO:
        return GitHubRepositoryAdapter(
            request.owner or "",
            request.repository or "",
            http,
            path=request.path,
            branch=request.branch,
            token=settings.github_token or None,
            term=request.term,
        )
    raise ValueError(f"source {request.source.value} is not implemented in the MVP")
