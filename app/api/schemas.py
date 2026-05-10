"""Pydantic schemas for the REST API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator


# ──────────────── Auth ────────────────


class TelegramAuthRequest(BaseModel):
    init_data: str  # raw Telegram WebApp initData string


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    recaptcha_token: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    telegram_id: int | None
    username: str | None
    full_name: str
    email: str | None
    trial_used: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────── Plans ────────────────


class PlanResponse(BaseModel):
    id: str
    name: str
    duration_days: int
    traffic_gb: int
    price: int
    description: str
    is_trial: bool


# ──────────────── Subscription ────────────────


class SubscriptionResponse(BaseModel):
    id: int
    plan_id: str
    status: str
    subscription_url: str
    traffic_limit_gb: int
    started_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class TrialActivateResponse(BaseModel):
    ok: bool
    subscription_url: str | None = None
    expires_at: datetime | None = None
    error: str | None = None


# ──────────────── Payments ────────────────


class PaymentCreateRequest(BaseModel):
    plan_id: str
    provider: str


class PaymentCreateResponse(BaseModel):
    ok: bool
    payment_id: int | None = None
    confirmation_url: str | None = None
    error: str | None = None


class PaymentStatusResponse(BaseModel):
    ok: bool
    status: str
    subscription_url: str | None = None
    expires_at: datetime | None = None
    error: str | None = None


class PaymentHistoryItem(BaseModel):
    id: int
    plan_id: str
    amount: int
    currency: str
    provider: str
    status: str
    created_at: datetime
    paid_at: datetime | None

    model_config = {"from_attributes": True}


# ──────────────── Providers ────────────────


class ProviderResponse(BaseModel):
    provider: str
    label: str
