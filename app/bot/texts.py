"""Все тексты бота в одном месте.

Модуль-уровневые переменные — дефолтные значения (VPNBox).
После загрузки клиента из БД вызывается init(client), которая обновляет их.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.config import PLANS

if TYPE_CHECKING:
    from app.db.models import Client

# ──────────────── Главное меню ────────────────

LEGAL_AGREEMENT = (
    "📄 <a href=\"https://telegra.ph/Polzovatelskoe-soglashenie-04-10-18\">Пользовательское соглашение</a> · "
    "<a href=\"https://telegra.ph/Politika-konfidencialnosti-04-10-17\">Политика конфиденциальности</a>\n"
    "<i>Используя бота, вы принимаете условия этих документов.</i>"
)

INFO_TEXT = (
    "ℹ️ <b>Информация о VPNBox</b>\n\n"
    "📄 <b>Документы:</b>\n"
    "• <a href=\"https://telegra.ph/Polzovatelskoe-soglashenie-04-10-18\">Пользовательское соглашение</a>\n"
    "• <a href=\"https://telegra.ph/Politika-konfidencialnosti-04-10-17\">Политика конфиденциальности</a>"
)

WELCOME = (
    "👋 <b>Добро пожаловать в VPNBox!</b>\n\n"
    "Быстрый, безопасный и надёжный VPN для всех устройств.\n\n"
    "🎁 Попробуйте бесплатно — <b>3 дня</b> без оплаты!"
)

WELCOME_BACK = (
    "👋 <b>С возвращением!</b>\n\n"
    "Выберите действие:"
)

# ──────────────── Пробный период ────────────────

TRIAL_ACTIVATED = (
    "✅ <b>Пробный период активирован!</b>\n\n"
    "📋 Детали:\n"
    "• Срок: <b>3 дня</b>\n"
    "• Трафик: <b>5 ГБ</b>\n"
    "• Действует до: <b>{expires}</b>\n\n"
    "🔗 <b>Ваша ссылка для подключения:</b>\n"
    "<code>{url}</code>\n\n"
    "👇 Нажмите на ссылку выше, чтобы скопировать, "
    "или используйте кнопку ниже для быстрого подключения."
)

TRIAL_ALREADY_USED = (
    "❌ Вы уже использовали пробный период.\n\n"
    "Оформите подписку, чтобы продолжить пользоваться VPN!"
)

HAS_ACTIVE_SUB = (
    "ℹ️ У вас уже есть активная подписка.\n\n"
    "Откройте профиль, чтобы посмотреть детали."
)

NO_SERVERS = (
    "😔 К сожалению, все серверы сейчас перегружены.\n"
    "Попробуйте позже или обратитесь в поддержку."
)

# ──────────────── Тарифы ────────────────

CHOOSE_PLAN = (
    "💳 <b>Выберите тарифный план:</b>\n\n"
    "• <b>1 месяц</b> — 149 ₽ (100 ГБ)\n"
    "• <b>3 месяца</b> — 399 ₽ (300 ГБ) 💡 <i>экономия 11%</i>\n"
    "• <b>6 месяцев</b> — 699 ₽ (600 ГБ) 🔥 <i>экономия 22%</i>\n"
    "• <b>1 год</b> — 1190 ₽ (Безлимит) ⭐ <i>экономия 33%</i>"
)

ORDER_SUMMARY = (
    "🛒 <b>Ваш заказ:</b>\n\n"
    "📦 Тариф: <b>{plan_name}</b>\n"
    "📊 Трафик: <b>{traffic}</b>\n"
    "💰 Стоимость: <b>{price} ₽</b>"
)

CHOOSE_PAYMENT_METHOD = (
    "🏦 <b>Выберите способ оплаты:</b>"
)

# ──────────────── Оплата ────────────────

PAY_LINK = (
    "💳 Для оплаты перейдите по ссылке:\n\n"
    "👉 <a href=\"{url}\">Оплатить {price} ₽</a>\n\n"
    "После оплаты нажмите <b>«Проверить оплату»</b> ниже."
)

PAYMENT_SUCCESS = (
    "✅ <b>Оплата подтверждена!</b>\n\n"
    "📋 Ваша подписка:\n"
    "• Тариф: <b>{plan_name}</b>\n"
    "• Действует до: <b>{expires}</b>\n\n"
    "🔗 <b>Ваша ссылка для подключения:</b>\n"
    "<code>{url}</code>"
)

PAYMENT_PENDING = (
    "⏳ Оплата ещё не поступила.\n\n"
    "Если вы уже оплатили, подождите пару минут "
    "и нажмите <b>«Проверить оплату»</b> ещё раз."
)

PAYMENT_CANCELLED = (
    "❌ Платёж был отменён.\n"
    "Вы можете оформить новый заказ."
)

PAYMENT_ERROR = (
    "⚠️ Ошибка при создании платежа.\n"
    "Попробуйте позже или обратитесь в поддержку."
)

# ──────────────── Профиль ────────────────

PROFILE_ACTIVE = (
    "👤 <b>Ваш профиль</b>\n\n"
    "📋 Подписка: <b>Активна ✅</b>\n"
    "• Тариф: <b>{plan_name}</b>\n"
    "• Действует до: <b>{expires}</b>\n"
    "• Трафик: <b>{traffic}</b>\n\n"
    "🔗 Ссылка:\n<code>{url}</code>"
)

PROFILE_NO_SUB = (
    "👤 <b>Ваш профиль</b>\n\n"
    "📋 Подписка: <b>Нет активной подписки</b>\n\n"
    "Оформите подписку, чтобы получить доступ к VPN."
)

# ──────────────── Подключение ────────────────

CONNECT_GUIDE = (
    "📱 <b>Инструкция по подключению</b>\n\n"
    "<b>1.</b> Скачайте приложение <b>Hiddify</b>:\n"
    "   • <a href=\"https://play.google.com/store/apps/details?id=app.hiddify.com\">Android (Google Play)</a>\n"
    "   • <a href=\"https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532\">iOS (App Store)</a>\n"
    "   • <a href=\"https://github.com/hiddify/hiddify-app/releases/latest\">Windows / macOS / Linux</a>\n\n"
    "<b>2.</b> Откройте Hiddify\n\n"
    "<b>3.</b> Нажмите <b>«+»</b> → <b>«Добавить из буфера»</b>\n\n"
    "<b>4.</b> Скопируйте вашу ссылку (нажмите на неё):\n"
    "<code>{url}</code>\n\n"
    "<b>5.</b> Вставьте ссылку в Hiddify и подключайтесь! 🚀"
)

CONNECT_NO_SUB = (
    "❌ У вас нет активной подписки.\n"
    "Сначала активируйте пробный период или купите подписку."
)

# ──────────────── Реферальная программа ────────────────

REFERRAL_INFO = (
    "👥 <b>Реферальная программа</b>\n\n"
    "Приглашайте друзей и получайте бонусы!\n\n"
    "🎁 <b>Ваш бонус:</b> +7 дн. к подписке за каждого друга, оформившего платную подписку\n"
    "🎁 <b>Бонус друга:</b> 3 дня бесплатного доступа после регистрации по вашей ссылке\n\n"
    "🔗 <b>Ваша реферальная ссылка:</b>\n"
    "<code>{ref_link}</code>"
)

REFERRAL_STATS = (
    "📊 <b>Статистика рефералов</b>\n\n"
    "👥 Всего приглашено: <b>{total}</b>\n"
    "💳 Оформили платную подписку: <b>{paid}</b>"
)

REFERRAL_TRIAL_BONUS = (
    "🎁 <b>Бонус за регистрацию по реферальной ссылке!</b>\n\n"
    "📋 Детали:\n"
    "• Срок: <b>3 дня</b>\n"
    "• Действует до: <b>{expires}</b>\n\n"
    "🔗 <b>Ваша ссылка для подключения:</b>\n"
    "<code>{url}</code>"
)

# ──────────────── Поддержка ────────────────

SUPPORT_TEXT = (
    "🆘 <b>Тех. поддержка</b>\n\n"
    "Если у вас возникли вопросы или проблемы — напишите нашему менеджеру:\n\n"
    "👉 @support"
)

# ──────────────── Напоминания ────────────────

EXPIRY_REMINDER = (
    "⏰ <b>Ваша подписка VPNBox истекает завтра!</b>\n\n"
    "Продлите подписку, чтобы не потерять доступ к VPN."
)

SUB_EXPIRED = (
    "❌ <b>Ваша подписка VPNBox истекла.</b>\n\n"
    "Оформите новую подписку, чтобы продолжить пользоваться VPN."
)


# ──────────────── Инициализация из конфига клиента ────────────────


def init(client: "Client") -> None:
    """
    Обновить все модуль-уровневые тексты на основе конфига клиента из БД.
    Вызывается один раз при старте после загрузки клиента.
    """
    global LEGAL_AGREEMENT, INFO_TEXT, WELCOME, CONNECT_GUIDE, \
           EXPIRY_REMINDER, SUB_EXPIRED, CHOOSE_PLAN, TRIAL_ACTIVATED, SUPPORT_TEXT, REFERRAL_INFO

    sn = client.service_name

    LEGAL_AGREEMENT = (
        f'📄 <a href="{client.terms_url}">Пользовательское соглашение</a> · '
        f'<a href="{client.privacy_url}">Политика конфиденциальности</a>\n'
        f'<i>Используя бота, вы принимаете условия этих документов.</i>'
    )

    INFO_TEXT = (
        f'ℹ️ <b>Информация о {sn}</b>\n\n'
        f'📄 <b>Документы:</b>\n'
        f'• <a href="{client.terms_url}">Пользовательское соглашение</a>\n'
        f'• <a href="{client.privacy_url}">Политика конфиденциальности</a>'
    )

    WELCOME = (
        f'👋 <b>Добро пожаловать в {sn}!</b>\n\n'
        f'Быстрый, безопасный и надёжный VPN для всех устройств.\n\n'
        f'🎁 Попробуйте бесплатно — <b>3 дня</b> без оплаты!'
    )

    platform_lines = []
    if client.vpn_app_show_android:
        platform_lines.append(f'   • <a href="{client.vpn_app_android_url}">Android (Google Play)</a>')
    if client.vpn_app_show_ios:
        platform_lines.append(f'   • <a href="{client.vpn_app_ios_url}">iOS (App Store)</a>')
    if client.vpn_app_show_desktop:
        platform_lines.append(f'   • <a href="{client.vpn_app_desktop_url}">Windows / macOS / Linux</a>')

    platforms_block = "\n".join(platform_lines) if platform_lines else f'   • {client.vpn_app_name}'

    CONNECT_GUIDE = (
        f'📱 <b>Инструкция по подключению</b>\n\n'
        f'<b>1.</b> Скачайте приложение <b>{client.vpn_app_name}</b>:\n'
        f'{platforms_block}\n\n'
        f'<b>2.</b> Откройте {client.vpn_app_name}\n\n'
        f'<b>3.</b> Нажмите <b>«+»</b> → <b>«Добавить из буфера»</b>\n\n'
        f'<b>4.</b> Скопируйте вашу ссылку (нажмите на неё):\n'
        f'<code>{{url}}</code>\n\n'
        f'<b>5.</b> Вставьте ссылку в {client.vpn_app_name} и подключайтесь! 🚀'
    )

    EXPIRY_REMINDER = (
        f'⏰ <b>Ваша подписка {sn} истекает завтра!</b>\n\n'
        f'Продлите подписку, чтобы не потерять доступ к VPN.'
    )

    SUB_EXPIRED = (
        f'❌ <b>Ваша подписка {sn} истекла.</b>\n\n'
        f'Оформите новую подписку, чтобы продолжить пользоваться VPN.'
    )

    if client.support_url:
        contact = client.support_url
        # @username → ссылка в тексте, полный URL — оставляем как есть
        if contact.startswith("@"):
            contact_line = contact
        else:
            contact_line = f'<a href="{contact}">Написать в поддержку</a>'
        SUPPORT_TEXT = (
            f'🆘 <b>Тех. поддержка</b>\n\n'
            f'Если у вас возникли вопросы или проблемы — напишите нашему менеджеру:\n\n'
            f'👉 {contact_line}'
        )
    else:
        SUPPORT_TEXT = (
            "🆘 <b>Тех. поддержка</b>\n\n"
            "Контакт поддержки не настроен. Обратитесь к администратору бота."
        )

    reward_days = getattr(client, "referral_reward_days", 7)
    REFERRAL_INFO = (
        "👥 <b>Реферальная программа</b>\n\n"
        "Приглашайте друзей и получайте бонусы!\n\n"
        f"🎁 <b>Ваш бонус:</b> +{reward_days} дн. к подписке за каждого друга, оформившего платную подписку\n"
        "🎁 <b>Бонус друга:</b> 3 дня бесплатного доступа после регистрации по вашей ссылке\n\n"
        "🔗 <b>Ваша реферальная ссылка:</b>\n"
        "<code>{ref_link}</code>"
    )

    # Перестраиваем текст выбора тарифа из актуальных PLANS
    CHOOSE_PLAN = _build_choose_plan()

    # Обновляем детали пробного периода из плана trial
    trial = PLANS.get("trial")
    if trial:
        TRIAL_ACTIVATED = (
            "✅ <b>Пробный период активирован!</b>\n\n"
            "📋 Детали:\n"
            f"• Срок: <b>{trial.duration_days} дн.</b>\n"
            f"• Трафик: <b>{traffic_text(trial.traffic_gb)}</b>\n"
            "• Действует до: <b>{expires}</b>\n\n"
            "🔗 <b>Ваша ссылка для подключения:</b>\n"
            "<code>{url}</code>\n\n"
            "👇 Нажмите на ссылку выше, чтобы скопировать, "
            "или используйте кнопку ниже для быстрого подключения."
        )


def _build_choose_plan() -> str:
    """Построить текст выбора тарифа из текущих PLANS."""
    lines = ["💳 <b>Выберите тарифный план:</b>\n"]
    for plan in PLANS.values():
        if plan.price == 0:
            continue
        traffic = traffic_text(plan.traffic_gb)
        lines.append(f"• <b>{plan.name}</b> — {plan.price} ₽ ({traffic})")
    return "\n".join(lines)


# ──────────────── Helpers ────────────────


def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


def traffic_text(gb: int) -> str:
    return "Безлимит" if gb == 0 else f"{gb} ГБ"
