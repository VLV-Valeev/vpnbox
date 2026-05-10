"""Platega.io payment provider.

API docs: https://docs.platega.io/
Base URL: https://app.platega.io/
Auth: X-MerchantId + X-Secret headers (no HMAC, static keys).
"""
from __future__ import annotations

import uuid

import aiohttp

from app.config import settings
from app.services.payments.base import (
    BasePaymentProvider,
    PaymentResult,
    PaymentStatusResult,
    ProviderPaymentStatus,
)

_API_BASE = "https://app.platega.io"

# Platega statuses → internal
_STATUS_MAP: dict[str, ProviderPaymentStatus] = {
    "NONE":         ProviderPaymentStatus.PENDING,
    "CREATED":      ProviderPaymentStatus.PENDING,
    "PENDING":      ProviderPaymentStatus.PENDING,
    "INPROGRESS":   ProviderPaymentStatus.PENDING,
    "CONFIRMED":    ProviderPaymentStatus.SUCCEEDED,
    "FAILED":       ProviderPaymentStatus.FAILED,
    "EXPIRED":      ProviderPaymentStatus.FAILED,
    "CANCELED":     ProviderPaymentStatus.CANCELLED,
    "REFUNDED":     ProviderPaymentStatus.CANCELLED,
    "CHARGEBACKED": ProviderPaymentStatus.FAILED,
}

# Метод оплаты по умолчанию: integer enum (2=SBP, 10=CardRu/МИР, 12=International)
_DEFAULT_PAYMENT_METHOD = 10


class PlatEgaProvider(BasePaymentProvider):
    name = "platega"

    def _headers(self) -> dict:
        return {
            "X-MerchantId": settings.platega_merchant_id,
            "X-Secret": settings.platega_secret_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def create_payment(
        self,
        amount: int,
        order_id: str,
        description: str,
        **kwargs,
    ) -> PaymentResult:
        transaction_id = str(uuid.uuid4())
        payment_method = int(
            kwargs.get("payment_method") or settings.platega_payment_method or _DEFAULT_PAYMENT_METHOD
        )
        bot_url = "https://t.me/" + settings.bot_username
        payload = {
            "paymentMethod": payment_method,
            "id": transaction_id,
            "paymentDetails": {
                "amount": float(amount),
                "currency": "RUB",
            },
            "description": description,
            "return": bot_url,
            "failedUrl": bot_url,
            "payload": order_id,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_API_BASE}/transaction/process",
                json=payload,
                headers=self._headers(),
            ) as resp:
                body = await resp.json(content_type=None)

        if resp.status != 200 or "redirect" not in body:
            raise RuntimeError(f"Platega error: {body}")

        return PaymentResult(
            provider_payment_id=body.get("transactionId", transaction_id),
            payment_url=body["redirect"],
            status=ProviderPaymentStatus.PENDING,
        )

    async def check_payment(
        self, provider_payment_id: str,
    ) -> PaymentStatusResult:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{_API_BASE}/transaction/{provider_payment_id}",
                headers=self._headers(),
            ) as resp:
                body = await resp.json(content_type=None)

        if resp.status != 200:
            raise RuntimeError(f"Platega error: {body}")

        raw_status = body.get("status", "PENDING")
        return PaymentStatusResult(
            provider_payment_id=provider_payment_id,
            status=_STATUS_MAP.get(raw_status, ProviderPaymentStatus.PENDING),
        )
