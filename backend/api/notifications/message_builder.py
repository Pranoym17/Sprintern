import hashlib
import uuid
from typing import cast

from api.models import JobMatch, NotificationChannel, NotificationDelivery
from api.notifications.domain import NotificationMessage
from api.notifications.email_renderer import (
    PublicNotificationJob,
    render_daily_digest,
    render_email_notification,
)
from api.settings import settings


def _public_job(match: JobMatch) -> PublicNotificationJob:
    job = match.job
    return PublicNotificationJob(
        company=job.company,
        title=job.title,
        location=job.location or "Location not specified",
        term=job.term,
        application_url=job.application_url,
    )


def _telegram_match_message(delivery: NotificationDelivery) -> NotificationMessage:
    match = cast(JobMatch, delivery.match)
    job = _public_job(match)
    term = job.term or "Term not specified"
    text = (
        f"🎯 New match: {job.title}\n"
        f"🏢 {job.company}\n"
        f"📍 {job.location} · {term}\n\n"
        f"{job.application_url}"
    )
    return NotificationMessage(
        recipient=delivery.recipient,
        subject=f"New match: {job.title}",
        text=text,
        html="",
        apply_url=job.application_url,
        idempotency_key=delivery.idempotency_key,
    )


def build_message(deliveries: list[NotificationDelivery]) -> NotificationMessage:
    if not deliveries:
        raise ValueError("at least one delivery is required")
    first = deliveries[0]
    if first.match is not None:
        if first.channel == NotificationChannel.TELEGRAM:
            if len(deliveries) != 1:
                raise ValueError("Telegram match messages must contain exactly one posting")
            return _telegram_match_message(first)
        matches = [cast(JobMatch, delivery.match) for delivery in deliveries]
        stable_ids = ":".join(sorted(str(delivery.id) for delivery in deliveries))
        return render_daily_digest(
            profile_id=first.profile_id,
            recipient=first.recipient,
            jobs=[_public_job(match) for match in matches],
            idempotency_key=f"digest:{hashlib.sha256(stable_ids.encode()).hexdigest()}",
        )

    title = str(first.payload.get("title") or "Sprintern update")
    body = str(first.payload.get("body") or "You have a new Sprintern update.")
    apply_url = str(first.payload.get("apply_url") or settings.frontend_url)
    if first.channel == NotificationChannel.EMAIL:
        return render_email_notification(
            profile_id=first.profile_id,
            recipient=first.recipient,
            title=title,
            body=body,
            apply_url=apply_url,
            idempotency_key=first.idempotency_key,
        )
    return NotificationMessage(
        recipient=first.recipient,
        subject=title,
        text=f"{title}\n\n{body}",
        html="",
        apply_url=apply_url,
        idempotency_key=first.idempotency_key,
    )


def build_test_message(
    *,
    profile_id: uuid.UUID,
    recipient: str,
    channel: NotificationChannel,
    nonce: str,
) -> NotificationMessage:
    jobs = [
        PublicNotificationJob(
            company="Northstar Robotics",
            title="Software Engineering Intern",
            location="Toronto, ON",
            term="Summer 2027",
            application_url="https://example.com/jobs/software-intern",
        ),
        PublicNotificationJob(
            company="Cedar Labs",
            title="Backend Developer Intern",
            location="Remote, Canada",
            term="Summer 2027",
            application_url="https://example.com/jobs/backend-intern",
        ),
        PublicNotificationJob(
            company="Signal Works",
            title="Platform Engineering Intern",
            location="Vancouver, BC",
            term="Fall 2027",
            application_url="https://example.com/jobs/platform-intern",
        ),
    ]
    if channel == NotificationChannel.EMAIL:
        return render_daily_digest(
            profile_id=profile_id,
            recipient=recipient,
            jobs=jobs,
            idempotency_key=f"test:{profile_id}:email:{nonce}",
            is_test=True,
        )
    job = jobs[0]
    return NotificationMessage(
        recipient=recipient,
        subject="[Test] New match",
        text=(
            f"🧪 Test notification\n\n"
            f"🎯 New match: {job.title}\n"
            f"🏢 {job.company}\n"
            f"📍 {job.location} · {job.term}\n\n"
            f"{job.application_url}"
        ),
        html="",
        apply_url=job.application_url,
        idempotency_key=f"test:{profile_id}:telegram:{nonce}",
    )
