from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from app.db.engine import async_session
from app.services import client_service

logger = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session() as session:
            data["session"] = session
            try:
                return await handler(event, data)
            except Exception:
                await session.rollback()
                raise


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Unhandled exception in handler")
            msg = None
            from aiogram.types import Update
            if isinstance(event, Message):
                msg = event
            elif isinstance(event, Update):
                if event.message:
                    msg = event.message
                elif event.callback_query and event.callback_query.message:
                    msg = event.callback_query.message
            if msg:
                try:
                    await msg.answer(
                        "Произошла ошибка. Попробуйте позже или обратитесь к администратору."
                    )
                except Exception:
                    pass
            return None


class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            data["is_admin"] = client_service.is_admin(event.from_user.id)
        return await handler(event, data)
