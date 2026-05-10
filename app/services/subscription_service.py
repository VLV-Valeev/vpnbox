"""Бизнес-логика управления подписками."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PLANS
from app.db.models import User, SubStatus
from app.db.repo import UserRepo, SubRepo, PaymentRepo
from app.services import vpn_service
from app.services.payments import get_provider, ProviderPaymentStatus
from app.services.client_service import get_client

logger = logging.getLogger(__name__)


def _vpn_username(telegram_id: int) -> str:
    return f"vb_{telegram_id}"


def _vpn_username_for_user(user) -> str:
    """Генерирует vpn_username для любого юзера (Telegram или web)."""
    if user.telegram_id:
        return f"vb_{user.telegram_id}"
    return f"vb_web_{user.id}"


async def activate_trial(session: AsyncSession, telegram_id: int) -> dict:
    plan = PLANS.get("trial")
    if not plan:
        return {"ok": False, "error": "trial_disabled"}

    user_repo = UserRepo(session)
    sub_repo = SubRepo(session)

    user = await user_repo.get_by_tg(telegram_id)
    if not user:
        return {"ok": False, "error": "user_not_found"}
    if user.trial_used:
        return {"ok": False, "error": "trial_already_used"}

    existing = await sub_repo.get_active(user.id)
    if existing:
        return {"ok": False, "error": "has_active_sub"}

    vpn_username = _vpn_username(telegram_id)
    try:
        vpn_user, server_id = await vpn_service.create_vpn_user(
            vpn_username, plan.traffic_gb, plan.duration_days,
        )
    except Exception:
        logger.exception("create_vpn_user failed")
        return {"ok": False, "error": "no_servers"}

    now = datetime.utcnow()
    sub = await sub_repo.create(
        user_id=user.id,
        plan_id=plan.id,
        vpn_username=vpn_username,
        server_id=server_id,
        subscription_url=vpn_user.subscription_url,
        status=SubStatus.TRIAL,
        traffic_limit_gb=plan.traffic_gb,
        started_at=now,
        expires_at=now + timedelta(days=plan.duration_days),
    )
    await user_repo.mark_trial_used(user.id)

    return {
        "ok": True,
        "subscription_url": vpn_user.subscription_url,
        "expires_at": sub.expires_at,
        "plan": plan,
    }


async def create_payment_for_plan(
    session: AsyncSession,
    telegram_id: int,
    plan_id: str,
    provider: str = "yookassa",
) -> dict:
    plan = PLANS.get(plan_id)
    if not plan or plan.price == 0:
        return {"ok": False, "error": "invalid_plan"}

    user_repo = UserRepo(session)
    pay_repo = PaymentRepo(session)

    user = await user_repo.get_by_tg(telegram_id)
    if not user:
        return {"ok": False, "error": "user_not_found"}

    try:
        payment_provider = get_provider(provider)
        result = await payment_provider.create_payment(
            amount=plan.price,
            order_id=f"{user.id}_{plan_id}_{int(datetime.utcnow().timestamp() * 1000)}",
            description=f"{get_client().service_name} — {plan.name}",
            metadata={"user_id": str(user.id), "plan_id": plan_id},
        )
    except Exception:
        logger.exception("create_payment_for_plan: provider=%s plan=%s user=%s", provider, plan_id, user.id)
        return {"ok": False, "error": "payment_provider_error"}

    db_payment = await pay_repo.create(
        user_id=user.id,
        plan_id=plan_id,
        amount=plan.price,
        provider=provider,
        provider_payment_id=result.provider_payment_id,
        confirmation_url=result.payment_url,
    )

    return {
        "ok": True,
        "confirmation_url": result.payment_url,
        "payment_id": db_payment.id,
    }


async def check_and_activate(session: AsyncSession, payment_id: int) -> dict:
    # Advisory lock per-payment, чтобы бот-поллинг и celery-beat не активировали
    # один и тот же платёж одновременно. Лок держится до конца транзакции.
    got_lock = (await session.execute(
        text("SELECT pg_try_advisory_xact_lock(:key)"),
        {"key": payment_id},
    )).scalar()
    if not got_lock:
        return {"ok": False, "status": "pending", "error": "locked"}

    pay_repo = PaymentRepo(session)
    sub_repo = SubRepo(session)

    payment = await pay_repo.get_by_id(payment_id)
    if not payment:
        return {"ok": False, "status": "not_found", "error": "payment_not_found"}

    if payment.status.value == "succeeded":
        sub = await sub_repo.get_active(payment.user_id)
        if sub:
            return {
                "ok": True,
                "status": "succeeded",
                "subscription_url": sub.subscription_url,
                "expires_at": sub.expires_at,
            }
        return {"ok": True, "status": "succeeded"}

    if not payment.provider_payment_id:
        return {"ok": False, "status": "pending", "error": "no_provider_id"}

    try:
        payment_provider = get_provider(payment.provider)
        provider_status = await payment_provider.check_payment(payment.provider_payment_id)
    except Exception:
        return {"ok": False, "status": "pending", "error": "check_failed"}

    if provider_status.status in (ProviderPaymentStatus.CANCELLED, ProviderPaymentStatus.FAILED):
        await pay_repo.mark_cancelled(payment.id)
        return {"ok": False, "status": "cancelled", "error": "payment_cancelled"}

    if provider_status.status != ProviderPaymentStatus.SUCCEEDED:
        return {"ok": False, "status": "pending"}

    await pay_repo.mark_succeeded(payment.id, provider_status.provider_payment_id)
    return await _activate_paid_subscription(session, payment)


async def _activate_paid_subscription(
    session: AsyncSession, payment,
) -> dict:
    plan = PLANS.get(payment.plan_id)
    if not plan:
        return {"ok": False, "status": "error", "error": "unknown_plan"}

    sub_repo = SubRepo(session)
    user_repo = UserRepo(session)

    user = await session.get(User, payment.user_id)
    if not user:
        return {"ok": False, "status": "error", "error": "user_not_found"}

    existing = await sub_repo.get_active(user.id)

    if existing:
        new_expiry = existing.expires_at + timedelta(days=plan.duration_days)
        extra_traffic = plan.traffic_gb
        await sub_repo.activate(
            existing.id,
            expires_at=new_expiry,
            traffic_limit_gb=existing.traffic_limit_gb + extra_traffic,
            plan_id=plan.id,
        )
        try:
            await vpn_service.extend_vpn_user(
                existing.vpn_username,
                existing.server_id,
                plan.duration_days,
                plan.traffic_gb,
            )
        except Exception:
            logger.exception(
                "extend_vpn_user failed for user %s sub %s", user.id, existing.id
            )

        await _reward_referrer(session, payment)

        return {
            "ok": True,
            "status": "succeeded",
            "subscription_url": existing.subscription_url,
            "expires_at": new_expiry,
        }

    vpn_username = _vpn_username(user.telegram_id)
    try:
        vpn_user, server_id = await vpn_service.create_vpn_user(
            vpn_username, plan.traffic_gb, plan.duration_days,
        )
    except Exception:
        logger.exception("create_vpn_user failed for user %s plan %s", user.id, plan.id)
        return {"ok": False, "status": "error", "error": "no_servers"}

    now = datetime.utcnow()
    sub = await sub_repo.create(
        user_id=user.id,
        plan_id=plan.id,
        vpn_username=vpn_username,
        server_id=server_id,
        subscription_url=vpn_user.subscription_url,
        status=SubStatus.ACTIVE,
        traffic_limit_gb=plan.traffic_gb,
        started_at=now,
        expires_at=now + timedelta(days=plan.duration_days),
    )

    payment.subscription_id = sub.id
    await session.commit()

    await _reward_referrer(session, payment)

    return {
        "ok": True,
        "status": "succeeded",
        "subscription_url": vpn_user.subscription_url,
        "expires_at": sub.expires_at,
    }


async def grant_plan(session: AsyncSession, telegram_id: int, plan_id: str) -> dict:
    plan = PLANS.get(plan_id)
    if not plan:
        return {"ok": False, "error": "unknown_plan"}

    user_repo = UserRepo(session)
    sub_repo = SubRepo(session)

    user = await user_repo.get_by_tg(telegram_id)
    if not user:
        return {"ok": False, "error": "user_not_found"}

    existing = await sub_repo.get_active(user.id)

    if existing:
        new_expiry = existing.expires_at + timedelta(days=plan.duration_days)
        new_traffic = (existing.traffic_limit_gb + plan.traffic_gb) if plan.traffic_gb else 0
        await sub_repo.activate(
            existing.id,
            expires_at=new_expiry,
            traffic_limit_gb=new_traffic,
            plan_id=plan.id,
        )
        try:
            await vpn_service.extend_vpn_user(
                existing.vpn_username,
                existing.server_id,
                plan.duration_days,
                plan.traffic_gb,
            )
        except Exception:
            pass

        return {
            "ok": True,
            "subscription_url": existing.subscription_url,
            "expires_at": new_expiry,
            "action": "extended",
        }

    vpn_username = _vpn_username(telegram_id)
    try:
        vpn_user, server_id = await vpn_service.create_vpn_user(
            vpn_username, plan.traffic_gb, plan.duration_days,
        )
    except Exception:
        logger.exception("create_vpn_user failed")
        return {"ok": False, "error": "no_servers"}

    now = datetime.utcnow()
    status = SubStatus.TRIAL if plan.price == 0 else SubStatus.ACTIVE
    sub = await sub_repo.create(
        user_id=user.id,
        plan_id=plan.id,
        vpn_username=vpn_username,
        server_id=server_id,
        subscription_url=vpn_user.subscription_url,
        status=status,
        traffic_limit_gb=plan.traffic_gb,
        started_at=now,
        expires_at=now + timedelta(days=plan.duration_days),
    )

    if plan.price == 0:
        await user_repo.mark_trial_used(user.id)

    return {
        "ok": True,
        "subscription_url": vpn_user.subscription_url,
        "expires_at": sub.expires_at,
        "action": "created",
    }


async def _reward_referrer(session: AsyncSession, payment) -> None:
    if payment.referral_reward_given:
        return

    user = await session.get(User, payment.user_id)
    if not user or not user.referrer_id:
        return

    referrer = await session.get(User, user.referrer_id)
    if not referrer:
        return

    sub_repo = SubRepo(session)
    referrer_sub = await sub_repo.get_active(referrer.id)

    reward_days = get_client().referral_reward_days

    if referrer_sub:
        new_expiry = referrer_sub.expires_at + timedelta(days=reward_days)
        await sub_repo.activate(referrer_sub.id, expires_at=new_expiry)
        try:
            await vpn_service.extend_vpn_user(
                referrer_sub.vpn_username, referrer_sub.server_id, reward_days, 0,
            )
        except Exception:
            pass

    await PaymentRepo(session).mark_referral_rewarded(payment.id)

    await _notify_referrer(
        referrer_tg_id=referrer.telegram_id,
        referred_name=user.full_name,
        reward_days=reward_days,
        has_sub=referrer_sub is not None,
    )


async def _notify_referrer(
    referrer_tg_id: int,
    referred_name: str,
    reward_days: int,
    has_sub: bool,
) -> None:
    from aiogram import Bot
    from app.config import settings

    if has_sub:
        body = (
            f"🎉 <b>Реферальный бонус!</b>\n\n"
            f"Ваш друг <b>{referred_name}</b> оформил платную подписку.\n"
            f"<b>+{reward_days} дн.</b> добавлено к вашей подписке! 🚀"
        )
    else:
        body = (
            f"🎉 <b>Реферальный бонус!</b>\n\n"
            f"Ваш друг <b>{referred_name}</b> оформил платную подписку.\n"
            f"Бонус <b>+{reward_days} дн.</b> будет начислен, когда вы оформите свою подписку."
        )

    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_message(referrer_tg_id, body, parse_mode="HTML")
    except Exception:
        pass
    finally:
        await bot.session.close()


async def expire_subscription(session: AsyncSession, sub_id: int) -> None:
    sub_repo = SubRepo(session)
    sub = await sub_repo.get_by_id(sub_id)
    if not sub:
        return
    await sub_repo.set_status(sub_id, SubStatus.EXPIRED)
    await vpn_service.delete_vpn_user(sub.vpn_username, sub.server_id)


async def activate_trial_for_user(session: AsyncSession, user_id: int) -> dict:
    from sqlalchemy import select as sa_select
    from app.db.models import User as UserModel
    user = (await session.execute(sa_select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
    if not user:
        return {"ok": False, "error": "user_not_found"}

    plan = PLANS.get("trial")
    if not plan:
        return {"ok": False, "error": "trial_disabled"}

    sub_repo = SubRepo(session)
    user_repo = UserRepo(session)

    if user.trial_used:
        return {"ok": False, "error": "trial_already_used"}

    existing = await sub_repo.get_active(user.id)
    if existing:
        return {"ok": False, "error": "has_active_sub"}

    vpn_username = _vpn_username_for_user(user)
    try:
        vpn_user, server_id = await vpn_service.create_vpn_user(
            vpn_username, plan.traffic_gb, plan.duration_days,
        )
    except Exception:
        logger.exception("create_vpn_user failed")
        return {"ok": False, "error": "no_servers"}

    now = datetime.utcnow()
    sub = await sub_repo.create(
        user_id=user.id,
        plan_id=plan.id,
        vpn_username=vpn_username,
        server_id=server_id,
        subscription_url=vpn_user.subscription_url,
        status=SubStatus.TRIAL,
        traffic_limit_gb=plan.traffic_gb,
        started_at=now,
        expires_at=now + timedelta(days=plan.duration_days),
    )
    await user_repo.mark_trial_used(user.id)

    return {
        "ok": True,
        "subscription_url": vpn_user.subscription_url,
        "expires_at": sub.expires_at,
        "plan": plan,
    }


async def create_payment_for_user(
    session: AsyncSession,
    user_id: int,
    plan_id: str,
    provider: str = "yookassa",
) -> dict:
    from sqlalchemy import select as sa_select
    from app.db.models import User as UserModel
    user = (await session.execute(sa_select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
    if not user:
        return {"ok": False, "error": "user_not_found"}

    plan = PLANS.get(plan_id)
    if not plan or plan.price == 0:
        return {"ok": False, "error": "invalid_plan"}

    pay_repo = PaymentRepo(session)

    try:
        payment_provider = get_provider(provider)
        result = await payment_provider.create_payment(
            amount=plan.price,
            order_id=f"{user.id}_{plan_id}_{int(datetime.utcnow().timestamp() * 1000)}",
            description=f"{get_client().service_name} — {plan.name}",
            metadata={"user_id": str(user.id), "plan_id": plan_id},
        )
    except Exception:
        logger.exception("create_payment_for_user: provider=%s plan=%s user=%s", provider, plan_id, user.id)
        return {"ok": False, "error": "payment_provider_error"}

    db_payment = await pay_repo.create(
        user_id=user.id,
        plan_id=plan_id,
        amount=plan.price,
        provider=provider,
        provider_payment_id=result.provider_payment_id,
        confirmation_url=result.payment_url,
    )

    return {
        "ok": True,
        "confirmation_url": result.payment_url,
        "payment_id": db_payment.id,
    }


async def check_and_activate_for_user(
    session: AsyncSession,
    payment_id: int,
    user_id: int,
) -> dict:
    pay_repo = PaymentRepo(session)
    payment = await pay_repo.get_by_id(payment_id)
    if not payment:
        return {"ok": False, "status": "not_found", "error": "payment_not_found"}
    if payment.user_id != user_id:
        return {"ok": False, "status": "forbidden", "error": "payment_not_found"}
    return await check_and_activate(session, payment_id)
