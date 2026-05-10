from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Subscription, Payment, SubStatus, PayStatus


# ──────────────── User ────────────────


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_or_create(
        self, telegram_id: int, username: str | None, full_name: str,
        referrer_id: int | None = None,
    ) -> tuple[User, bool]:
        """Возвращает (user, is_new). is_new=True если пользователь создан впервые."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        user = (await self.s.execute(stmt)).scalar_one_or_none()
        if user:
            user.username = username
            user.full_name = full_name
            await self.s.commit()
            return user, False

        from app.services.client_service import get_env_admin_ids, add_admin
        role = "admin" if telegram_id in get_env_admin_ids() else "user"

        user = User(
            telegram_id=telegram_id, username=username, full_name=full_name,
            role=role,
            referrer_id=referrer_id,
        )
        self.s.add(user)
        await self.s.commit()
        await self.s.refresh(user)

        if role == "admin":
            add_admin(telegram_id)

        return user, True

    async def get_by_tg(self, telegram_id: int) -> User | None:
        stmt = select(User).where(User.telegram_id == telegram_id)
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def mark_trial_used(self, user_id: int) -> None:
        await self.s.execute(
            update(User).where(User.id == user_id).values(trial_used=True),
        )
        await self.s.commit()


# ──────────────── Subscription ────────────────


class SubRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, **kw) -> Subscription:
        sub = Subscription(**kw)
        self.s.add(sub)
        await self.s.commit()
        await self.s.refresh(sub)
        return sub

    async def get_active(self, user_id: int) -> Subscription | None:
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_([SubStatus.TRIAL, SubStatus.ACTIVE]),
            )
            .order_by(Subscription.expires_at.desc())
        )
        return (await self.s.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, sub_id: int) -> Subscription | None:
        return await self.s.get(Subscription, sub_id)

    async def get_expired(self, now: datetime) -> list[Subscription]:
        stmt = (
            select(Subscription)
            .where(
                Subscription.status.in_([SubStatus.TRIAL, SubStatus.ACTIVE]),
                Subscription.expires_at <= now,
            )
        )
        return list((await self.s.execute(stmt)).scalars().all())

    async def get_expiring_soon(
        self, from_dt: datetime, to_dt: datetime,
    ) -> list[Subscription]:
        stmt = (
            select(Subscription)
            .where(
                Subscription.status.in_([SubStatus.TRIAL, SubStatus.ACTIVE]),
                Subscription.expires_at > from_dt,
                Subscription.expires_at <= to_dt,
                Subscription.notified_expiry == False,  # noqa: E712
            )
        )
        return list((await self.s.execute(stmt)).scalars().all())

    async def set_status(self, sub_id: int, status: SubStatus) -> None:
        await self.s.execute(
            update(Subscription)
            .where(Subscription.id == sub_id)
            .values(status=status),
        )
        await self.s.commit()

    async def mark_notified(self, sub_id: int) -> None:
        await self.s.execute(
            update(Subscription)
            .where(Subscription.id == sub_id)
            .values(notified_expiry=True),
        )
        await self.s.commit()

    async def activate(self, sub_id: int, **kw) -> None:
        values = {"status": SubStatus.ACTIVE, **kw}
        await self.s.execute(
            update(Subscription).where(Subscription.id == sub_id).values(**values),
        )
        await self.s.commit()


# ──────────────── Payment ────────────────


class PaymentRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def create(self, **kw) -> Payment:
        pay = Payment(**kw)
        self.s.add(pay)
        await self.s.commit()
        await self.s.refresh(pay)
        return pay

    async def get_by_id(self, pid: int) -> Payment | None:
        return await self.s.get(Payment, pid)

    async def get_pending(self) -> list[Payment]:
        stmt = select(Payment).where(Payment.status == PayStatus.PENDING)
        return list((await self.s.execute(stmt)).scalars().all())

    async def get_pending_for_user(self, user_id: int) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.user_id == user_id, Payment.status == PayStatus.PENDING)
            .order_by(Payment.created_at.desc())
        )
        return list((await self.s.execute(stmt)).scalars().all())

    async def mark_succeeded(
        self, pid: int, provider_payment_id: str | None = None,
    ) -> None:
        values: dict = {
            "status": PayStatus.SUCCEEDED,
            "paid_at": datetime.utcnow(),
        }
        if provider_payment_id:
            values["provider_payment_id"] = provider_payment_id
        await self.s.execute(
            update(Payment).where(Payment.id == pid).values(**values),
        )
        await self.s.commit()

    async def mark_cancelled(self, pid: int) -> None:
        await self.s.execute(
            update(Payment).where(Payment.id == pid).values(status=PayStatus.CANCELLED),
        )
        await self.s.commit()

    async def mark_referral_rewarded(self, pid: int) -> None:
        await self.s.execute(
            update(Payment).where(Payment.id == pid).values(referral_reward_given=True),
        )
        await self.s.commit()


# ──────────────── Referral ────────────────


class ReferralRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get_stats(self, user_id: int) -> tuple[int, int]:
        total_stmt = (
            select(func.count())
            .select_from(User)
            .where(User.referrer_id == user_id)
        )
        total = (await self.s.execute(total_stmt)).scalar() or 0

        paid_stmt = (
            select(func.count(User.id.distinct()))
            .join(Payment, Payment.user_id == User.id)
            .where(
                User.referrer_id == user_id,
                Payment.status == PayStatus.SUCCEEDED,
            )
        )
        paid = (await self.s.execute(paid_stmt)).scalar() or 0

        return int(total), int(paid)
