from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum as SQLEnum, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ──────────────── Клиент (покупатель бота) ────────────────


class Client(Base):
    """Конфигурация одного покупателя/экземпляра бота."""
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    service_name: Mapped[str] = mapped_column(String(100), default="VPNBox")

    # Приложение для подключения
    vpn_app_name: Mapped[str] = mapped_column(String(100), default="Hiddify")
    vpn_app_android_url: Mapped[str] = mapped_column(
        String(500), default="https://play.google.com/store/apps/details?id=app.hiddify.com",
    )
    vpn_app_ios_url: Mapped[str] = mapped_column(
        String(500), default="https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532",
    )
    vpn_app_desktop_url: Mapped[str] = mapped_column(
        String(500), default="https://github.com/hiddify/hiddify-app/releases/latest",
    )

    # Какие платформы показывать в инструкции по подключению
    vpn_app_show_android: Mapped[bool] = mapped_column(Boolean, default=True)
    vpn_app_show_ios: Mapped[bool] = mapped_column(Boolean, default=True)
    vpn_app_show_desktop: Mapped[bool] = mapped_column(Boolean, default=True)

    # Документы
    terms_url: Mapped[str] = mapped_column(
        String(500), default="https://telegra.ph/Polzovatelskoe-soglashenie-04-10-18",
    )
    privacy_url: Mapped[str] = mapped_column(
        String(500), default="https://telegra.ph/Politika-konfidencialnosti-04-10-17",
    )

    # Контакт поддержки (показывается в профиле пользователя)
    support_url: Mapped[str] = mapped_column(String(500), default="")

    # Реферальная программа
    referral_reward_days: Mapped[int] = mapped_column(Integer, default=7)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    plans: Mapped[list[ClientPlan]] = relationship(
        back_populates="client", lazy="selectin",
        order_by="ClientPlan.sort_order",
    )
    payment_providers: Mapped[list[ClientPaymentProvider]] = relationship(
        back_populates="client", lazy="selectin",
        order_by="ClientPaymentProvider.sort_order",
    )


class ClientPlan(Base):
    """Тарифный план конкретного клиента."""
    __tablename__ = "client_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    slug: Mapped[str] = mapped_column(String(50))        # "trial", "1month", …
    name: Mapped[str] = mapped_column(String(100))       # "1 месяц"
    duration_days: Mapped[int] = mapped_column(Integer)
    traffic_gb: Mapped[int] = mapped_column(Integer, default=0)   # 0 = безлимит
    price: Mapped[int] = mapped_column(Integer, default=0)        # ₽, 0 = бесплатно
    description: Mapped[str] = mapped_column(String(200), default="")
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    client: Mapped[Client] = relationship(back_populates="plans")


class ClientPaymentProvider(Base):
    """Настройки платёжного провайдера для конкретного клиента."""
    __tablename__ = "client_payment_providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    provider: Mapped[str] = mapped_column(String(50))    # "yookassa", "stars", …
    label: Mapped[str] = mapped_column(String(100))      # "💳 ЮKassa"
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}")  # JSON с ключами провайдера
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    client: Mapped[Client] = relationship(back_populates="payment_providers")


# ──────────────── VPN-серверы ────────────────


class Server(Base):
    """VPN-сервер (панель 3X-UI)."""
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    panel_type: Mapped[str] = mapped_column(String(20))       # "3xui"
    url: Mapped[str] = mapped_column(String(500))
    username: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(255))
    country: Mapped[str] = mapped_column(String(10), default="🌍")
    inbound_id: Mapped[int] = mapped_column(Integer, default=1)   # только для 3x-ui
    max_users: Mapped[int] = mapped_column(Integer, default=500)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())


# ──────────────── Enums ────────────────


class SubStatus(enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"


class PayStatus(enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"


# ──────────────── Models ────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")  # "user" / "admin"
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    referrer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, default=None,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subscriptions: Mapped[list[Subscription]] = relationship(
        back_populates="user", lazy="selectin",
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="user", lazy="selectin",
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    plan_id: Mapped[str] = mapped_column(String(50))
    vpn_username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    server_id: Mapped[int] = mapped_column(Integer)
    subscription_url: Mapped[str] = mapped_column(Text)
    status: Mapped[SubStatus] = mapped_column(
        SQLEnum(SubStatus), default=SubStatus.TRIAL,
    )
    traffic_limit_gb: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    notified_expiry: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="subscriptions")
    payments: Mapped[list[Payment]] = relationship(
        back_populates="subscription", lazy="selectin",
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id"), nullable=True,
    )
    plan_id: Mapped[str] = mapped_column(String(50))
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    provider: Mapped[str] = mapped_column(String(50), default="yookassa")
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True,
    )
    confirmation_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PayStatus] = mapped_column(
        SQLEnum(PayStatus), default=PayStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    referral_reward_given: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="payments")
    subscription: Mapped[Subscription | None] = relationship(back_populates="payments")
