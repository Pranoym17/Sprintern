import hashlib
import html

from api.models import JobMatch, JobSourceName, NotificationDelivery
from api.notifications.domain import NotificationMessage


def build_message(deliveries: list[NotificationDelivery]) -> NotificationMessage:
    if not deliveries:
        raise ValueError("at least one delivery is required")
    matches: list[JobMatch] = [delivery.match for delivery in deliveries]
    recipient = deliveries[0].recipient
    if len(matches) == 1:
        match = matches[0]
        job = match.job
        source = job.sources[0]
        source_label = source.source.value.replace("_", " ").title()
        attribution = (
            "Source: Remote OK — view the original listing at Remote OK."
            if source.source == JobSourceName.REMOTEOK
            else f"Source: {source_label}"
        )
        location = job.location or "Location not specified"
        text = f"{job.company} — {job.title}\n{location}\n{attribution}\nApply: {source.apply_url}"
        body = (
            f"<h2>{html.escape(job.company)} — {html.escape(job.title)}</h2>"
            f"<p>{html.escape(location)}</p>"
            f"<p>{html.escape(attribution)}</p>"
            f'<p><a href="{html.escape(source.apply_url, quote=True)}">Apply now</a></p>'
        )
        return NotificationMessage(
            recipient=recipient,
            subject=f"New internship: {job.title} at {job.company}",
            text=text[:4096],
            html=body,
            apply_url=source.apply_url,
            idempotency_key=deliveries[0].idempotency_key,
        )

    lines = ["Your Sprintern internship digest:"]
    html_items: list[str] = []
    for match in matches:
        job = match.job
        source = job.sources[0]
        lines.append(f"- {job.company} — {job.title}: {source.apply_url}")
        html_items.append(
            f"<li>{html.escape(job.company)} — {html.escape(job.title)}: "
            f'<a href="{html.escape(source.apply_url, quote=True)}">Apply</a></li>'
        )
    stable_ids = ":".join(sorted(str(delivery.id) for delivery in deliveries))
    digest_key = f"digest:{hashlib.sha256(stable_ids.encode()).hexdigest()}"
    return NotificationMessage(
        recipient=recipient,
        subject=f"Sprintern digest: {len(matches)} new internships",
        text="\n".join(lines)[:4096],
        html=f"<h2>Your Sprintern internship digest</h2><ul>{''.join(html_items)}</ul>",
        apply_url=matches[0].job.sources[0].apply_url,
        idempotency_key=digest_key,
    )
