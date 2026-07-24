import argparse
import asyncio
import uuid

import httpx

from api.database import SessionLocal
from api.models import NotificationChannel, Profile
from api.notifications.domain import DeliveryOutcome
from api.notifications.message_builder import build_test_message
from api.notifications.providers import (
    NotificationProvider,
    ResendProvider,
    TelegramProvider,
)
from api.settings import settings


async def run(profile_id: uuid.UUID, channels: list[NotificationChannel]) -> int:
    with SessionLocal() as session:
        profile = session.get(Profile, profile_id)
        if profile is None:
            raise SystemExit("Profile not found")
        recipients = {
            NotificationChannel.EMAIL: profile.email,
            NotificationChannel.TELEGRAM: profile.telegram_chat_id,
        }
    failed = False
    async with httpx.AsyncClient(timeout=15.0) as client:
        providers: dict[NotificationChannel, NotificationProvider] = {
            NotificationChannel.EMAIL: ResendProvider(
                settings.resend_api_key, settings.resend_from_email, client
            ),
            NotificationChannel.TELEGRAM: TelegramProvider(
                settings.telegram_bot_token, client
            ),
        }
        for channel in channels:
            recipient = recipients[channel]
            if not recipient:
                print(f"{channel.value}: skipped (not connected)")
                failed = True
                continue
            result = await providers[channel].send(
                build_test_message(
                    profile_id=profile_id,
                    recipient=recipient,
                    channel=channel,
                    nonce=uuid.uuid4().hex,
                )
            )
            print(
                f"{channel.value}: {result.outcome.value}"
                + (f" ({result.provider_message_id})" if result.provider_message_id else "")
            )
            failed |= result.outcome != DeliveryOutcome.SENT
    return int(failed)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send clearly labelled notification smoke tests without creating deliveries."
    )
    parser.add_argument("--profile-id", type=uuid.UUID, required=True)
    parser.add_argument(
        "--channel",
        action="append",
        choices=[item.value for item in NotificationChannel],
        required=True,
    )
    arguments = parser.parse_args()
    channels = [NotificationChannel(value) for value in arguments.channel]
    raise SystemExit(asyncio.run(run(arguments.profile_id, channels)))


if __name__ == "__main__":
    main()
