"""YooKassa payment provider."""
from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

from yookassa import Configuration, Payment as YKPayment

from app.config import settings
from app.services.payments.base import (
    BasePaymentProvider,
    PaymentResult,
    PaymentStatusResult,
    ProviderPaymentStatus,
)

_executor = ThreadPoolExecutor(max_workers=4)
_configured = False


def _ensure_configured() -> None:
    global _configured
    if not _configured:
        Configuration.account_id = settings.yookassa_shop_id
        Configuration.secret_key = settings.yookassa_secret_key
        _configured = True


_YK_STATUS_MAP = {
    "pending": ProviderPaymentStatus.PENDING,
    "waiting_for_capture": ProviderPaymentStatus.PENDING,
    "succeeded": ProviderPaymentStatus.SUCCEEDED,
    "canceled": ProviderPaymentStatus.CANCELLED,
}


class YooKassaProvider(BasePaymentProvider):
    name = "yookassa"

    async def create_payment(
        self,
        amount: int,
        order_id: str,
        description: str,
        **kwargs,
    ) -> PaymentResult:
        return_url = kwargs.get("return_url") or f"https://t.me/{settings.bot_username}"
        metadata = kwargs.get("metadata", {})

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            _executor,
            self._create_sync,
            amount,
            description,
            metadata,
            return_url,
        )
        return result

    async def check_payment(
        self, provider_payment_id: str,
    ) -> PaymentStatusResult:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _executor, self._check_sync, provider_payment_id,
        )

    @staticmethod
    def _create_sync(
        amount: int, description: str, metadata: dict, return_url: str,
    ) -> PaymentResult:
        _ensure_configured()
        payment = YKPayment.create(
            {
                "amount": {"value": f"{amount}.00", "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url,
                },
                "capture": True,
                "description": description,
                "metadata": metadata,
            },
            idempotency_key=str(uuid.uuid4()),
        )
        return PaymentResult(
            provider_payment_id=payment.id,
            payment_url=payment.confirmation.confirmation_url,
            status=_YK_STATUS_MAP.get(payment.status, ProviderPaymentStatus.PENDING),
        )

    @staticmethod
    def _check_sync(provider_payment_id: str) -> PaymentStatusResult:
        _ensure_configured()
        payment = YKPayment.find_one(provider_payment_id)
        return PaymentStatusResult(
            provider_payment_id=payment.id,
            status=_YK_STATUS_MAP.get(payment.status, ProviderPaymentStatus.PENDING),
        )
