from typing import Any, Protocol

import httpx

from api.notifications.domain import (
    DeliveryOutcome,
    NotificationMessage,
    ProviderResult,
)


class NotificationProvider(Protocol):
    async def send(self, message: NotificationMessage) -> ProviderResult: ...


class TelegramProvider:
    def __init__(self, token: str, client: httpx.AsyncClient) -> None:
        self.token = token
        self.client = client

    async def send(self, message: NotificationMessage) -> ProviderResult:
        if not self.token:
            return ProviderResult(
                DeliveryOutcome.PERMANENT_FAILURE, error="Telegram provider is not configured"
            )
        try:
            response = await self.client.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": message.recipient,
                    "text": message.text[:4096],
                    **(
                        {"parse_mode": message.telegram_parse_mode}
                        if message.telegram_parse_mode
                        else {}
                    ),
                    "link_preview_options": {"is_disabled": True},
                    "reply_markup": {
                        "inline_keyboard": [[{"text": "Apply", "url": message.apply_url}]]
                    },
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return ProviderResult(DeliveryOutcome.TRANSIENT_FAILURE, error=type(exc).__name__)
        payload = self._json(response)
        if response.status_code == 429:
            retry_after = (payload.get("parameters") or {}).get("retry_after")
            return ProviderResult(
                DeliveryOutcome.RATE_LIMITED,
                error="Telegram rate limit",
                retry_after_seconds=float(retry_after) if retry_after is not None else None,
            )
        if response.status_code >= 500:
            return ProviderResult(
                DeliveryOutcome.TRANSIENT_FAILURE, error=f"Telegram HTTP {response.status_code}"
            )
        if response.status_code >= 400 or not payload.get("ok"):
            return ProviderResult(
                DeliveryOutcome.PERMANENT_FAILURE,
                error=(
                    f"Telegram rejected message: {payload.get('description', response.status_code)}"
                ),
            )
        message_id = (payload.get("result") or {}).get("message_id")
        return ProviderResult(
            DeliveryOutcome.SENT,
            provider_message_id=str(message_id) if message_id is not None else None,
        )

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except ValueError:
            return {}


class ResendProvider:
    def __init__(self, api_key: str, from_email: str, client: httpx.AsyncClient) -> None:
        self.api_key = api_key
        self.from_email = from_email
        self.client = client

    async def send(self, message: NotificationMessage) -> ProviderResult:
        if not self.api_key or not self.from_email:
            return ProviderResult(
                DeliveryOutcome.PERMANENT_FAILURE, error="Email provider is not configured"
            )
        try:
            response = await self.client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": message.idempotency_key,
                },
                json={
                    "from": self.from_email,
                    "to": [message.recipient],
                    "subject": message.subject.replace("\r", " ").replace("\n", " "),
                    "text": message.text,
                    "html": message.html,
                    **(
                        {
                            "headers": {
                                "List-Unsubscribe": f"<{message.unsubscribe_url}>",
                                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                            }
                        }
                        if message.unsubscribe_url
                        else {}
                    ),
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            return ProviderResult(DeliveryOutcome.TRANSIENT_FAILURE, error=type(exc).__name__)
        if response.status_code == 429:
            return ProviderResult(
                DeliveryOutcome.RATE_LIMITED,
                error="Resend rate limit",
                retry_after_seconds=self._retry_after(response),
            )
        if response.status_code >= 500:
            return ProviderResult(
                DeliveryOutcome.TRANSIENT_FAILURE, error=f"Resend HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            return ProviderResult(
                DeliveryOutcome.PERMANENT_FAILURE,
                error=f"Resend rejected message with HTTP {response.status_code}",
            )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        message_id = payload.get("id") if isinstance(payload, dict) else None
        return ProviderResult(
            DeliveryOutcome.SENT,
            provider_message_id=str(message_id) if message_id is not None else None,
        )

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        try:
            return float(response.headers["Retry-After"])
        except (KeyError, ValueError):
            return None
