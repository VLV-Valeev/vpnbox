"""Payment endpoints: create invoice, check status, history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.api.schemas import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentHistoryItem,
    PaymentStatusResponse,
)
from app.db.models import Payment, PayStatus, User
from app.services.subscription_service import (
    check_and_activate_for_user,
    create_payment_for_user,
)

router = APIRouter(prefix="/payment", tags=["payment"])


@router.post("/create", response_model=PaymentCreateResponse)
async def create_payment(
    body: PaymentCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PaymentCreateResponse:
    result = await create_payment_for_user(
        session,
        user_id=current_user.id,
        plan_id=body.plan_id,
        provider=body.provider,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error", "payment_error"))
    return PaymentCreateResponse(
        ok=True,
        payment_id=result["payment_id"],
        confirmation_url=result["confirmation_url"],
    )


@router.get("/{payment_id}/status", response_model=PaymentStatusResponse)
async def check_payment_status(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PaymentStatusResponse:
    result = await check_and_activate_for_user(session, payment_id, current_user.id)
    return PaymentStatusResponse(
        ok=result["ok"],
        status=result.get("status", "pending"),
        subscription_url=result.get("subscription_url"),
        expires_at=result.get("expires_at"),
        error=result.get("error"),
    )


@router.post("/{payment_id}/cancel")
async def cancel_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = select(Payment).where(
        Payment.id == payment_id,
        Payment.user_id == current_user.id,
        Payment.status == PayStatus.PENDING,
    )
    payment = (await session.execute(stmt)).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="payment_not_found")
    payment.status = PayStatus.CANCELLED
    await session.commit()
    return {"ok": True}


@router.get("/history", response_model=list[PaymentHistoryItem])
async def payment_history(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[PaymentHistoryItem]:
    stmt = (
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .limit(50)
    )
    payments = list((await session.execute(stmt)).scalars().all())
    return [
        PaymentHistoryItem(
            id=p.id,
            plan_id=p.plan_id,
            amount=p.amount,
            currency=p.currency,
            provider=p.provider,
            status=p.status.value,
            created_at=p.created_at,
            paid_at=p.paid_at,
        )
        for p in payments
    ]
