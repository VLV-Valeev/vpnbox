import asyncio

from aiogram import Router, F
from aiogram.types import CallbackQuery, LinkPreviewOptions
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PLANS
from app.bot import texts, keyboards
from app.services.subscription_service import create_payment_for_plan, check_and_activate

router = Router()

# Активные polling-задачи: payment_id → asyncio.Task
_polling_tasks: dict[int, asyncio.Task] = {}

POLL_INTERVAL = 3        # секунд между проверками
POLL_MAX_DURATION = 900   # 15 минут максимум


@router.callback_query(F.data.startswith("pay:"))
async def create_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = callback.data.split(":")
    # Формат: pay:{plan_id}:{provider}
    if len(parts) != 3:
        await callback.answer("Ошибка формата", show_alert=True)
        return

    _, plan_id, provider = parts
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    result = await create_payment_for_plan(
        session, callback.from_user.id, plan_id, provider=provider,
    )

    if not result["ok"]:
        await callback.message.edit_text(
            texts.PAYMENT_ERROR,
            reply_markup=keyboards.main_menu(trial_available=False),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    payment_id = result["payment_id"]
    text = texts.PAY_LINK.format(url=result["confirmation_url"], price=plan.price)
    await callback.message.edit_text(
        text,
        reply_markup=keyboards.check_payment(payment_id),
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    await callback.answer()

    # Запускаем фоновый polling для этого платежа
    _start_polling(payment_id, callback)


@router.callback_query(F.data.startswith("check:"))
async def check_payment_status(callback: CallbackQuery, session: AsyncSession) -> None:
    payment_id = int(callback.data.split(":", 1)[1])

    result = await check_and_activate(session, payment_id)

    if result["status"] == "succeeded":
        _stop_polling(payment_id)
        if "subscription_url" in result:
            text = texts.PAYMENT_SUCCESS.format(
                plan_name="VPN",
                expires=texts.fmt_date(result["expires_at"]),
                url=result["subscription_url"],
            )
        else:
            text = "Оплата подтверждена! Подписка активирована."

        await callback.message.edit_text(
            text,
            reply_markup=keyboards.after_payment(),
            parse_mode="HTML",
        )
        await callback.answer("Оплата подтверждена!")
        return

    if result["status"] == "cancelled":
        _stop_polling(payment_id)
        await callback.message.edit_text(
            texts.PAYMENT_CANCELLED,
            reply_markup=keyboards.main_menu(trial_available=False),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.answer(
        "Оплата ещё не поступила. Подождите и попробуйте ещё раз.",
        show_alert=True,
    )


# ──────────────── Polling ────────────────


def _start_polling(payment_id: int, callback: CallbackQuery) -> None:
    """Запустить asyncio-таску для polling-а статуса платежа."""
    if payment_id in _polling_tasks:
        return
    task = asyncio.create_task(_poll_payment(payment_id, callback))
    _polling_tasks[payment_id] = task


def _stop_polling(payment_id: int) -> None:
    """Остановить polling для платежа."""
    task = _polling_tasks.pop(payment_id, None)
    if task and not task.done():
        task.cancel()


async def _poll_payment(payment_id: int, callback: CallbackQuery) -> None:
    """Проверять статус платежа каждые POLL_INTERVAL сек."""
    from app.db.engine import async_session

    elapsed = 0
    try:
        while elapsed < POLL_MAX_DURATION:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

            try:
                async with async_session() as session:
                    result = await check_and_activate(session, payment_id)
            except Exception:
                continue

            if result["status"] == "succeeded":
                if "subscription_url" in result:
                    text = texts.PAYMENT_SUCCESS.format(
                        plan_name="VPN",
                        expires=texts.fmt_date(result["expires_at"]),
                        url=result["subscription_url"],
                    )
                else:
                    text = "Оплата подтверждена! Подписка активирована."

                try:
                    await callback.message.edit_text(
                        text,
                        reply_markup=keyboards.after_payment(),
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
                break

            if result["status"] in ("cancelled", "failed"):
                try:
                    await callback.message.edit_text(
                        texts.PAYMENT_CANCELLED,
                        reply_markup=keyboards.main_menu(trial_available=False),
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
                break
    except asyncio.CancelledError:
        pass
    finally:
        _polling_tasks.pop(payment_id, None)
