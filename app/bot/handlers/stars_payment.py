"""Оплата через Telegram Stars (XTR).

Поток:
  pay:{plan_id}:stars  →  send_invoice (внутри Telegram, без внешней ссылки)
  pre_checkout_query   →  approve (обязательно в течение 10 сек)
  successful_payment   →  записать в БД + активировать подписку

Polling не нужен — Telegram сам присылает successful_payment при успехе.
"""
from __future__ import annotations

import logging

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PLANS
from app.bot import texts, keyboards
from app.db.repo import UserRepo, PaymentRepo
from app.services.subscription_service import _activate_paid_subscription
from app.services.client_service import get_client, get_stars_rate

router = Router()
logger = logging.getLogger(__name__)


def _stars_amount(plan_id: str) -> int:
    """Стоимость тарифа в Telegram Stars (целое число)."""
    return PLANS[plan_id].price * get_stars_rate()


# ──────────────── Отправка инвойса ────────────────


@router.callback_query(F.data.startswith("pay:") & F.data.endswith(":stars"))
async def send_stars_invoice(callback: CallbackQuery, bot: Bot) -> None:
    parts = callback.data.split(":")   # ["pay", plan_id, "stars"]
    plan_id = parts[1]
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    stars = _stars_amount(plan_id)
    # payload передаётся обратно в successful_payment verbatim
    payload = f"{plan_id}:{callback.from_user.id}"

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{get_client().service_name} — {plan.name}",
        description=plan.description,
        payload=payload,
        provider_token="",   # ОБЯЗАТЕЛЬНО пустая строка для XTR
        currency="XTR",
        prices=[LabeledPrice(label=plan.name, amount=stars)],
    )
    await callback.answer()


# ──────────────── Pre-checkout (обязательный шаг) ────────────────


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    """Telegram требует ответа в течение 10 секунд, иначе платёж отменяется."""
    await query.answer(ok=True)


# ──────────────── Успешная оплата ────────────────


@router.message(F.successful_payment)
async def on_successful_payment(message: Message, session: AsyncSession) -> None:
    sp = message.successful_payment
    if sp.currency != "XTR":
        return  # не наш Stars-платёж

    payload_parts = sp.invoice_payload.split(":")
    plan_id = payload_parts[0]
    charge_id = sp.telegram_payment_charge_id  # хранить для возможного возврата

    # ── Получаем пользователя ──
    user = await UserRepo(session).get_by_tg(message.from_user.id)
    if not user:
        logger.error("stars payment: user not found tg_id=%s", message.from_user.id)
        await message.answer(
            "✅ Оплата получена!\n\n"
            "⚠️ Не удалось найти ваш аккаунт — обратитесь в поддержку.",
            parse_mode="HTML",
        )
        return

    plan = PLANS.get(plan_id)
    if not plan:
        logger.error("stars payment: unknown plan_id=%s", plan_id)
        await message.answer(
            "✅ Оплата получена!\n\n"
            "⚠️ Неизвестный тариф — обратитесь в поддержку.",
            parse_mode="HTML",
        )
        return

    pay_repo = PaymentRepo(session)

    # ── Создаём запись платежа — сразу succeeded (Stars confirmed on Telegram side) ──
    try:
        db_payment = await pay_repo.create(
            user_id=user.id,
            plan_id=plan_id,
            amount=sp.total_amount,   # количество Stars
            currency="XTR",
            provider="stars",
            provider_payment_id=charge_id,
            confirmation_url=None,
        )
        await pay_repo.mark_succeeded(db_payment.id, charge_id)
        # Рефрешим объект после commit чтобы все атрибуты были актуальны
        await session.refresh(db_payment)
    except Exception:
        logger.exception(
            "stars: failed to save payment for user %s plan %s", user.id, plan_id
        )
        await message.answer(
            "✅ Оплата получена!\n\n"
            "⚠️ Ошибка записи платежа — обратитесь в поддержку.\n"
            f"Charge ID: <code>{charge_id}</code>",
            parse_mode="HTML",
        )
        return

    # ── Активируем подписку ──
    try:
        result = await _activate_paid_subscription(session, db_payment)
    except Exception:
        logger.exception(
            "stars: _activate_paid_subscription failed for user %s plan %s",
            user.id, plan_id,
        )
        await message.answer(
            "✅ Оплата получена!\n\n"
            "⚠️ Ошибка активации подписки — обратитесь в поддержку.\n"
            f"Charge ID: <code>{charge_id}</code>",
            parse_mode="HTML",
        )
        return

    if not result.get("ok"):
        error = result.get("error", "unknown")
        logger.error(
            "stars: activation returned ok=False for user %s plan %s error=%s",
            user.id, plan_id, error,
        )
        if error == "no_servers":
            text_body = (
                "✅ Оплата получена!\n\n"
                "⚠️ VPN-серверы временно недоступны — подписка будет активирована вручную. "
                "Обратитесь в поддержку."
            )
        else:
            text_body = (
                "✅ Оплата получена!\n\n"
                f"⚠️ Ошибка активации ({error}) — обратитесь в поддержку.\n"
                f"Charge ID: <code>{charge_id}</code>"
            )
        await message.answer(text_body, parse_mode="HTML")
        return

    # ── Успех ──
    await message.answer(
        texts.PAYMENT_SUCCESS.format(
            plan_name=plan.name,
            expires=texts.fmt_date(result["expires_at"]),
            url=result["subscription_url"],
        ),
        reply_markup=keyboards.after_payment(),
        parse_mode="HTML",
    )
