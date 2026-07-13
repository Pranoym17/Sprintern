import asyncio
import random
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

TRANSIENT_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class SourceHTTPError(Exception):
    pass


class RetryingHTTPClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        max_attempts: int = 4,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 30.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self.client = client
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.sleep = sleep
        self.jitter: Callable[[], float] = jitter

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = await self.client.get(url, **kwargs)
                if response.status_code not in TRANSIENT_STATUS_CODES:
                    response.raise_for_status()
                    return response.json()
                last_error = SourceHTTPError(f"transient HTTP {response.status_code}")
                retry_after = self._retry_after_seconds(response)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                retry_after = None
            except (httpx.HTTPStatusError, ValueError) as exc:
                raise SourceHTTPError("source returned a permanent or invalid response") from exc

            if attempt < self.max_attempts:
                delay = retry_after if retry_after is not None else self._backoff(attempt)
                await self.sleep(min(delay, self.max_delay_seconds))

        raise SourceHTTPError(
            f"source request failed after {self.max_attempts} attempts"
        ) from last_error

    def _backoff(self, attempt: int) -> float:
        exponential = self.base_delay_seconds * pow(2.0, attempt - 1)
        return float(exponential + self.jitter() * 0.25)

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
            except (TypeError, ValueError):
                return None
