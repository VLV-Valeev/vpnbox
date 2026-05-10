from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts, keyboards
from app.services.subscription_service import activate_trial

router = Router()


@router.callback_query(F.data == "trial")
async def on_trial(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await activate_trial(session, callback.from_user.id)

    if not result["ok"]:
        error = result["error"]
        if error == "trial_already_used":
            text = texts.TRIAL_ALREADY_USED
        elif error == "has_active_sub":
            text = texts.HAS_ACTIVE_SUB
        elif error == "no_servers":
            text = texts.NO_SERVERS
        elif error == "trial_disabled":
            text = "❌ Пробный период временно недоступен."
        else:
            text = "❌ Ошибка. Попробуйте позже."

        await callback.message.edit_text(
            text,
            reply_markup=keyboards.main_menu(trial_available=False),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    text = texts.TRIAL_ACTIVATED.format(
        expires=texts.fmt_date(result["expires_at"]),
        url=result["subscription_url"],
    )
    await callback.message.edit_text(
        text,
        reply_markup=keyboards.after_payment(),
        parse_mode="HTML",
    )
    await callback.answer("✅ Пробный период активирован!")
