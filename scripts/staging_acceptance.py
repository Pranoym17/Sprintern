"""Run a reversible staging smoke test with two dedicated Supabase users.

Required environment:
STAGING_API_URL, STAGING_USER_TOKEN, STAGING_SECOND_USER_TOKEN, STAGING_INTERNAL_API_KEY.
Set STAGING_TEST_EMAIL/TELEGRAM=true only after those channels are connected for user one.
"""

import os
import sys
import uuid
from typing import Any

import httpx


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def expect(response: httpx.Response, status: int) -> Any:
    if response.status_code != status:
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path} returned "
            f"{response.status_code}: {response.text[:500]}"
        )
    return response.json() if response.content else None


def enabled(name: str) -> bool:
    return os.getenv(name, "").casefold() in {"1", "true", "yes"}


def main() -> int:
    base_url = required("STAGING_API_URL").rstrip("/")
    token_one = required("STAGING_USER_TOKEN")
    token_two = required("STAGING_SECOND_USER_TOKEN")
    internal_key = required("STAGING_INTERNAL_API_KEY")
    first = {"Authorization": f"Bearer {token_one}"}
    second = {"Authorization": f"Bearer {token_two}"}
    internal = {"X-Internal-API-Key": internal_key}
    filter_id = ""

    with httpx.Client(base_url=base_url, timeout=20.0) as client:
        expect(client.get("/health/live"), 200)
        expect(client.get("/health/ready"), 200)
        expect(client.get("/users/me", headers=first), 200)
        expect(client.get("/users/me", headers=second), 200)
        launch = expect(client.get("/internal/launch/readiness", headers=internal), 200)
        if not launch["ready"]:
            missing = [item["key"] for item in launch["checks"] if not item["configured"]]
            raise RuntimeError(f"Launch controls are incomplete: {', '.join(missing)}")

        created = expect(
            client.post(
                "/filters",
                headers=first,
                json={
                    "name": f"Staging acceptance {uuid.uuid4().hex[:8]}",
                    "role_keywords": ["software"],
                    "location_keywords": ["Canada", "Remote"],
                    "terms": ["Summer 2027"],
                },
            ),
            201,
        )
        filter_id = created["id"]
        expect(client.get(f"/filters/{filter_id}", headers=first), 200)
        expect(client.get(f"/filters/{filter_id}", headers=second), 404)
        expect(client.get("/matches?limit=10", headers=first), 200)
        expect(client.get("/users/me/export", headers=first), 200)

        for channel, flag in (
            ("email", "STAGING_TEST_EMAIL"),
            ("telegram", "STAGING_TEST_TELEGRAM"),
        ):
            if enabled(flag):
                result = expect(
                    client.post("/notifications/test", headers=first, json={"channel": channel}),
                    200,
                )
                if result["outcome"] != "sent":
                    raise RuntimeError(f"{channel} test failed: {result.get('error')}")

        monitoring = expect(
            client.get("/internal/monitoring/status", headers=internal), 200
        )
        if monitoring["state"] != "healthy":
            raise RuntimeError(f"Operational monitoring is degraded: {monitoring}")

        expect(client.delete(f"/filters/{filter_id}", headers=first), 204)
        filter_id = ""

    print("Staging acceptance checks passed.")
    print("Manually verify received messages, application links, reminders, and account deletion.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"Staging acceptance failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
