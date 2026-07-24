import hashlib
import html
from typing import cast
from urllib.parse import urlparse

from api.models import (
    JobMatch,
    JobSource,
    JobSourceName,
    NotificationChannel,
    NotificationDelivery,
)
from api.notifications.domain import NotificationMessage
from api.notifications.email_preferences import UnsubscribeTokenService
from api.settings import settings

unsubscribe_tokens = UnsubscribeTokenService(
    settings.unsubscribe_signing_secret, settings.public_api_url
)


def _preferred_source(match: JobMatch) -> JobSource:
    """Prefer a direct application destination when a job overlaps across sources."""
    return cast(
        JobSource,
        min(
            match.job.sources,
            key=lambda source: (
                urlparse(source.apply_url).hostname in {"github.com", "www.github.com"},
                source.source == JobSourceName.GITHUB_REPO,
            ),
        ),
    )


def build_message(deliveries: list[NotificationDelivery]) -> NotificationMessage:
    if not deliveries:
        raise ValueError("at least one delivery is required")
    if deliveries[0].match is None:
        delivery = deliveries[0]
        profile = delivery.profile
        recipient = delivery.recipient
        is_email = delivery.channel == NotificationChannel.EMAIL
        unsubscribe_url = unsubscribe_tokens.url(profile.id, recipient) if is_email else None
        title = str(delivery.payload.get("title") or "Sprintern update")
        body_text = str(delivery.payload.get("body") or "You have a new Sprintern update.")
        apply_url = str(delivery.payload.get("apply_url") or settings.public_api_url)
        support = settings.support_email
        footer = (
            f"\n\nUnsubscribe: {unsubscribe_url}\nSupport: {support}" if unsubscribe_url else ""
        )
        html_footer = (
            f'<hr><p><a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe</a>'
            f" &middot; Contact {html.escape(support)}</p>"
            if unsubscribe_url
            else ""
        )
        return NotificationMessage(
            recipient=recipient,
            subject=title,
            text=f"{title}\n{body_text}{footer}"[:4096],
            html=f"<h2>{html.escape(title)}</h2><p>{html.escape(body_text)}</p>{html_footer}",
            apply_url=apply_url,
            idempotency_key=delivery.idempotency_key,
            unsubscribe_url=unsubscribe_url,
        )
    matches: list[JobMatch] = [cast(JobMatch, delivery.match) for delivery in deliveries]
    recipient = deliveries[0].recipient
    profile = matches[0].profile
    is_email = deliveries[0].channel == NotificationChannel.EMAIL
    unsubscribe_url = unsubscribe_tokens.url(profile.id, recipient) if is_email else None
    support = settings.support_email
    text_footer = (
        f"\n\nUnsubscribe: {unsubscribe_url}\nSupport: {support}" if unsubscribe_url else ""
    )
    html_footer = (
        f'<hr><p><a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe</a>'
        f" &middot; Contact {html.escape(support)}</p>"
        if unsubscribe_url
        else ""
    )
    if len(matches) == 1:
        match = matches[0]
        job = match.job
        source = _preferred_source(match)
        source_label = source.source.value.replace("_", " ").title()
        attribution = (
            "Source: Remote OK — view the original listing at Remote OK."
            if source.source == JobSourceName.REMOTEOK
            else f"Source: {source_label}"
        )
        location = job.location or "Location not specified"
        text = (
            f"{job.company} — {job.title}\n{location}\n{attribution}\nApply: {source.apply_url}"
            f"{text_footer}"
        )
        body = (
            f"<h2>{html.escape(job.company)} — {html.escape(job.title)}</h2>"
            f"<p>{html.escape(location)}</p>"
            f"<p>{html.escape(attribution)}</p>"
            f'<p><a href="{html.escape(source.apply_url, quote=True)}">Apply now</a></p>'
            f"{html_footer}"
        )
        return NotificationMessage(
            recipient=recipient,
            subject=f"New internship: {job.title} at {job.company}",
            text=text[:4096],
            html=body,
            apply_url=source.apply_url,
            idempotency_key=deliveries[0].idempotency_key,
            unsubscribe_url=unsubscribe_url,
        )

    lines = ["Your Sprintern internship digest:"]
    html_items: list[str] = []
    for match in matches:
        job = match.job
        source = _preferred_source(match)
        lines.append(f"- {job.company} — {job.title}: {source.apply_url}")
        html_items.append(
            f"<li>{html.escape(job.company)} — {html.escape(job.title)}: "
            f'<a href="{html.escape(source.apply_url, quote=True)}">Apply</a></li>'
        )
    stable_ids = ":".join(sorted(str(delivery.id) for delivery in deliveries))
    digest_key = f"digest:{hashlib.sha256(stable_ids.encode()).hexdigest()}"
    if unsubscribe_url:
        lines.extend(["", f"Unsubscribe: {unsubscribe_url}", f"Support: {support}"])
    return NotificationMessage(
        recipient=recipient,
        subject=f"Sprintern digest: {len(matches)} new internships",
        text="\n".join(lines)[:4096],
        html=(
            f"<h2>Your Sprintern internship digest</h2><ul>{''.join(html_items)}</ul>{html_footer}"
        ),
        apply_url=_preferred_source(matches[0]).apply_url,
        idempotency_key=digest_key,
        unsubscribe_url=unsubscribe_url,
    )
