import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.database import get_db
from api.errors import AppError
from api.models import EmailProviderEvent
from api.notifications.email_preferences import (
    UnsubscribeTokenService,
    suppress_email,
    unsubscribe_profile,
)
from api.rate_limiting import ip_rate_limit
from api.settings import settings

router = APIRouter(tags=["email"])
unsubscribe_tokens = UnsubscribeTokenService(
    settings.unsubscribe_signing_secret, settings.public_api_url
)
Database = Annotated[Session, Depends(get_db)]


def _verify_resend_signature(body: bytes, message_id: str, timestamp: str, signature: str) -> None:
    if not settings.resend_webhook_secret:
        raise AppError(503, "not_configured", "Email webhook is not configured")
    if not message_id or not timestamp or not signature:
        raise AppError(401, "invalid_webhook_signature", "Webhook signature is invalid")
    try:
        timestamp_value = int(timestamp)
    except (ValueError, binascii.Error) as exc:
        raise AppError(401, "invalid_webhook_signature", "Webhook signature is invalid") from exc
    if abs(int(time.time()) - timestamp_value) > 300:
        raise AppError(401, "invalid_webhook_signature", "Webhook signature is invalid")
    secret_value = settings.resend_webhook_secret
    if secret_value.startswith("whsec_"):
        secret_value = secret_value[6:]
    try:
        secret = base64.b64decode(secret_value)
    except ValueError as exc:
        raise AppError(503, "not_configured", "Email webhook is not configured") from exc
    signed = f"{message_id}.{timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(secret, signed, hashlib.sha256).digest()).decode()
    candidates = [part[3:] for part in signature.split() if part.startswith("v1,")]
    if not candidates or not any(hmac.compare_digest(value, expected) for value in candidates):
        raise AppError(401, "invalid_webhook_signature", "Webhook signature is invalid")


@router.get(
    "/email/unsubscribe",
    response_class=HTMLResponse,
    dependencies=[Depends(ip_rate_limit("email.unsubscribe", 30))],
)
def unsubscribe_email(token: str, session: Database) -> HTMLResponse:
    profile_id, fingerprint = unsubscribe_tokens.verify(token)
    unsubscribe_profile(session, profile_id, fingerprint)
    session.commit()
    return HTMLResponse(
        "<!doctype html><html><head><meta name='viewport' content='width=device-width'>"
        "<title>Email alerts disabled</title></head><body>"
        "<main><h1>Email alerts disabled</h1>"
        "<p>You will no longer receive Sprintern email alerts. "
        "You can change this later in notification settings.</p></main></body></html>"
    )


@router.post(
    "/email/unsubscribe",
    response_class=HTMLResponse,
    dependencies=[Depends(ip_rate_limit("email.unsubscribe", 30))],
)
def one_click_unsubscribe(token: str, session: Database) -> HTMLResponse:
    return unsubscribe_email(token, session)


@router.post(
    "/webhooks/resend",
    status_code=204,
    dependencies=[Depends(ip_rate_limit("webhooks.resend", 120))],
)
async def resend_webhook(request: Request, session: Database) -> Response:
    body = await request.body()
    message_id = request.headers.get("svix-id", "")
    timestamp = request.headers.get("svix-timestamp", "")
    signature = request.headers.get("svix-signature", "")
    _verify_resend_signature(body, message_id, timestamp, signature)
    try:
        payload: dict[str, Any] = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AppError(400, "invalid_webhook_payload", "Webhook payload is invalid") from exc
    event_id = str(payload.get("id") or message_id)
    event_type = str(payload.get("type") or "")
    if session.get(EmailProviderEvent, event_id) is not None:
        return Response(status_code=204)
    session.add(EmailProviderEvent(id=event_id, event_type=event_type))
    if event_type in {"email.bounced", "email.complained", "email.suppressed"}:
        data = payload.get("data")
        recipients = data.get("to", []) if isinstance(data, dict) else []
        if isinstance(recipients, str):
            recipients = [recipients]
        reason = {
            "email.bounced": "bounce",
            "email.complained": "complaint",
            "email.suppressed": "provider_suppressed",
        }[event_type]
        for recipient in recipients:
            if isinstance(recipient, str) and recipient.strip():
                suppress_email(session, recipient, reason)
    session.commit()
    return Response(status_code=204)
