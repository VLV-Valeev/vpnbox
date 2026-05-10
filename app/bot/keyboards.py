"""Inline-клавиатуры бота."""
from __future__ import annotations


from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import PLANS
from app.services.payments.factory import get_enabled_providers


# ──────────────── Главное меню ────────────────


def main_menu(trial_available: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    if trial_available:
        buttons.append(
            [InlineKeyboardButton(text="🎁 Попробовать бесплатно", callback_data="trial")],
        )
    buttons.extend([
        [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="📱 Подключение", callback_data="connect")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ──────────────── Реферальная программа ────────────────


def referral_menu(telegram_id: int) -> InlineKeyboardMarkup:
    from app.config import settings
    ref_link = f"https://t.me/{settings.bot_username}?start=ref_{telegram_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Статистика рефералов",
            callback_data="referral:stats",
        )],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back:main")],
    ])


def referral_stats_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="referral")],
    ])


# ──────────────── Выбор тарифа ────────────────


def plans_menu() -> InlineKeyboardMarkup:
    from app.bot.texts import traffic_text
    buttons = []
    for slug, plan in PLANS.items():
        if plan.price == 0:
            continue  # пропускаем бесплатные (trial)
        traffic = traffic_text(plan.traffic_gb)
        label = f"{plan.name} — {plan.price} ₽ ({traffic})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"plan:{slug}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ──────────────── Подтверждение заказа ────────────────


def order_confirm(plan_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"choose_pay:{plan_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="buy")],
    ])


# ──────────────── Выбор платёжной системы ────────────────


def payment_provider_menu(plan_id: str) -> InlineKeyboardMarkup:
    try:
        from app.services.client_service import get_client
        client = get_client()
        providers = {
            p.provider: p.label
            for p in sorted(client.payment_providers, key=lambda x: x.sort_order)
            if p.is_enabled
        }
    except RuntimeError:
        # fallback до инициализации клиента
        providers = get_enabled_providers()
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"pay:{plan_id}:{provider}")]
        for provider, label in providers.items()
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"plan:{plan_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ──────────────── Проверка оплаты ────────────────


def check_payment(payment_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check:{payment_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="back:main")],
    ])


# ──────────────── После успешной оплаты ────────────────


def after_payment() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Как подключиться", callback_data="connect")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back:main")],
    ])


# ──────────────── Профиль ────────────────


def profile_menu(has_sub: bool = False, support_url: str = "") -> InlineKeyboardMarkup:
    buttons = []
    if has_sub:
        buttons.append(
            [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="buy")],
        )
        buttons.append(
            [InlineKeyboardButton(text="📱 Как подключиться", callback_data="connect")],
        )
    else:
        buttons.append(
            [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy")],
        )
    if support_url:
        url = (
            support_url if support_url.startswith("http")
            else f"https://t.me/{support_url.lstrip('@')}"
        )
        buttons.append(
            [InlineKeyboardButton(text="🆘 Тех. поддержка", url=url)],
        )
    buttons.append(
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back:main")],
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ──────────────── Подключение ────────────────


def connect_menu(vless_url: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back:main")],
    ])


# ──────────────── Напоминания ────────────────


def renew_prompt() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="buy")],
    ])

