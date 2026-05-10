"""Инициализация и запуск Telegram-бота."""
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.db.engine import engine
from app.bot.middlewares import (
    DbSessionMiddleware,
    ErrorMiddleware,
    AdminMiddleware,
)
from app.bot.handlers import router as handlers_router
from app.services import vpn_service


async def on_startup(bot: Bot) -> None:
    # Схема БД создаётся/обновляется ТОЛЬКО через Alembic (`bash migrate.sh`).
    # Здесь ничего не создаём — бот просто начинает работать с имеющейся БД.
    from app.db.engine import async_session
    from app.services.client_service import init_client

    async with async_session() as session:
        await init_client(session, settings.bot_token)

    try:
        await vpn_service.get_manager()
    except Exception:
        pass


async def on_shutdown(bot: Bot) -> None:
    await vpn_service.close()
    await engine.dispose()


def create_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(AdminMiddleware())
    dp.update.middleware(ErrorMiddleware())
    dp.include_router(handlers_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return bot, dp


async def run() -> None:
    bot, dp = create_bot()
    await dp.start_polling(bot)
