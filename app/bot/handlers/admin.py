"""Админ-панель Telegram-бота.

Команда /admin — полное управление сервисом:
  • Аналитика
  • Выдача тарифа
  • Настройки сервиса (название, поддержка, документы)
  • Управление тарифами (цена, трафик, длительность, вкл/выкл)
  • Настройки VPN-приложения (название, ссылки, платформы)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PLANS
from app.db.models import Payment, PayStatus, SubStatus, Subscription, User
from app.db.repo import UserRepo
from app.services import client_service

router = Router()


# ──────────────── FSM ────────────────


class AdminStates(StatesGroup):
    waiting_user_id = State()          # Выдача тарифа
    waiting_service_name = State()     # Смена названия
    waiting_support_url = State()      # Контакт поддержки
    waiting_terms_url = State()        # Ссылка на соглашение
    waiting_privacy_url = State()      # Ссылка на политику
    waiting_app_name = State()         # Название VPN-приложения
    waiting_app_android = State()      # Ссылка Android
    waiting_app_ios = State()          # Ссылка iOS
    waiting_app_desktop = State()      # Ссылка Desktop
    waiting_plan_price = State()       # Цена тарифа
    waiting_plan_traffic = State()     # Трафик тарифа
    waiting_plan_duration = State()    # Длительность тарифа
    waiting_plan_name = State()        # Название тарифа
    waiting_admin_id = State()         # Выдача/снятие админки
    waiting_referral_days = State()    # Реферальный бонус (дни)


# ──────────────── Helpers ────────────────


def _is_admin(user_id: int) -> bool:
    return client_service.is_admin(user_id)


def _client():
    """Кэшированный Client (только для чтения — кнопки, тексты)."""
    return client_service.get_client()


async def _client_for_edit(session: AsyncSession):
    """Client привязанный к текущей сессии (для записи в БД)."""
    from app.db.models import Client
    from app.config import settings
    result = await session.execute(
        select(Client).where(Client.bot_token == settings.bot_token)
    )
    return result.scalar_one()


def _admin_check(callback: CallbackQuery) -> bool:
    """Проверка прав. Возвращает True если доступ запрещён."""
    if not _is_admin(callback.from_user.id):
        return True
    return False


async def _reload_client(session: AsyncSession) -> None:
    """Перезагрузить клиента из БД и обновить тексты/планы."""
    from app.config import settings
    await client_service.init_client(session, settings.bot_token)


# ──────────────── Главное меню админки ────────────────


def _admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Аналитика", callback_data="adm:analytics")],
        [InlineKeyboardButton(text="🎁 Выдать тариф", callback_data="adm:grant")],
        [InlineKeyboardButton(text="⚙️ Настройки сервиса", callback_data="adm:settings")],
        [InlineKeyboardButton(text="📋 Управление тарифами", callback_data="adm:plans")],
        [InlineKeyboardButton(text="📱 VPN-приложение", callback_data="adm:app")],
        [InlineKeyboardButton(text="👑 Администраторы", callback_data="adm:admins")],
    ])


def _back_kb(to: str = "adm:menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=to)],
    ])


def _cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm:menu")],
    ])


# ──────────────── /admin ────────────────


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    await state.clear()
    sn = _client().service_name
    await message.answer(
        f"🔐 <b>Панель управления {sn}</b>\n\nВыберите действие:",
        reply_markup=_admin_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm:menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    sn = _client().service_name
    await callback.message.edit_text(
        f"🔐 <b>Панель управления {sn}</b>\n\nВыберите действие:",
        reply_markup=_admin_menu_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# ══════════════════════════════════════════
#  АНАЛИТИКА
# ══════════════════════════════════════════


@router.callback_query(F.data == "adm:analytics")
async def admin_analytics(callback: CallbackQuery, session: AsyncSession) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.answer()

    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = today - timedelta(days=today.weekday())
    month = today.replace(day=1)

    u = (await session.execute(
        select(
            sa_func.count(User.id),
            sa_func.count(User.id).filter(User.created_at >= today),
            sa_func.count(User.id).filter(User.created_at >= week),
            sa_func.count(User.id).filter(User.created_at >= month),
        )
    )).one()
    total_users, users_today, users_week, users_month = u

    s = (await session.execute(
        select(
            sa_func.count(Subscription.id).filter(
                Subscription.status.in_([SubStatus.TRIAL, SubStatus.ACTIVE])
            ),
            sa_func.count(Subscription.id).filter(Subscription.status == SubStatus.TRIAL),
            sa_func.count(Subscription.id).filter(Subscription.status == SubStatus.ACTIVE),
            sa_func.count(Subscription.id).filter(Subscription.status == SubStatus.EXPIRED),
        )
    )).one()
    active_subs, trial_subs, paid_subs, expired_subs = s

    base_revenue = (Payment.status == PayStatus.SUCCEEDED) & (Payment.currency == "RUB")
    p = (await session.execute(
        select(
            sa_func.count(Payment.id).filter(Payment.status == PayStatus.SUCCEEDED),
            sa_func.count(Payment.id).filter(Payment.status == PayStatus.PENDING),
            sa_func.coalesce(sa_func.sum(Payment.amount).filter(base_revenue), 0),
            sa_func.coalesce(sa_func.sum(Payment.amount).filter(base_revenue & (Payment.paid_at >= today)), 0),
            sa_func.coalesce(sa_func.sum(Payment.amount).filter(base_revenue & (Payment.paid_at >= week)), 0),
            sa_func.coalesce(sa_func.sum(Payment.amount).filter(base_revenue & (Payment.paid_at >= month)), 0),
        )
    )).one()
    succeeded, pending, revenue_all, revenue_today, revenue_week, revenue_month = p

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="adm:analytics")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu")],
    ])

    text = (
        "📊 <b>Аналитика</b>\n\n"
        "👥 <b>Пользователи</b>\n"
        f"  Всего: <b>{total_users}</b>\n"
        f"  Сегодня: <b>+{users_today}</b>\n"
        f"  За неделю: <b>+{users_week}</b>\n"
        f"  За месяц: <b>+{users_month}</b>\n\n"
        "📋 <b>Подписки</b>\n"
        f"  Активных: <b>{active_subs}</b>  "
        f"(триал: {trial_subs} / платных: {paid_subs})\n"
        f"  Истёкших: <b>{expired_subs}</b>\n\n"
        "💳 <b>Платежи</b>\n"
        f"  Успешных: <b>{succeeded}</b>\n"
        f"  Ожидают: <b>{pending}</b>\n\n"
        "💰 <b>Выручка (RUB)</b>\n"
        f"  Сегодня: <b>{revenue_today} ₽</b>\n"
        f"  За неделю: <b>{revenue_week} ₽</b>\n"
        f"  За месяц: <b>{revenue_month} ₽</b>\n"
        f"  За всё время: <b>{revenue_all} ₽</b>"
    )

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ══════════════════════════════════════════
#  ВЫДАТЬ ТАРИФ
# ══════════════════════════════════════════


@router.callback_query(F.data == "adm:grant")
async def admin_grant_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_user_id)
    await callback.message.edit_text(
        "🎁 <b>Выдать тариф</b>\n\n"
        "Введите Telegram ID пользователя\n"
        "<i>(числовой ID, например: 123456789)</i>:",
        reply_markup=_cancel_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_user_id)
async def admin_grant_receive_id(
    message: Message, session: AsyncSession, state: FSMContext,
) -> None:
    if not _is_admin(message.from_user.id):
        return

    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer(
            "❌ Telegram ID — это число. Попробуйте ещё раз:",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
        return

    telegram_id = int(text)
    user = await UserRepo(session).get_by_tg(telegram_id)
    if not user:
        await message.answer(
            f"❌ Пользователь <code>{telegram_id}</code> не найден в боте.\n\nВведите другой ID:",
            reply_markup=_cancel_kb(), parse_mode="HTML",
        )
        return

    await state.clear()
    buttons = []
    for slug, plan in PLANS.items():
        traffic = "безлимит" if plan.traffic_gb == 0 else f"{plan.traffic_gb} ГБ"
        label = f"{plan.name} — {plan.duration_days} дн., {traffic}"
        if plan.price > 0:
            label += f" ({plan.price} ₽)"
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f"adm:grant:{telegram_id}:{slug}",
        )])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="adm:menu")])

    uname = f" (@{user.username})" if user.username else ""
    await message.answer(
        f"👤 <b>{user.full_name}</b>{uname}\n"
        f"ID: <code>{telegram_id}</code>\n\nВыберите тариф для выдачи:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm:grant:"))
async def admin_grant_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("❌ Неверный формат", show_alert=True)
        return

    telegram_id = int(parts[2])
    plan_slug = parts[3]

    await callback.answer("⏳ Выдаю тариф...")

    from app.services.subscription_service import grant_plan
    from app.bot.texts import fmt_date

    result = await grant_plan(session, telegram_id, plan_slug)

    if not result["ok"]:
        err_map = {
            "user_not_found": "Пользователь не найден.",
            "unknown_plan": "Тариф не найден.",
            "no_servers": "Нет доступных VPN-серверов.",
        }
        err = err_map.get(result.get("error", ""), "Неизвестная ошибка.")
        await callback.message.edit_text(
            f"❌ <b>Ошибка выдачи тарифа</b>\n\n{err}",
            reply_markup=_back_kb(), parse_mode="HTML",
        )
        return

    plan = PLANS.get(plan_slug)
    plan_name = plan.name if plan else plan_slug
    expires_str = fmt_date(result["expires_at"])
    action = result.get("action", "created")
    action_label = "продлена" if action == "extended" else "выдана"

    await callback.message.edit_text(
        f"✅ <b>Подписка {action_label}!</b>\n\n"
        f"👤 Пользователь: <code>{telegram_id}</code>\n"
        f"📦 Тариф: <b>{plan_name}</b>\n"
        f"📅 Действует до: <b>{expires_str}</b>\n\n"
        f"🔗 Ссылка:\n<code>{result['subscription_url']}</code>",
        reply_markup=_back_kb(), parse_mode="HTML",
    )


# ══════════════════════════════════════════
#  НАСТРОЙКИ СЕРВИСА
# ══════════════════════════════════════════


def _settings_kb() -> InlineKeyboardMarkup:
    c = _client()
    support = c.support_url or "не задан"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📝 Название: {c.service_name}", callback_data="adm:set:name")],
        [InlineKeyboardButton(text=f"🆘 Поддержка: {support}", callback_data="adm:set:support")],
        [InlineKeyboardButton(text="📄 Пользовательское соглашение", callback_data="adm:set:terms")],
        [InlineKeyboardButton(text="🔒 Политика конфиденциальности", callback_data="adm:set:privacy")],
        [InlineKeyboardButton(
            text=f"🎁 Реферальный бонус: {c.referral_reward_days} дн.",
            callback_data="adm:set:refdays",
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu")],
    ])


@router.callback_query(F.data == "adm:settings")
async def admin_settings(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "⚙️ <b>Настройки сервиса</b>\n\nВыберите параметр для изменения:",
        reply_markup=_settings_kb(), parse_mode="HTML",
    )
    await callback.answer()


# ── Название сервиса ──

@router.callback_query(F.data == "adm:set:name")
async def set_name_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_service_name)
    await callback.message.edit_text(
        f"📝 <b>Название сервиса</b>\n\n"
        f"Текущее: <b>{_client().service_name}</b>\n\n"
        f"Введите новое название:",
        reply_markup=_back_kb("adm:settings"), parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_service_name)
async def set_name_done(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    new_name = (message.text or "").strip()
    if not new_name or len(new_name) > 100:
        await message.answer("❌ Название должно быть от 1 до 100 символов.", reply_markup=_back_kb("adm:settings"))
        return

    c = await _client_for_edit(session)
    c.service_name = new_name
    await session.commit()
    await _reload_client(session)
    await state.clear()
    await message.answer(
        f"✅ Название изменено на <b>{new_name}</b>",
        reply_markup=_back_kb("adm:settings"), parse_mode="HTML",
    )


# ── Контакт поддержки ──

@router.callback_query(F.data == "adm:set:support")
async def set_support_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_support_url)
    current = _client().support_url or "не задан"
    await callback.message.edit_text(
        f"🆘 <b>Контакт поддержки</b>\n\n"
        f"Текущий: <b>{current}</b>\n\n"
        f"Введите @username или URL:",
        reply_markup=_back_kb("adm:settings"), parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_support_url)
async def set_support_done(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    c = await _client_for_edit(session)
    c.support_url = value
    await session.commit()
    await _reload_client(session)
    await state.clear()
    await message.answer(
        f"✅ Контакт поддержки: <b>{value or 'очищен'}</b>",
        reply_markup=_back_kb("adm:settings"), parse_mode="HTML",
    )


# ── Пользовательское соглашение ──

@router.callback_query(F.data == "adm:set:terms")
async def set_terms_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_terms_url)
    await callback.message.edit_text(
        f"📄 <b>Пользовательское соглашение</b>\n\n"
        f"Текущая ссылка:\n{_client().terms_url}\n\n"
        f"Введите новый URL:",
        reply_markup=_back_kb("adm:settings"), parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_terms_url)
async def set_terms_done(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    if not value.startswith("http"):
        await message.answer("❌ Ссылка должна начинаться с http:// или https://", reply_markup=_back_kb("adm:settings"))
        return
    c = await _client_for_edit(session)
    c.terms_url = value
    await session.commit()
    await _reload_client(session)
    await state.clear()
    await message.answer("✅ Ссылка на соглашение обновлена.", reply_markup=_back_kb("adm:settings"), parse_mode="HTML")


# ── Политика конфиденциальности ──

@router.callback_query(F.data == "adm:set:privacy")
async def set_privacy_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_privacy_url)
    await callback.message.edit_text(
        f"🔒 <b>Политика конфиденциальности</b>\n\n"
        f"Текущая ссылка:\n{_client().privacy_url}\n\n"
        f"Введите новый URL:",
        reply_markup=_back_kb("adm:settings"), parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_privacy_url)
async def set_privacy_done(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    if not value.startswith("http"):
        await message.answer("❌ Ссылка должна начинаться с http:// или https://", reply_markup=_back_kb("adm:settings"))
        return
    c = await _client_for_edit(session)
    c.privacy_url = value
    await session.commit()
    await _reload_client(session)
    await state.clear()
    await message.answer("✅ Ссылка на политику обновлена.", reply_markup=_back_kb("adm:settings"), parse_mode="HTML")


# ── Реферальный бонус ──

@router.callback_query(F.data == "adm:set:refdays")
async def set_refdays_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_referral_days)
    await callback.message.edit_text(
        f"🎁 <b>Реферальный бонус</b>\n\n"
        f"Текущее значение: <b>{_client().referral_reward_days} дн.</b>\n\n"
        f"Введите количество дней бонуса за каждого реферала, оформившего платную подписку\n"
        f"<i>(от 1 до 365)</i>:",
        reply_markup=_back_kb("adm:settings"), parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_referral_days)
async def set_refdays_done(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    if not value.isdigit() or not 1 <= int(value) <= 365:
        await message.answer(
            "❌ Введите целое число от 1 до 365.",
            reply_markup=_back_kb("adm:settings"),
        )
        return
    days = int(value)
    c = await _client_for_edit(session)
    c.referral_reward_days = days
    await session.commit()
    await _reload_client(session)
    await state.clear()
    await message.answer(
        f"✅ Реферальный бонус изменён: <b>{days} дн.</b>",
        reply_markup=_back_kb("adm:settings"), parse_mode="HTML",
    )


# ══════════════════════════════════════════
#  УПРАВЛЕНИЕ ТАРИФАМИ
# ══════════════════════════════════════════


def _plans_list_kb() -> InlineKeyboardMarkup:
    buttons = []
    for plan_db in _client().plans:
        status = "✅" if plan_db.is_active else "❌"
        traffic = "∞" if plan_db.traffic_gb == 0 else f"{plan_db.traffic_gb}ГБ"
        label = f"{status} {plan_db.name} — {plan_db.price}₽ / {plan_db.duration_days}д / {traffic}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"adm:plan:{plan_db.id}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "adm:plans")
async def admin_plans_list(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "📋 <b>Управление тарифами</b>\n\n"
        "✅ — активен, ❌ — выключен\n"
        "Нажмите на тариф для редактирования:",
        reply_markup=_plans_list_kb(), parse_mode="HTML",
    )
    await callback.answer()


def _plan_detail_kb(plan_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ Выключить" if is_active else "✅ Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Название", callback_data=f"adm:planedit:{plan_id}:name")],
        [InlineKeyboardButton(text="💰 Цена", callback_data=f"adm:planedit:{plan_id}:price")],
        [InlineKeyboardButton(text="📊 Трафик", callback_data=f"adm:planedit:{plan_id}:traffic")],
        [InlineKeyboardButton(text="📅 Длительность (дни)", callback_data=f"adm:planedit:{plan_id}:duration")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"adm:plantoggle:{plan_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:plans")],
    ])


def _find_plan_db(plan_id: int):
    """Найти план в кэше (только для чтения)."""
    for p in _client().plans:
        if p.id == plan_id:
            return p
    return None


async def _find_plan_for_edit(session: AsyncSession, plan_id: int):
    """Найти план в текущей сессии (для записи)."""
    from app.db.models import ClientPlan
    return await session.get(ClientPlan, plan_id)


@router.callback_query(F.data.regexp(r"^adm:plan:\d+$"))
async def admin_plan_detail(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    plan_id = int(callback.data.split(":")[2])
    plan = _find_plan_db(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return

    traffic = "Безлимит" if plan.traffic_gb == 0 else f"{plan.traffic_gb} ГБ"
    status = "Активен ✅" if plan.is_active else "Выключен ❌"

    await callback.message.edit_text(
        f"📦 <b>Тариф: {plan.name}</b>\n\n"
        f"• Slug: <code>{plan.slug}</code>\n"
        f"• Цена: <b>{plan.price} ₽</b>\n"
        f"• Трафик: <b>{traffic}</b>\n"
        f"• Длительность: <b>{plan.duration_days} дн.</b>\n"
        f"• Описание: {plan.description}\n"
        f"• Статус: <b>{status}</b>",
        reply_markup=_plan_detail_kb(plan_id, plan.is_active),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Вкл/выкл тарифа ──

@router.callback_query(F.data.regexp(r"^adm:plantoggle:\d+$"))
async def admin_plan_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    plan_id = int(callback.data.split(":")[2])
    plan = await _find_plan_for_edit(session, plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return

    plan.is_active = not plan.is_active
    await session.commit()
    await _reload_client(session)

    status = "включён ✅" if plan.is_active else "выключен ❌"
    await callback.answer(f"Тариф {plan.name} {status}", show_alert=True)

    # Обновить карточку (из обновлённого кэша)
    plan = _find_plan_db(plan_id)
    traffic = "Безлимит" if plan.traffic_gb == 0 else f"{plan.traffic_gb} ГБ"
    status_text = "Активен ✅" if plan.is_active else "Выключен ❌"

    await callback.message.edit_text(
        f"📦 <b>Тариф: {plan.name}</b>\n\n"
        f"• Slug: <code>{plan.slug}</code>\n"
        f"• Цена: <b>{plan.price} ₽</b>\n"
        f"• Трафик: <b>{traffic}</b>\n"
        f"• Длительность: <b>{plan.duration_days} дн.</b>\n"
        f"• Описание: {plan.description}\n"
        f"• Статус: <b>{status_text}</b>",
        reply_markup=_plan_detail_kb(plan_id, plan.is_active),
        parse_mode="HTML",
    )


# ── Редактирование полей тарифа ──

@router.callback_query(F.data.regexp(r"^adm:planedit:\d+:(name|price|traffic|duration)$"))
async def admin_plan_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    plan_id = int(parts[2])
    field = parts[3]
    plan = _find_plan_db(plan_id)
    if not plan:
        await callback.answer("❌ Тариф не найден", show_alert=True)
        return

    field_map = {
        "name": ("📝 Название", plan.name, AdminStates.waiting_plan_name),
        "price": ("💰 Цена (₽)", str(plan.price), AdminStates.waiting_plan_price),
        "traffic": ("📊 Трафик (ГБ, 0 = безлимит)", str(plan.traffic_gb), AdminStates.waiting_plan_traffic),
        "duration": ("📅 Длительность (дни)", str(plan.duration_days), AdminStates.waiting_plan_duration),
    }

    label, current, fsm_state = field_map[field]
    await state.set_state(fsm_state)
    await state.update_data(plan_id=plan_id)

    await callback.message.edit_text(
        f"✏️ <b>{label}</b>\n\n"
        f"Тариф: <b>{plan.name}</b>\n"
        f"Текущее значение: <b>{current}</b>\n\n"
        f"Введите новое значение:",
        reply_markup=_back_kb(f"adm:plan:{plan_id}"), parse_mode="HTML",
    )
    await callback.answer()


async def _save_plan_field(
    message: Message, session: AsyncSession, state: FSMContext,
    field: str, parse_int: bool = False,
) -> None:
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    plan_id = data.get("plan_id")
    plan = await _find_plan_for_edit(session, plan_id)
    if not plan:
        await message.answer("❌ Тариф не найден.", reply_markup=_back_kb("adm:plans"))
        await state.clear()
        return

    value = (message.text or "").strip()

    if parse_int:
        if not value.isdigit():
            await message.answer("❌ Введите число.", reply_markup=_back_kb(f"adm:plan:{plan_id}"))
            return
        setattr(plan, field, int(value))
    else:
        if not value or len(value) > 100:
            await message.answer("❌ Значение от 1 до 100 символов.", reply_markup=_back_kb(f"adm:plan:{plan_id}"))
            return
        setattr(plan, field, value)

    # Обновить description автоматически
    traffic_txt = "Безлимит" if plan.traffic_gb == 0 else f"{plan.traffic_gb} ГБ"
    plan.description = f"{plan.duration_days} дн. • {traffic_txt}"

    await session.commit()
    await _reload_client(session)
    await state.clear()
    await message.answer(
        f"✅ Тариф <b>{plan.name}</b> обновлён.",
        reply_markup=_back_kb(f"adm:plan:{plan_id}"), parse_mode="HTML",
    )


@router.message(AdminStates.waiting_plan_name)
async def plan_edit_name(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _save_plan_field(message, session, state, "name")


@router.message(AdminStates.waiting_plan_price)
async def plan_edit_price(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _save_plan_field(message, session, state, "price", parse_int=True)


@router.message(AdminStates.waiting_plan_traffic)
async def plan_edit_traffic(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _save_plan_field(message, session, state, "traffic_gb", parse_int=True)


@router.message(AdminStates.waiting_plan_duration)
async def plan_edit_duration(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _save_plan_field(message, session, state, "duration_days", parse_int=True)


# ══════════════════════════════════════════
#  VPN-ПРИЛОЖЕНИЕ
# ══════════════════════════════════════════


def _app_settings_kb() -> InlineKeyboardMarkup:
    c = _client()
    android_icon = "✅" if c.vpn_app_show_android else "❌"
    ios_icon = "✅" if c.vpn_app_show_ios else "❌"
    desktop_icon = "✅" if c.vpn_app_show_desktop else "❌"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📱 Приложение: {c.vpn_app_name}", callback_data="adm:appset:name")],
        [
            InlineKeyboardButton(text=f"{android_icon} Android", callback_data="adm:apptoggle:android"),
            InlineKeyboardButton(text=f"{ios_icon} iOS", callback_data="adm:apptoggle:ios"),
            InlineKeyboardButton(text=f"{desktop_icon} Desktop", callback_data="adm:apptoggle:desktop"),
        ],
        [InlineKeyboardButton(text="🔗 Ссылка Android", callback_data="adm:appurl:android")],
        [InlineKeyboardButton(text="🔗 Ссылка iOS", callback_data="adm:appurl:ios")],
        [InlineKeyboardButton(text="🔗 Ссылка Desktop", callback_data="adm:appurl:desktop")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu")],
    ])


def _app_status_text() -> str:
    c = _client()
    android = f"✅ {c.vpn_app_android_url}" if c.vpn_app_show_android else "❌ скрыт"
    ios = f"✅ {c.vpn_app_ios_url}" if c.vpn_app_show_ios else "❌ скрыт"
    desktop = f"✅ {c.vpn_app_desktop_url}" if c.vpn_app_show_desktop else "❌ скрыт"
    return (
        f"📱 <b>VPN-приложение</b>\n\n"
        f"Название: <b>{c.vpn_app_name}</b>\n\n"
        f"<b>Android:</b> {android}\n"
        f"<b>iOS:</b> {ios}\n"
        f"<b>Desktop:</b> {desktop}"
    )


@router.callback_query(F.data == "adm:app")
async def admin_app_settings(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        _app_status_text(),
        reply_markup=_app_settings_kb(), parse_mode="HTML",
    )
    await callback.answer()


# ── Переключение платформ ──

@router.callback_query(F.data.regexp(r"^adm:apptoggle:(android|ios|desktop)$"))
async def admin_app_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    platform = callback.data.split(":")[2]
    c = await _client_for_edit(session)

    field_map = {
        "android": "vpn_app_show_android",
        "ios": "vpn_app_show_ios",
        "desktop": "vpn_app_show_desktop",
    }
    field = field_map[platform]
    new_value = not getattr(c, field)
    setattr(c, field, new_value)
    await session.commit()
    await _reload_client(session)

    status = "включён ✅" if new_value else "выключен ❌"
    await callback.answer(f"{platform.capitalize()} {status}")

    await callback.message.edit_text(
        _app_status_text(),
        reply_markup=_app_settings_kb(), parse_mode="HTML",
    )


# ── Название приложения ──

@router.callback_query(F.data == "adm:appset:name")
async def set_app_name_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_app_name)
    await callback.message.edit_text(
        f"📱 <b>Название VPN-приложения</b>\n\n"
        f"Текущее: <b>{_client().vpn_app_name}</b>\n\n"
        f"Введите новое название (Hiddify, V2rayTun, Happ и т.д.):",
        reply_markup=_back_kb("adm:app"), parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_app_name)
async def set_app_name_done(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    if not value or len(value) > 100:
        await message.answer("❌ Название от 1 до 100 символов.", reply_markup=_back_kb("adm:app"))
        return
    c = await _client_for_edit(session)
    c.vpn_app_name = value
    await session.commit()
    await _reload_client(session)
    await state.clear()
    await message.answer(
        f"✅ Приложение: <b>{value}</b>",
        reply_markup=_back_kb("adm:app"), parse_mode="HTML",
    )


# ── Ссылки на скачивание ──

@router.callback_query(F.data.regexp(r"^adm:appurl:(android|ios|desktop)$"))
async def set_app_url_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    platform = callback.data.split(":")[2]
    c = _client()

    url_map = {
        "android": ("Android", c.vpn_app_android_url, AdminStates.waiting_app_android),
        "ios": ("iOS", c.vpn_app_ios_url, AdminStates.waiting_app_ios),
        "desktop": ("Desktop", c.vpn_app_desktop_url, AdminStates.waiting_app_desktop),
    }
    label, current, fsm_state = url_map[platform]
    await state.set_state(fsm_state)

    await callback.message.edit_text(
        f"🔗 <b>Ссылка {label}</b>\n\n"
        f"Текущая:\n{current}\n\n"
        f"Введите новый URL:",
        reply_markup=_back_kb("adm:app"), parse_mode="HTML",
    )
    await callback.answer()


async def _save_app_url(
    message: Message, session: AsyncSession, state: FSMContext, field: str,
) -> None:
    if not _is_admin(message.from_user.id):
        return
    value = (message.text or "").strip()
    if not value.startswith("http"):
        await message.answer("❌ Ссылка должна начинаться с http:// или https://", reply_markup=_back_kb("adm:app"))
        return
    c = await _client_for_edit(session)
    setattr(c, field, value)
    await session.commit()
    await _reload_client(session)
    await state.clear()
    await message.answer("✅ Ссылка обновлена.", reply_markup=_back_kb("adm:app"), parse_mode="HTML")


@router.message(AdminStates.waiting_app_android)
async def set_app_android(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _save_app_url(message, session, state, "vpn_app_android_url")


@router.message(AdminStates.waiting_app_ios)
async def set_app_ios(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _save_app_url(message, session, state, "vpn_app_ios_url")


@router.message(AdminStates.waiting_app_desktop)
async def set_app_desktop(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _save_app_url(message, session, state, "vpn_app_desktop_url")


# ══════════════════════════════════════════
#  АДМИНИСТРАТОРЫ
# ══════════════════════════════════════════


async def _admins_list_kb(session: AsyncSession) -> InlineKeyboardMarkup:
    result = await session.execute(
        select(User).where(User.role == "admin")
    )
    admins = list(result.scalars().all())

    buttons = []
    for u in admins:
        uname = f" @{u.username}" if u.username else ""
        buttons.append([InlineKeyboardButton(
            text=f"👑 {u.full_name}{uname} ({u.telegram_id})",
            callback_data=f"adm:admininfo:{u.telegram_id}",
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить админа", callback_data="adm:adminadd")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "adm:admins")
async def admin_admins_list(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "👑 <b>Администраторы</b>\n\n"
        "Список пользователей с правами администратора:",
        reply_markup=await _admins_list_kb(session), parse_mode="HTML",
    )
    await callback.answer()


# ── Инфо об админе (с кнопкой снятия) ──

@router.callback_query(F.data.regexp(r"^adm:admininfo:\d+$"))
async def admin_admin_info(callback: CallbackQuery, session: AsyncSession) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tg_id = int(callback.data.split(":")[2])
    user = await UserRepo(session).get_by_tg(tg_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    uname = f" (@{user.username})" if user.username else ""
    is_self = callback.from_user.id == tg_id

    buttons = []
    if not is_self:
        buttons.append([InlineKeyboardButton(
            text="🚫 Снять права админа",
            callback_data=f"adm:adminrevoke:{tg_id}",
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="⚠️ Это вы (снять нельзя)", callback_data="adm:noop",
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:admins")])

    await callback.message.edit_text(
        f"👑 <b>Администратор</b>\n\n"
        f"👤 {user.full_name}{uname}\n"
        f"ID: <code>{tg_id}</code>\n"
        f"Роль: <b>{user.role}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:noop")
async def admin_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ── Снятие админки ──

@router.callback_query(F.data.regexp(r"^adm:adminrevoke:\d+$"))
async def admin_revoke(callback: CallbackQuery, session: AsyncSession) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    tg_id = int(callback.data.split(":")[2])

    if tg_id == callback.from_user.id:
        await callback.answer("❌ Нельзя снять админку с себя", show_alert=True)
        return

    user = await UserRepo(session).get_by_tg(tg_id)
    if not user or user.role != "admin":
        await callback.answer("❌ Пользователь не является админом", show_alert=True)
        return

    user.role = "user"
    await session.commit()
    client_service.remove_admin(tg_id)

    await callback.answer(f"Права админа сняты с {user.full_name}", show_alert=True)
    await callback.message.edit_text(
        "👑 <b>Администраторы</b>\n\n"
        "Список пользователей с правами администратора:",
        reply_markup=await _admins_list_kb(session), parse_mode="HTML",
    )


# ── Добавление админа ──

@router.callback_query(F.data == "adm:adminadd")
async def admin_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if _admin_check(callback):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_admin_id)
    await callback.message.edit_text(
        "➕ <b>Добавить администратора</b>\n\n"
        "Введите Telegram ID пользователя\n"
        "<i>(он должен уже написать боту /start)</i>:",
        reply_markup=_back_kb("adm:admins"), parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_admin_id)
async def admin_add_done(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return

    text = (message.text or "").strip()
    if not text.lstrip("-").isdigit():
        await message.answer(
            "❌ Telegram ID — это число. Попробуйте ещё раз:",
            reply_markup=_back_kb("adm:admins"), parse_mode="HTML",
        )
        return

    tg_id = int(text)
    user = await UserRepo(session).get_by_tg(tg_id)

    if not user:
        await message.answer(
            f"❌ Пользователь <code>{tg_id}</code> не найден.\n"
            f"Он должен сначала написать боту /start.",
            reply_markup=_back_kb("adm:admins"), parse_mode="HTML",
        )
        return

    if user.role == "admin":
        await message.answer(
            f"ℹ️ <b>{user.full_name}</b> уже является администратором.",
            reply_markup=_back_kb("adm:admins"), parse_mode="HTML",
        )
        await state.clear()
        return

    user.role = "admin"
    await session.commit()
    client_service.add_admin(tg_id)
    await state.clear()

    uname = f" (@{user.username})" if user.username else ""
    await message.answer(
        f"✅ <b>{user.full_name}</b>{uname} назначен администратором.",
        reply_markup=_back_kb("adm:admins"), parse_mode="HTML",
    )
