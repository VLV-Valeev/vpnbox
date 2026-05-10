"""Фабрика платёжных провайдеров."""
from __future__ import annotations

from app.services.payments.base import BasePaymentProvider

# Все возможные провайдеры: name → (label, [обязательные поля в settings])
_PROVIDER_REGISTRY: dict[str, tuple[str, list[str]]] = {
    "yookassa": ("💳 ЮKassa", ["yookassa_shop_id", "yookassa_secret_key"]),
    "freekassa": ("🏦 FreeKassa", ["freekassa_shop_id", "freekassa_api_key"]),
    "platega": ("💠 Platega", ["platega_merchant_id", "platega_secret_key"]),
    "cryptocloud": ("₿ CryptoCloud", ["cryptocloud_shop_id", "cryptocloud_api_key"]),
    "stars": ("⭐ Telegram Stars", []),   # всегда включён, ключи не нужны
}

_cache: dict[str, BasePaymentProvider] = {}


def get_enabled_providers() -> dict[str, str]:
    """Вернуть только те провайдеры, у которых заполнены все ключи в .env."""
    from app.config import settings

    enabled: dict[str, str] = {}
    for name, (label, required_fields) in _PROVIDER_REGISTRY.items():
        if all(getattr(settings, field, "") for field in required_fields):
            enabled[name] = label
    return enabled


def get_provider(name: str) -> BasePaymentProvider:
    """Получить экземпляр провайдера по имени."""
    if name in _cache:
        return _cache[name]

    if name == "yookassa":
        from app.services.payments.yookassa_provider import YooKassaProvider
        _cache[name] = YooKassaProvider()
    elif name == "freekassa":
        from app.services.payments.freekassa_provider import FreeKassaProvider
        _cache[name] = FreeKassaProvider()
    elif name == "platega":
        from app.services.payments.platega_provider import PlatEgaProvider
        _cache[name] = PlatEgaProvider()
    elif name == "cryptocloud":
        from app.services.payments.cryptocloud_provider import CryptoCloudProvider
        _cache[name] = CryptoCloudProvider()
    else:
        raise ValueError(f"Unknown payment provider: {name}")

    return _cache[name]
