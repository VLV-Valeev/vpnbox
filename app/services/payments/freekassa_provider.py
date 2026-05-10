"""FreeKassa payment provider.

API docs: https://docs.freekassa.net/
Base URL: https://api.fk.life/v1
Auth: HMAC-SHA256 — все поля запроса (кроме signature) сортируются по ключу
      алфавитно, значения объединяются через '|'.

Ключевые моменты:
- Поля в camelCase: paymentId, shopId
- При создании заказа: используем только paymentId (не orderId)
- Подпись: sorted_keys → values joined by '|' → HMAC-SHA256(api_key)
"""
from __future__ import annotations

import hashlib
import hmac
import time
import socket

import aiohttp

from app.config import settings
from app.services.payments.base import (
    BasePaymentProvider,
    PaymentResult,
    PaymentStatusResult,
    ProviderPaymentStatus,
)

import logging
_logger = logging.getLogger(__name__)

_API_BASE = "https://api.fk.life/v1"

# FreeKassa статусы заказа → внутренний статус
_FK_STATUS_MAP = {
    0: ProviderPaymentStatus.PENDING,    # ожидает оплаты
    1: ProviderPaymentStatus.SUCCEEDED,  # оплачен
    8: ProviderPaymentStatus.FAILED,     # отменён / ошибка
    9: ProviderPaymentStatus.CANCELLED,  # возврат
}


def _sign(params: dict, api_key: str) -> str:
    """HMAC-SHA256: все поля (кроме 'signature') сортируем по ключу алфавитно."""
    fields = sorted(k for k in params if k != "signature")
    parts = []
    for k in fields:
        v = params[k]
        if isinstance(v, float):
            parts.append(str(int(v)) if v == int(v) else str(v))
        else:
            parts.append(str(v))
    msg = "|".join(parts)
    sig = hmac.new(api_key.encode(), msg.encode(), hashlib.sha256).hexdigest()
    _logger.debug("FK SIGN: fields=%s msg=%r sig=%.12s...", fields, msg, sig)
    return sig


def _is_private_ip(ip: str) -> bool:
    """Проверить, является ли IP частным/локальным."""
    try:
        parts = ip.split(".")
        if len(parts) != 4:
            return True
        octets = [int(p) for p in parts]
        if octets[0] == 10:
            return True
        if octets[0] == 172 and 16 <= octets[1] <= 31:
            return True
        if octets[0] == 192 and octets[1] == 168:
            return True
        if octets[0] == 127:
            return True
        if ip == "0.0.0.0":
            return True
        return False
    except Exception:
        return True


def _get_server_ip() -> str:
    """Получить внешний IP сервера как fallback."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "5.255.255.1"


def _to_amount(amount) -> int | float:
    """Вернуть amount как число (int если целое, float если дробное)."""
    f = float(amount)
    return int(f) if f == int(f) else f


class FreeKassaProvider(BasePaymentProvider):
    name = "freekassa"

    async def create_payment(
        self,
        amount: int,
        order_id: str,
        description: str,
        **kwargs,
    ) -> PaymentResult:
        # Определяем IP пользователя
        ip = kwargs.get("ip") or _get_server_ip()
        if _is_private_ip(ip):
            ip = _get_server_ip()

        payment_system_id = int(
            kwargs.get("payment_system_id") or settings.freekassa_payment_system_id
        )

        params = {
            "shopId": int(settings.freekassa_shop_id),
            "nonce": time.time_ns(),
            "paymentId": order_id,
            "i": payment_system_id,
            "amount": _to_amount(amount),
            "currency": kwargs.get("currency", "RUB"),
            "email": kwargs.get("email", "user@vpnbox.app"),
            "ip": ip,
        }

        params["signature"] = _sign(params, settings.freekassa_api_key)

        headers = {
            "Content-Type": "application/json",
        }

        _logger.info(
            "FK create_payment: paymentId=%s amount=%s",
            order_id, params["amount"],
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_API_BASE}/orders/create",
                json=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                body = await resp.json(content_type=None)

        _logger.info("FK create_payment response: status=%s body=%s", resp.status, body)

        if body.get("type") != "success":
            error_msg = body.get("message", str(body))
            raise RuntimeError(f"FreeKassa create_payment error: {error_msg}")

        location = body.get("location")
        if not location:
            raise RuntimeError(f"FreeKassa: нет URL для оплаты в ответе: {body}")

        fk_order_id = str(body.get("orderId", order_id))

        return PaymentResult(
            provider_payment_id=fk_order_id,
            payment_url=location,
            status=ProviderPaymentStatus.PENDING,
        )

    async def check_payment(
        self,
        provider_payment_id: str,
    ) -> PaymentStatusResult:
        params = {
            "shopId": int(settings.freekassa_shop_id),
            "nonce": time.time_ns(),
            "orderId": int(provider_payment_id),
        }
        params["signature"] = _sign(params, settings.freekassa_api_key)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{_API_BASE}/orders",
                json=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                body = await resp.json(content_type=None)

        if body.get("type") != "success":
            _logger.warning("FK check_payment error: %s", body)
            return PaymentStatusResult(
                provider_payment_id=provider_payment_id,
                status=ProviderPaymentStatus.PENDING,
            )

        orders = body.get("orders", [])
        if not orders:
            return PaymentStatusResult(
                provider_payment_id=provider_payment_id,
                status=ProviderPaymentStatus.PENDING,
            )

        order = orders[0]
        fk_status = order.get("status", 0)
        return PaymentStatusResult(
            provider_payment_id=provider_payment_id,
            status=_FK_STATUS_MAP.get(fk_status, ProviderPaymentStatus.PENDING),
        )
