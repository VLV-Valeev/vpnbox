"""Сервис загрузки и кэширования конфигурации клиента (покупателя бота).

При старте бота вызывается init_client() — она:
  1. Ищет запись Client в БД по bot_token.
  2. Если не найдена — создаёт дефолтную из текущих settings / PLANS.
  3. Синхронизирует PLANS, настройки платёжных провайдеров и тексты бота.
  4. Загружает список admin telegram_id из таблицы users.

Все остальные модули используют get_client() / is_admin() / get_stars_rate().
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Plan, PLANS, settings

if TYPE_CHECKING:
    from app.db.models import Client

_current_client: "Client | None" = None
_stars_rate: int = 2
_admin_tg_ids: set[int] = set()


# ──────────────── Публичный API ────────────────


async def init_client(session: AsyncSession, bot_token: str) -> "Client":
    """Загрузить клиента и синхронизировать конфиг. Вызывать один раз при старте."""
    global _current_client, _stars_rate

    from app.db.models import Client

    client = (await session.execute(
        select(Client).where(Client.bot_token == bot_token),
    )).scalar_one_or_none()

    if not client:
        client = await _create_default_client(session, bot_token)
    else:
        await _sync_env_to_db(session, client)

    _current_client = client

    _sync_plans(client)
    _stars_rate = _sync_payment_settings(client)

    await _load_admin_ids(session)

    from app.bot import texts
    texts.init(client)

    return client


def get_client() -> "Client":
    if _current_client is None:
        raise RuntimeError("Клиент не инициализирован. Вызовите init_client() при старте.")
    return _current_client


def is_admin(user_id: int) -> bool:
    """Проверка по кэшу admin IDs (из User.role) + fallback на .env."""
    if user_id in _admin_tg_ids:
        return True
    # Fallback: пользователь из .env, но ещё не /start'нул бота
    return user_id in _get_env_admin_ids()


def get_stars_rate() -> int:
    return _stars_rate


def get_env_admin_ids() -> set[int]:
    """Публичный доступ к ADMIN_ID из .env (для сидинга роли при регистрации)."""
    return _get_env_admin_ids()


def add_admin(tg_id: int) -> None:
    """Добавить admin в кэш (после изменения User.role в БД)."""
    _admin_tg_ids.add(tg_id)


def remove_admin(tg_id: int) -> None:
    """Убрать admin из кэша (после изменения User.role в БД)."""
    _admin_tg_ids.discard(tg_id)


# ──────────────── Внутренние функции ────────────────


def _get_env_admin_ids() -> set[int]:
    raw = settings.admin_id or ""
    try:
        return {int(x.strip()) for x in raw.split(",") if x.strip()}
    except ValueError:
        return set()


async def _load_admin_ids(session: AsyncSession) -> None:
    """Загрузить telegram_id всех админов из таблицы users."""
    global _admin_tg_ids
    from app.db.models import User
    result = await session.execute(
        select(User.telegram_id).where(User.role == "admin")
    )
    db_admins = {row[0] for row in result.all()}
    _admin_tg_ids = db_admins


def _sync_plans(client: "Client") -> None:
    active = [p for p in client.plans if p.is_active]
    if not active:
        return

    PLANS.clear()
    for db_plan in active:
        PLANS[db_plan.slug] = Plan(
            id=db_plan.slug,
            name=db_plan.name,
            duration_days=db_plan.duration_days,
            traffic_gb=db_plan.traffic_gb,
            price=db_plan.price,
            description=db_plan.description,
        )


def _sync_payment_settings(client: "Client") -> int:
    stars_rate = 2

    for provider in client.payment_providers:
        if not provider.is_enabled:
            continue

        cfg: dict = json.loads(provider.config_json or "{}")

        if provider.provider == "yookassa":
            settings.yookassa_shop_id = cfg.get("shop_id", "")
            settings.yookassa_secret_key = cfg.get("secret_key", "")
            try:
                import app.services.payments.yookassa_provider as yk
                yk._configured = False
            except ImportError:
                pass

        elif provider.provider == "freekassa":
            settings.freekassa_shop_id = cfg.get("shop_id", "")
            settings.freekassa_secret1 = cfg.get("secret1", "")
            settings.freekassa_secret2 = cfg.get("secret2", "")
            settings.freekassa_api_key = cfg.get("api_key", "")

        elif provider.provider == "platega":
            settings.platega_merchant_id = cfg.get("merchant_id", "")
            settings.platega_secret_key = cfg.get("secret_key", "")

        elif provider.provider == "cryptocloud":
            settings.cryptocloud_shop_id = cfg.get("shop_id", "")
            settings.cryptocloud_api_key = cfg.get("api_key", "")

        elif provider.provider == "stars":
            stars_rate = int(cfg.get("stars_rate", 2))

    return stars_rate


async def _sync_env_to_db(session: AsyncSession, client: "Client") -> None:
    """Синхронизирует credentials платёжных провайдеров из .env в БД."""
    import json as _json

    changed = False

    _ENV_PROVIDERS: dict[str, tuple[dict, bool]] = {
        "yookassa": (
            {"shop_id": settings.yookassa_shop_id, "secret_key": settings.yookassa_secret_key},
            bool(settings.yookassa_shop_id and settings.yookassa_secret_key),
        ),
        "freekassa": (
            {"shop_id": settings.freekassa_shop_id, "secret1": settings.freekassa_secret1,
             "secret2": settings.freekassa_secret2, "api_key": settings.freekassa_api_key},
            bool(settings.freekassa_shop_id and settings.freekassa_api_key),
        ),
        "platega": (
            {"merchant_id": settings.platega_merchant_id, "secret_key": settings.platega_secret_key},
            bool(settings.platega_merchant_id and settings.platega_secret_key),
        ),
        "cryptocloud": (
            {"shop_id": settings.cryptocloud_shop_id, "api_key": settings.cryptocloud_api_key},
            bool(settings.cryptocloud_shop_id and settings.cryptocloud_api_key),
        ),
    }

    for db_provider in client.payment_providers:
        env_entry = _ENV_PROVIDERS.get(db_provider.provider)
        if env_entry is None:
            continue

        env_cfg, env_has_creds = env_entry

        if not env_has_creds:
            # Ключей в .env нет — отключаем провайдер в БД
            if db_provider.is_enabled:
                db_provider.is_enabled = False
                changed = True
            continue

        new_json = _json.dumps(env_cfg, ensure_ascii=False)
        if db_provider.config_json != new_json or not db_provider.is_enabled:
            db_provider.config_json = new_json
            db_provider.is_enabled = True
            changed = True

    if changed:
        await session.commit()
        await session.refresh(client, ["plans", "payment_providers"])


async def _create_default_client(session: AsyncSession, bot_token: str) -> "Client":
    from app.db.models import Client, ClientPlan, ClientPaymentProvider

    client = Client(
        bot_token=bot_token,
        service_name="VPNBox",
    )
    session.add(client)
    await session.flush()

    for i, (slug, plan) in enumerate(PLANS.items()):
        session.add(ClientPlan(
            client_id=client.id,
            slug=plan.id,
            name=plan.name,
            duration_days=plan.duration_days,
            traffic_gb=plan.traffic_gb,
            price=plan.price,
            description=plan.description,
            is_trial=(plan.id == "trial"),
            is_active=True,
            sort_order=i,
        ))

    _PROVIDERS = [
        ("yookassa", "💳 ЮKassa", 0, {
            "shop_id": settings.yookassa_shop_id,
            "secret_key": settings.yookassa_secret_key,
        }, bool(settings.yookassa_shop_id and settings.yookassa_secret_key)),
        ("freekassa", "🏦 FreeKassa", 1, {
            "shop_id": settings.freekassa_shop_id,
            "secret1": settings.freekassa_secret1,
            "secret2": settings.freekassa_secret2,
            "api_key": settings.freekassa_api_key,
        }, bool(settings.freekassa_shop_id and settings.freekassa_api_key)),
        ("platega", "💠 Platega", 2, {
            "merchant_id": settings.platega_merchant_id,
            "secret_key": settings.platega_secret_key,
        }, bool(settings.platega_merchant_id and settings.platega_secret_key)),
        ("cryptocloud", "₿ CryptoCloud", 3, {
            "shop_id": settings.cryptocloud_shop_id,
            "api_key": settings.cryptocloud_api_key,
        }, bool(settings.cryptocloud_shop_id and settings.cryptocloud_api_key)),
        ("stars", "⭐ Telegram Stars", 4, {"stars_rate": 2}, True),
    ]

    for provider_name, label, order, cfg, enabled in _PROVIDERS:
        session.add(ClientPaymentProvider(
            client_id=client.id,
            provider=provider_name,
            label=label,
            is_enabled=enabled,
            config_json=json.dumps(cfg, ensure_ascii=False),
            sort_order=order,
        ))

    await session.commit()

    client = (await session.execute(
        select(Client).where(Client.bot_token == bot_token),
    )).scalar_one()

    return client
