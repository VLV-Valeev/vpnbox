#!/usr/bin/env python3
"""Entry point для запуска Telegram-бота."""
import asyncio

from app.config import settings
from app.logging_config import setup_logging


def main() -> None:
    setup_logging()
    settings.require("bot_token")
    settings.require("database_url")
    settings.require("redis_url")

    from app.bot.main import run
    asyncio.run(run())


if __name__ == "__main__":
    main()
