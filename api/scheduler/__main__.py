import asyncio
import logging

from api.scheduler.runtime import run_scheduler


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
