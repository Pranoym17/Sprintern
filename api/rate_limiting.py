import ipaddress
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

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


limiter = InMemoryRateLimiter()


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
