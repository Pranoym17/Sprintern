import uuid
from dataclasses import dataclass

from jinja2 import Environment, PackageLoader, StrictUndefined

from api.notifications.domain import NotificationMessage
from api.notifications.email_preferences import UnsubscribeTokenService
from api.settings import settings

environment = Environment(
    loader=PackageLoader("api.notifications", "templates"),
    autoescape=lambda name: bool(name and ".html" in name),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
unsubscribe_tokens = UnsubscribeTokenService(
    settings.unsubscribe_signing_secret, settings.public_api_url
)


@dataclass(frozen=True)
class PublicNotificationJob:
    company: str
    title: str
    location: str
    term: str | None
    application_url: str


def _common_context(profile_id: uuid.UUID, recipient: str) -> dict[str, str]:
    frontend = settings.frontend_url.rstrip("/")
    return {
        "filters_url": f"{frontend}/filters",
        "settings_url": f"{frontend}/settings",
        "unsubscribe_url": unsubscribe_tokens.url(profile_id, recipient),
        "support_email": settings.support_email,
    }


def render_daily_digest(
    *,
    profile_id: uuid.UUID,
    recipient: str,
    jobs: list[PublicNotificationJob],
    idempotency_key: str,
    is_test: bool = False,
) -> NotificationMessage:
    if not jobs:
        raise ValueError("a daily digest requires at least one job")
    count = len(jobs)
    subject = f"{count} new internship {'match' if count == 1 else 'matches'} for you today"
    if is_test:
        subject = f"[Test] {subject}"
    common = _common_context(profile_id, recipient)
    context = {
        **common,
        "subject": subject,
        "jobs": jobs,
    }
    return NotificationMessage(
        recipient=recipient,
        subject=subject,
        text=environment.get_template("daily_digest.txt.j2").render(context).strip(),
        html=environment.get_template("daily_digest.html.j2").render(context),
        apply_url=jobs[0].application_url,
        idempotency_key=idempotency_key,
        unsubscribe_url=common["unsubscribe_url"],
    )


def render_email_notification(
    *,
    profile_id: uuid.UUID,
    recipient: str,
    title: str,
    body: str,
    apply_url: str,
    idempotency_key: str,
    is_test: bool = False,
) -> NotificationMessage:
    subject = f"[Test] {title}" if is_test else title
    common = _common_context(profile_id, recipient)
    context = {
        **common,
        "subject": subject,
        "title": subject,
        "body": body,
    }
    return NotificationMessage(
        recipient=recipient,
        subject=subject,
        text=environment.get_template("notification.txt.j2").render(context).strip(),
        html=environment.get_template("notification.html.j2").render(context),
        apply_url=apply_url,
        idempotency_key=idempotency_key,
        unsubscribe_url=common["unsubscribe_url"],
    )
