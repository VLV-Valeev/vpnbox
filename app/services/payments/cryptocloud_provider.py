"""CryptoCloud payment provider.

API docs: https://docs.cryptocloud.plus/
Base URL: https://api.cryptocloud.plus/v2/
Auth: Authorization: Token <API_KEY>
Polling: POST /v2/invoice/merchant/info with {"uuids": [...]}
"""
from __future__ import annotations

import aiohttp

from app.config import settings
from app.services.payments.base import (
    BasePaymentProvider,
    PaymentResult,
    PaymentStatusResult,
    ProviderPaymentStatus,
)

_API_BASE = "https://api.cryptocloud.plus/v2"

# CryptoCloud invoice statuses → internal
_STATUS_MAP: dict[str, ProviderPaymentStatus] = {
    "created": ProviderPaymentStatus.PENDING,
    "partial": ProviderPaymentStatus.PENDING,
    "paid":    ProviderPaymentStatus.SUCCEEDED,
    "overpaid": ProviderPaymentStatus.SUCCEEDED,
    "canceled": ProviderPaymentStatus.CANCELLED,
}


class CryptoCloudProvider(BasePaymentProvider):
    name = "cryptocloud"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Token {settings.cryptocloud_api_key}",
            "Content-Type": "application/json",
        }

    async def create_payment(
        self,
        amount: int,
        order_id: str,
        description: str,
        **kwargs,
    ) -> PaymentResult:
        payload = {
            "shop_id": settings.cryptocloud_shop_id,
            "amount": float(amount),
            "currency": "RUB",
            "order_id": order_id,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_API_BASE}/invoice/create",
                json=payload,
                headers=self._headers(),
            ) as resp:
                body = await resp.json(content_type=None)

        if resp.status != 200 or body.get("status") != "success":
            raise RuntimeError(f"CryptoCloud error: {body}")

        result = body["result"]
        return PaymentResult(
            provider_payment_id=result["uuid"],   # формат: "INV-XXXXXXXX"
            payment_url=result["link"],
            status=ProviderPaymentStatus.PENDING,
        )

    async def check_payment(
        self, provider_payment_id: str,
    ) -> PaymentStatusResult:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_API_BASE}/invoice/merchant/info",
                json={"uuids": [provider_payment_id]},
                headers=self._headers(),
            ) as resp:
                body = await resp.json(content_type=None)

        if resp.status != 200 or body.get("status") != "success":
            raise RuntimeError(f"CryptoCloud error: {body}")

        invoices = body.get("result", [])
        if not invoices:
            return PaymentStatusResult(
                provider_payment_id=provider_payment_id,
                status=ProviderPaymentStatus.PENDING,
            )

        raw_status = invoices[0].get("status", "created")
        return PaymentStatusResult(
            provider_payment_id=provider_payment_id,
            status=_STATUS_MAP.get(raw_status, ProviderPaymentStatus.PENDING),
        )
