"""Plans and payment providers endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import PlanResponse, ProviderResponse
from app.config import PLANS
from app.services.payments import get_enabled_providers

router = APIRouter(tags=["plans"])


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans() -> list[PlanResponse]:
    paid = [
        PlanResponse(
            id=p.id,
            name=p.name,
            duration_days=p.duration_days,
            traffic_gb=p.traffic_gb,
            price=p.price,
            description=p.description,
            is_trial=p.price == 0,
        )
        for p in PLANS.values()
        if p.price > 0
    ]
    return paid


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers() -> list[ProviderResponse]:
    providers = get_enabled_providers()
    return [
        ProviderResponse(provider=name, label=label)
        for name, label in providers.items()
    ]
