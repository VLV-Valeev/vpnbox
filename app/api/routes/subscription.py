"""Subscription management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.api.schemas import SubscriptionResponse, TrialActivateResponse
from app.db.models import User
from app.db.repo import SubRepo
from app.services.subscription_service import activate_trial_for_user

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionResponse | None)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SubscriptionResponse | None:
    sub = await SubRepo(session).get_active(current_user.id)
    if not sub:
        return None
    return SubscriptionResponse(
        id=sub.id,
        plan_id=sub.plan_id,
        status=sub.status.value,
        subscription_url=sub.subscription_url,
        traffic_limit_gb=sub.traffic_limit_gb,
        started_at=sub.started_at,
        expires_at=sub.expires_at,
    )


@router.post("/trial", response_model=TrialActivateResponse)
async def activate_trial(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TrialActivateResponse:
    result = await activate_trial_for_user(session, current_user.id)
    if not result["ok"]:
        return TrialActivateResponse(ok=False, error=result.get("error"))
    return TrialActivateResponse(
        ok=True,
        subscription_url=result["subscription_url"],
        expires_at=result["expires_at"],
    )
