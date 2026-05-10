from aiogram import Router, F
from aiogram.types import CallbackQuery, LinkPreviewOptions
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts, keyboards
from app.config import settings
from app.db.repo import UserRepo, ReferralRepo

router = Router()


@router.callback_query(F.data == "referral")
async def referral_info(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserRepo(session).get_by_tg(callback.from_user.id)
    if not user:
        await callback.answer()
        return

    ref_link = f"https://t.me/{settings.bot_username}?start=ref_{callback.from_user.id}"

    await callback.message.edit_text(
        texts.REFERRAL_INFO.format(ref_link=ref_link),
        reply_markup=keyboards.referral_menu(callback.from_user.id),
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    await callback.answer()


@router.callback_query(F.data == "referral:stats")
async def referral_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserRepo(session).get_by_tg(callback.from_user.id)
    if not user:
        await callback.answer()
        return

    total, paid = await ReferralRepo(session).get_stats(user.id)

    await callback.message.edit_text(
        texts.REFERRAL_STATS.format(total=total, paid=paid),
        reply_markup=keyboards.referral_stats_back(),
        parse_mode="HTML",
    )
    await callback.answer()
