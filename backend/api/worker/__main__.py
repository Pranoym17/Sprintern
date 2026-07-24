import asyncio

from api.observability import configure_error_tracking, configure_logging
from api.settings import settings
from api.worker.runtime import run_worker


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
    configure_error_tracking(
        settings.error_tracking_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
