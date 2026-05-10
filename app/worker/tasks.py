"""Celery tasks для фоновых операций.

Celery prefork worker не шарит event loop между тасками, поэтому каждая
таска запускается в свежем loop через `_async_run`. Чтобы не плодить
десятки pg-коннекшнов, engine берётся из общей фабрики с маленьким пулом.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.worker.celery_app import celery

logger = logging.getLogger(__name__)


# ──────────────── Async helpers ────────────────


def _async_run(coro):
    """Свежий event loop на таску (prefork worker)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@asynccontextmanager
async def _session() -> AsyncIterator[AsyncSession]:
    """Короткоживущий engine + session на одну таску.

    Пул маленький (2/0) — каждая таска всё равно выполняется одна за раз
    внутри своего loop, большой пул только жрёт пг-коннекшны.
    """
    engine = create_async_engine(
        settings.database_url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )
    try:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()


# ──────────────── Проверка платежей ────────────────


@celery.task(name="app.worker.tasks.check_pending_payments")
def check_pending_payments() -> None:
    _async_run(_check_pending_payments())


async def _check_pending_payments() -> None:
    from app.db.repo import PaymentRepo
    from app.services.subscription_service import check_and_activate

    async with _session() as session:
        repo = PaymentRepo(session)
        pending = await repo.get_pending()

    for payment in pending:
        age = (datetime.utcnow() - payment.created_at).total_seconds()
        if age < 30:
            continue
        if age > 7200:
            async with _session() as session:
                await PaymentRepo(session).mark_cancelled(payment.id)
            continue
        try:
            async with _session() as session:
                await check_and_activate(session, payment.id)
        except Exception:
            logger.exception("check_and_activate failed for payment %s", payment.id)


# ──────────────── Истечение подписок ────────────────


@celery.task(name="app.worker.tasks.expire_subscriptions")
def expire_subscriptions() -> None:
    _async_run(_expire_subscriptions())


async def _expire_subscriptions() -> None:
    from app.db.repo import SubRepo
    from app.services.subscription_service import expire_subscription

    now = datetime.utcnow()
    async with _session() as session:
        expired = await SubRepo(session).get_expired(now)

    for sub in expired:
        try:
            async with _session() as session:
                await expire_subscription(session, sub.id)
            await _notify_user(sub.user_id, "expired")
        except Exception:
            logger.exception("expire_subscription failed for sub %s", sub.id)


# ──────────────── Напоминания об истечении ────────────────


@celery.task(name="app.worker.tasks.send_expiry_reminders")
def send_expiry_reminders() -> None:
    _async_run(_send_expiry_reminders())


async def _send_expiry_reminders() -> None:
    from app.db.repo import SubRepo

    now = datetime.utcnow()
    tomorrow = now + timedelta(hours=24)

    async with _session() as session:
        expiring = await SubRepo(session).get_expiring_soon(now, tomorrow)

    for sub in expiring:
        try:
            await _notify_user(sub.user_id, "expiring")
            async with _session() as session:
                await SubRepo(session).mark_notified(sub.id)
        except Exception:
            logger.exception("reminder failed for sub %s", sub.id)


# ──────────────── Healthcheck серверов ────────────────


@celery.task(name="app.worker.tasks.healthcheck_servers")
def healthcheck_servers() -> None:
    _async_run(_healthcheck_servers())


async def _healthcheck_servers() -> None:
    from app.services import vpn_service

    try:
        await vpn_service.healthcheck()
    except Exception:
        logger.exception("healthcheck failed")
    finally:
        await vpn_service.close()


# ──────────────── Очистка старых платежей ────────────────


@celery.task(name="app.worker.tasks.cleanup_stale_payments")
def cleanup_stale_payments() -> None:
    _async_run(_cleanup_stale_payments())


async def _cleanup_stale_payments() -> None:
    from app.db.repo import PaymentRepo

    async with _session() as session:
        pending = await PaymentRepo(session).get_pending()
        stale_ids = [
            p.id for p in pending
            if (datetime.utcnow() - p.created_at).total_seconds() > 86400
        ]
        for pid in stale_ids:
            await PaymentRepo(session).mark_cancelled(pid)


# ──────────────── Уведомления пользователей ────────────────


async def _notify_user(user_id: int, event: str) -> None:
    from aiogram import Bot
    from app.bot import keyboards, texts
    from app.db.models import User

    async with _session() as session:
        user = await session.get(User, user_id)

    if not user or not user.telegram_id:
        return

    bot = Bot(token=settings.bot_token)
    try:
        if event == "expiring":
            await bot.send_message(
                user.telegram_id,
                texts.EXPIRY_REMINDER,
                reply_markup=keyboards.renew_prompt(),
                parse_mode="HTML",
            )
        elif event == "expired":
            await bot.send_message(
                user.telegram_id,
                texts.SUB_EXPIRED,
                reply_markup=keyboards.renew_prompt(),
                parse_mode="HTML",
            )
    except Exception:
        logger.exception("notify_user failed: user=%s event=%s", user_id, event)
    finally:
        await bot.session.close()
