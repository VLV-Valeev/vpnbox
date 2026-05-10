from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.config import PLANS
from app.bot import texts, keyboards

router = Router()


@router.callback_query(F.data == "buy")
async def show_plans(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        texts._build_choose_plan(),
        reply_markup=keyboards.plans_menu(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"))
async def select_plan(callback: CallbackQuery) -> None:
    plan_id = callback.data.split(":", 1)[1]
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    traffic = texts.traffic_text(plan.traffic_gb)
    text = texts.ORDER_SUMMARY.format(
        plan_name=plan.name,
        traffic=traffic,
        price=plan.price,
    )
    await callback.message.edit_text(
        text,
        reply_markup=keyboards.order_confirm(plan_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("choose_pay:"))
async def choose_payment_method(callback: CallbackQuery) -> None:
    plan_id = callback.data.split(":", 1)[1]
    plan = PLANS.get(plan_id)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    await callback.message.edit_text(
        texts.CHOOSE_PAYMENT_METHOD,
        reply_markup=keyboards.payment_provider_menu(plan_id),
        parse_mode="HTML",
    )
    await callback.answer()
