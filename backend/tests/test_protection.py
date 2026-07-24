import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
import redis
from fastapi import Request
from sqlalchemy.orm import Session

import api.routes.sources as source_routes
from api.errors import AppError
from api.main import app
from api.models import JobSourceName, SourceState
from api.rate_limiting import InMemoryRateLimiter, RateLimit, RedisRateLimiter, client_ip
from api.settings import settings


def request_from(peer: str, forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": (peer, 1234),
            "server": ("test", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_sliding_window_rate_limit_isolated_by_identity() -> None:
    rate_limiter = InMemoryRateLimiter()
    rule = RateLimit("mutation", requests=2, window_seconds=60)

    assert rate_limiter.check(rule, "user:one", now=1)[0] == 1
    assert rate_limiter.check(rule, "user:one", now=2)[0] == 0
    assert rate_limiter.check(rule, "user:two", now=2)[0] == 1
    with pytest.raises(AppError) as error:
        rate_limiter.check(rule, "user:one", now=3)

    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "58"}
    assert rate_limiter.check(rule, "user:one", now=62)[0] == 1


def test_redis_rate_limiter_fails_closed_without_exposing_identity() -> None:
    class BrokenRedis:
        def eval(self, *_args: object) -> object:
            raise redis.ConnectionError("offline")

    rate_limiter = RedisRateLimiter("redis://localhost:6379/0")
    rate_limiter.client = BrokenRedis()  # type: ignore[assignment]
    with pytest.raises(AppError) as error:
        rate_limiter.check(RateLimit("public", 10, 60), "user:private@example.com")
    assert error.value.status_code == 503
    assert "private@example.com" not in error.value.message


def test_forwarded_client_ip_is_used_only_for_trusted_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_cidrs_value", "10.0.0.0/8")

    assert client_ip(request_from("192.0.2.10", "198.51.100.8")) == "192.0.2.10"
    assert client_ip(request_from("10.0.0.2", "198.51.100.8, 10.0.0.3")) == "198.51.100.8"
    assert client_ip(request_from("10.0.0.2", "not-an-ip")) == "10.0.0.2"


async def test_liveness_readiness_and_trusted_hosts(api_client: httpx.AsyncClient) -> None:
    live = await api_client.get("/health/live")
    ready = await api_client.get("/health/ready")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://attacker.example"
    ) as untrusted:
        rejected = await untrusted.get("/health/live")

    assert live.status_code == 200
    assert live.json() == {"status": "alive"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert rejected.status_code == 400


async def test_cors_allows_configured_origin_only(api_client: httpx.AsyncClient) -> None:
    allowed = await api_client.options(
        "/health/live",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = await api_client.options(
        "/health/live",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


async def test_public_source_status_is_aggregate_and_authenticated(
    api_client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    keys = ["owner/one:README.md", "owner/two:README.md"]
    monkeypatch.setattr(
        source_routes,
        "load_source_config",
        lambda _path: SimpleNamespace(
            enabled_github=[SimpleNamespace(source_key=key) for key in keys]
        ),
    )
    db_session.add_all(
        [
            SourceState(
                id=uuid.uuid4(),
                source=JobSourceName.GITHUB_REPO,
                source_key=keys[0],
                cursor={"secret_cursor": "not-public"},
                last_succeeded_at=now,
                last_error="private provider error",
            ),
            SourceState(
                id=uuid.uuid4(),
                source=JobSourceName.GITHUB_REPO,
                source_key=keys[1],
                cursor={},
                last_succeeded_at=now - timedelta(hours=25),
            ),
        ]
    )
    db_session.commit()

    response = await api_client.get("/sources/status")

    assert response.status_code == 200
    assert response.json() == {
        "state": "stale",
        "last_updated_at": now.isoformat().replace("+00:00", "Z"),
    }


async def test_telegram_webhook_rejects_missing_or_invalid_secret(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "telegram_webhook_secret", "expected-secret")
    payload = {"message": {"text": "/start unused", "chat": {"id": 1}}}

    missing = await api_client.post("/webhooks/telegram", json=payload)
    invalid = await api_client.post(
        "/webhooks/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json=payload,
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
