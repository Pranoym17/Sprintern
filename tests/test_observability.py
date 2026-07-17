import json
import logging

import httpx
from fastapi import FastAPI

from api.errors import register_exception_handlers
from api.observability import JsonFormatter, configure_logging, request_id_context


async def test_request_id_is_preserved_or_safely_generated(api_client: httpx.AsyncClient) -> None:
    supplied = await api_client.get("/health", headers={"X-Request-ID": "phase10-check.1"})
    generated = await api_client.get("/health", headers={"X-Request-ID": "invalid id with spaces"})

    assert supplied.headers["X-Request-ID"] == "phase10-check.1"
    assert generated.headers["X-Request-ID"] != "invalid id with spaces"
    assert len(generated.headers["X-Request-ID"]) == 36


def test_json_logs_include_correlation_and_redact_secrets() -> None:
    formatter = JsonFormatter()
    configure_logging(secrets=["configured-secret-value"])
    token = request_id_context.set("request-123")
    try:
        record = logging.LogRecord(
            name="sprintern.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=(
                "Bearer header.payload.signature configured-secret-value "
                "123456789:BotTokenValue_1234567890"
            ),
            args=(),
            exc_info=None,
        )
        record.event = "security.redaction_test"
        record.api_key = "never-log-this"
        payload = json.loads(formatter.format(record))
    finally:
        request_id_context.reset(token)

    serialized = json.dumps(payload)
    assert payload["event"] == "security.redaction_test"
    assert payload["request_id"] == "request-123"
    assert payload["api_key"] == "[REDACTED]"
    assert "configured-secret-value" not in serialized
    assert "header.payload.signature" not in serialized
    assert "BotTokenValue" not in serialized


async def test_unexpected_errors_return_no_internal_details() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)

    @test_app.get("/failure")
    def failure() -> None:
        raise RuntimeError("database password leaked-detail")

    transport = httpx.ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/failure")

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "An unexpected error occurred"}
    }
    assert "leaked-detail" not in response.text
