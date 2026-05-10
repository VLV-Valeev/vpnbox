from aiogram import Router, F
from aiogram.types import CallbackQuery, LinkPreviewOptions
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PLANS
from app.db.repo import UserRepo, SubRepo
from app.services import vpn_service
from app.services.client_service import get_client
from app.bot import texts, keyboards

router = Router()


def _support_url() -> str:
    try:
        return get_client().support_url or ""
    except RuntimeError:
        return ""


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserRepo(session).get_by_tg(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    sub = await SubRepo(session).get_active(user.id)
    if not sub:
        await callback.message.edit_text(
            texts.PROFILE_NO_SUB,
            reply_markup=keyboards.profile_menu(has_sub=False, support_url=_support_url()),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    plan = PLANS.get(sub.plan_id)
    plan_name = plan.name if plan else sub.plan_id

    # Пытаемся получить реальный трафик с сервера
    traffic_str = texts.traffic_text(sub.traffic_limit_gb)
    vpn_user = await vpn_service.get_vpn_user(sub.vpn_username, sub.server_id)
    if vpn_user:
        used = f"{vpn_user.traffic_used_gb:.1f}"
        if sub.traffic_limit_gb > 0:
            traffic_str = f"{used} / {sub.traffic_limit_gb} ГБ"
        else:
            traffic_str = f"{used} ГБ (Безлимит)"

    text = texts.PROFILE_ACTIVE.format(
        plan_name=plan_name,
        expires=texts.fmt_date(sub.expires_at),
        traffic=traffic_str,
        url=sub.subscription_url,
    )
    await callback.message.edit_text(
        text,
        reply_markup=keyboards.profile_menu(has_sub=True, support_url=_support_url()),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "connect")
async def show_connect(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserRepo(session).get_by_tg(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    sub = await SubRepo(session).get_active(user.id)
    if not sub:
        await callback.message.edit_text(
            texts.CONNECT_NO_SUB,
            reply_markup=keyboards.main_menu(trial_available=not user.trial_used),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    text = texts.CONNECT_GUIDE.format(url=sub.subscription_url)
    await callback.message.edit_text(
        text,
        reply_markup=keyboards.connect_menu(vless_url=sub.subscription_url),
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    await callback.answer()
