"""Абстракция платёжных провайдеров."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ProviderPaymentStatus(Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PaymentResult:
    """Результат создания платежа у провайдера."""
    provider_payment_id: str
    payment_url: str
    status: ProviderPaymentStatus


@dataclass
class PaymentStatusResult:
    """Результат проверки статуса платежа."""
    provider_payment_id: str
    status: ProviderPaymentStatus


class BasePaymentProvider(ABC):
    """Интерфейс платёжного провайдера."""

    name: str  # "yookassa", "freekassa", ...

    @abstractmethod
    async def create_payment(
        self,
        amount: int,
        order_id: str,
        description: str,
        **kwargs,
    ) -> PaymentResult:
        """Создать платёж. Возвращает ссылку для оплаты."""

    @abstractmethod
    async def check_payment(
        self, provider_payment_id: str,
    ) -> PaymentStatusResult:
        """Проверить статус платежа."""
