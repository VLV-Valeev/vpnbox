from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic_settings import BaseSettings


# ──────────────── Тарифные планы ──────────────────


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    duration_days: int
    traffic_gb: int        # 0 = безлимит
    price: int             # рублей, 0 = бесплатно
    description: str


PLANS: dict[str, Plan] = {
    "trial": Plan("trial", "Пробный период", 3, 5, 0, "3 дня • 5 ГБ"),
    "1month": Plan("1month", "1 месяц", 30, 100, 149, "30 дней • 100 ГБ"),
    "3months": Plan("3months", "3 месяца", 90, 300, 399, "90 дней • 300 ГБ"),
    "6months": Plan("6months", "6 месяцев", 180, 600, 699, "180 дней • 600 ГБ"),
    "12months": Plan("12months", "1 год", 365, 0, 1190, "365 дней • Безлимит"),
}


class Settings(BaseSettings):
    bot_token: str = ""
    bot_username: str = "vpnbox_bot"
    admin_id: str = ""

    database_url: str = "postgresql+asyncpg://vpnbox:vpnbox@postgres:5432/vpnbox"
    redis_url: str = "redis://redis:6379/0"

    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""

    freekassa_shop_id: str = ""
    freekassa_secret1: str = ""
    freekassa_secret2: str = ""
    freekassa_api_key: str = ""
    freekassa_payment_system_id: int = 0  # ID платёжной системы (обязательно для API)

    platega_merchant_id: str = ""
    platega_secret_key: str = ""
    platega_payment_method: int = 10  # 2=SBP, 10=CardRu/МИР, 12=International

    cryptocloud_shop_id: str = ""
    cryptocloud_api_key: str = ""

    log_level: str = "INFO"

    vpn_servers: str = "[]"

    # ── Web API (опционально, нужно только если установлен web-аддон) ──
    jwt_secret: str = "change-me-to-a-random-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30

    recaptcha_secret_key: str = ""
    recaptcha_site_key: str = ""

    api_cors_origins: str = "http://localhost:3000"
    web_url: str = "http://localhost:3000"

    @property
    def database_url_sync(self) -> str:
        return self.database_url.replace("+asyncpg", "").replace("asyncpg", "psycopg2")

    def get_vpn_servers(self) -> list[dict]:
        return json.loads(self.vpn_servers)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def require(self, field: str) -> str:
        """Получить обязательное поле — бросает RuntimeError с понятным
        сообщением, если поле пустое. Для использования в entrypoint'ах."""
        value = getattr(self, field, "")
        if not value:
            raise RuntimeError(
                f".env: поле {field.upper()} обязательно, но пустое. "
                f"Заполни его в .env и перезапусти сервис."
            )
        return value


settings = Settings()
