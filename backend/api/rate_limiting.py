import hashlib
import ipaddress
import math
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, cast

import redis
from fastapi import Depends, Request, Response

from api.auth.dependencies import get_current_user
from api.auth.models import AuthenticatedUser
from api.errors import AppError
from api.settings import settings


@dataclass(frozen=True)
class RateLimit:
    name: str
    requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """A bounded, process-local sliding-window limiter for the MVP deployment."""

    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def check(self, rule: RateLimit, identity: str, now: float | None = None) -> tuple[int, int]:
        if not settings.rate_limit_enabled:
            return rule.requests, 0
        current = time.monotonic() if now is None else now
        cutoff = current - rule.window_seconds
        key = (rule.name, identity)
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= rule.requests:
                retry_after = max(1, math.ceil(events[0] + rule.window_seconds - current))
                raise AppError(
                    429,
                    "rate_limited",
                    "Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(current)
            remaining = rule.requests - len(events)
            if len(self._events) > settings.rate_limit_max_identities:
                self._discard_inactive(current)
            return remaining, max(0, math.ceil(events[0] + rule.window_seconds - current))

    def _discard_inactive(self, now: float) -> None:
        inactive = [
            key for key, events in self._events.items() if not events or events[-1] < now - 3600
        ]
        for key in inactive:
            self._events.pop(key, None)
        if len(self._events) > settings.rate_limit_max_identities:
            oldest = sorted(self._events, key=lambda key: self._events[key][-1])
            for key in oldest[: len(self._events) - settings.rate_limit_max_identities]:
                self._events.pop(key, None)


class RedisRateLimiter:
    """Distributed sliding-window limiter; Redis stores only hashed identities."""

    _CHECK = """
    local key = KEYS[1]
    local cutoff = tonumber(ARGV[1])
    local now = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local member = ARGV[4]
    local window = tonumber(ARGV[5])
    redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
    local count = redis.call('ZCARD', key)
    if count >= limit then
      local first = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
      return {0, count, first[2] or now}
    end
    redis.call('ZADD', key, now, member)
    redis.call('PEXPIRE', key, window)
    return {1, count + 1, now}
    """

    def __init__(self, url: str) -> None:
        self.client = redis.Redis.from_url(url, decode_responses=True)

    def reset(self) -> None:
        # Production counters intentionally have no global reset operation.
        return

    def check(self, rule: RateLimit, identity: str, now: float | None = None) -> tuple[int, int]:
        current = time.time() if now is None else now
        now_ms = int(current * 1000)
        window_ms = rule.window_seconds * 1000
        identity_hash = hashlib.sha256(identity.encode()).hexdigest()
        key = f"sprintern:rate:{rule.name}:{identity_hash}"
        try:
            result = cast(
                Any,
                self.client.eval(
                    self._CHECK,
                    1,
                    key,
                    str(now_ms - window_ms),
                    str(now_ms),
                    str(rule.requests),
                    f"{now_ms}:{uuid.uuid4()}",
                    str(window_ms),
                ),
            )
            allowed, count, first_ms = result
        except redis.RedisError as exc:
            raise AppError(
                503,
                "rate_limit_unavailable",
                "Request protection is temporarily unavailable",
            ) from exc
        retry_after = max(1, math.ceil((int(first_ms) + window_ms - now_ms) / 1000))
        if not int(allowed):
            raise AppError(
                429,
                "rate_limited",
                "Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        return max(rule.requests - int(count), 0), retry_after


def build_rate_limiter() -> InMemoryRateLimiter | RedisRateLimiter:
    if settings.rate_limit_backend == "redis" and settings.rate_limit_redis_url:
        return RedisRateLimiter(settings.rate_limit_redis_url)
    return InMemoryRateLimiter()


limiter = build_rate_limiter()


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not any(peer_ip in network for network in settings.trusted_proxy_networks):
        return peer
    forwarded = request.headers.get("X-Forwarded-For", "")
    try:
        chain = [
            ipaddress.ip_address(value.strip()) for value in forwarded.split(",") if value.strip()
        ]
    except ValueError:
        return peer
    for candidate in reversed(chain):
        if not any(candidate in network for network in settings.trusted_proxy_networks):
            return str(candidate)
    return str(chain[0]) if chain else peer


def _enforce(request: Request, response: Response, rule: RateLimit, identity: str) -> None:
    remaining, reset = limiter.check(rule, identity)
    response.headers["X-RateLimit-Limit"] = str(rule.requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset)


def user_rate_limit(name: str, requests: int, window_seconds: int = 60) -> Callable[..., None]:
    rule = RateLimit(name, requests, window_seconds)

    def dependency(
        request: Request,
        response: Response,
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> None:
        _enforce(request, response, rule, f"user:{user.id}")

    return dependency


def ip_rate_limit(name: str, requests: int, window_seconds: int = 60) -> Callable[..., None]:
    rule = RateLimit(name, requests, window_seconds)

    def dependency(request: Request, response: Response) -> None:
        _enforce(request, response, rule, f"ip:{client_ip(request)}")

    return dependency
