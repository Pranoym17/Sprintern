import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import AuthenticatedUser
from api.models import EmailProviderEvent, EmailSuppression, JobFilter, Profile
from api.notifications.email_preferences import UnsubscribeTokenService
from api.routes import profiles
from api.settings import settings


async def test_email_requires_explicit_consent(
    api_client: httpx.AsyncClient, db_session: Session, authenticated_user: AuthenticatedUser
) -> None:
    initial = await api_client.get("/users/me")
    enabled = await api_client.patch("/users/me", json={"email_notifications_enabled": True})
    profile = db_session.get(Profile, authenticated_user.id)

    assert initial.json()["email_notifications_enabled"] is False
    assert enabled.status_code == 200
    assert enabled.json()["email_notifications_enabled"] is True
    assert profile is not None and profile.email_notifications_consent_at is not None


async def test_user_controls_daily_digest_time_and_size(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.patch(
        "/users/me",
        json={
            "timezone": "America/Toronto",
            "preferred_email_time": "07:45",
            "email_digest_job_limit": 10,
            "email_empty_digest_enabled": True,
        },
    )
    invalid = await api_client.patch(
        "/users/me", json={"email_digest_job_limit": 11}
    )

    assert response.status_code == 200
    assert response.json()["preferred_email_time"] == "07:45:00"
    assert response.json()["email_digest_job_limit"] == 10
    assert response.json()["email_empty_digest_enabled"] is True
    assert invalid.status_code == 422


async def test_signed_unsubscribe_link_disables_email_and_rejects_tampering(
    api_client: httpx.AsyncClient, db_session: Session, authenticated_user: AuthenticatedUser
) -> None:
    profile = Profile(
        id=authenticated_user.id,
        email=authenticated_user.email,
        email_notifications_enabled=True,
        email_notifications_consent_at=datetime.now(UTC),
    )
    db_session.add(profile)
    db_session.commit()
    service = UnsubscribeTokenService(settings.unsubscribe_signing_secret, settings.public_api_url)
    token = service.create(profile.id, profile.email or "")

    response = await api_client.get("/email/unsubscribe", params={"token": token})
    db_session.refresh(profile)
    tampered = await api_client.get("/email/unsubscribe", params={"token": token + "x"})

    assert response.status_code == 200
    assert profile.email_notifications_enabled is False
    assert profile.email_notifications_consent_at is None
    assert tampered.status_code == 400


async def test_export_is_scoped_to_authenticated_owner(
    api_client: httpx.AsyncClient, db_session: Session, authenticated_user: AuthenticatedUser
) -> None:
    owner = Profile(id=authenticated_user.id, email=authenticated_user.email)
    other = Profile(id=uuid.uuid4(), email="other@example.com")
    owner.filters.append(JobFilter(name="Mine"))
    other.filters.append(JobFilter(name="Other private filter"))
    db_session.add_all([owner, other])
    db_session.commit()

    response = await api_client.get("/users/me/export")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["id"] == str(authenticated_user.id)
    assert [item["name"] for item in body["filters"]] == ["Mine"]
    assert "Other private filter" not in response.text


async def test_delete_account_requires_confirmation_and_deletes_auth_and_data(
    api_client: httpx.AsyncClient,
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = Profile(id=authenticated_user.id, email=authenticated_user.email)
    profile.filters.append(JobFilter(name="Delete me"))
    other = Profile(id=uuid.uuid4(), email="other-delete@example.com")
    other.filters.append(JobFilter(name="Keep me"))
    db_session.add_all([profile, other])
    db_session.commit()
    deleted_ids: list[uuid.UUID] = []

    async def delete_user(user_id: uuid.UUID) -> None:
        deleted_ids.append(user_id)

    monkeypatch.setattr(profiles.auth_admin, "delete_user", delete_user)

    rejected = await api_client.request("DELETE", "/users/me", json={"confirmation": "delete"})
    accepted = await api_client.request("DELETE", "/users/me", json={"confirmation": "DELETE"})

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    assert accepted.json() == {
        "application_data_deleted": True,
        "auth_identity_deleted": True,
    }
    assert deleted_ids == [authenticated_user.id]
    assert db_session.get(Profile, authenticated_user.id) is None
    assert db_session.get(Profile, other.id) is not None
    assert db_session.scalar(select(JobFilter).where(JobFilter.name == "Delete me")) is None
    assert db_session.scalar(select(JobFilter).where(JobFilter.name == "Keep me")) is not None


async def test_resend_bounce_is_verified_idempotent_and_suppresses_email(
    api_client: httpx.AsyncClient,
    db_session: Session,
    authenticated_user: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    webhook_secret = base64.b64encode(b"test-webhook-secret").decode()
    monkeypatch.setattr(settings, "resend_webhook_secret", f"whsec_{webhook_secret}")
    profile = Profile(
        id=authenticated_user.id,
        email="Student@Example.com",
        email_notifications_enabled=True,
        email_notifications_consent_at=datetime.now(UTC),
    )
    db_session.add(profile)
    db_session.commit()
    payload = {
        "id": "event-1",
        "type": "email.bounced",
        "data": {"to": ["student@example.com"]},
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    message_id = "msg-1"
    timestamp = str(int(time.time()))
    signed = f"{message_id}.{timestamp}.".encode() + body
    signature = base64.b64encode(
        hmac.new(b"test-webhook-secret", signed, hashlib.sha256).digest()
    ).decode()
    headers = {
        "svix-id": message_id,
        "svix-timestamp": timestamp,
        "svix-signature": f"v1,{signature}",
        "content-type": "application/json",
    }

    first = await api_client.post("/webhooks/resend", headers=headers, content=body)
    second = await api_client.post("/webhooks/resend", headers=headers, content=body)
    db_session.refresh(profile)

    assert first.status_code == 204
    assert second.status_code == 204
    assert profile.email_notifications_enabled is False
    assert profile.email_suppression_reason == "bounce"
    assert db_session.get(EmailSuppression, "student@example.com") is not None
    assert len(list(db_session.scalars(select(EmailProviderEvent)))) == 1


async def test_resend_webhook_rejects_invalid_signature(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/webhooks/resend",
        headers={
            "svix-id": "msg",
            "svix-timestamp": str(int(time.time())),
            "svix-signature": "v1,invalid",
        },
        json={"id": "event", "type": "email.bounced", "data": {"to": []}},
    )

    assert response.status_code in {401, 503}
