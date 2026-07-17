import asyncio

from api.observability import configure_logging
from api.scheduler.runtime import run_scheduler
from api.settings import settings


def main() -> None:
    configure_logging(
        secrets=[
            settings.internal_api_key,
            settings.github_token,
            settings.telegram_bot_token,
            settings.telegram_webhook_secret,
            settings.resend_api_key,
        ]
    )
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
