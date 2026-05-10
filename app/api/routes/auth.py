"""Authentication endpoints: Telegram initData and email/password.

Внимание: тут НЕТ `from __future__ import annotations`. slowapi-декоратор
(@limiter.limit) оборачивает хендлер и теряет модульный namespace, из-за
чего pydantic не может резолвить forward-ref (TelegramAuthRequest и др.)
и падает с PydanticUndefinedAnnotation. С real-аннотациями всё работает.
"""
import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime, timedelta

import bcrypt
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.limiter import limiter

from app.api.deps import get_current_user, get_session
from app.api.schemas import (
    EmailLoginRequest,
    EmailRegisterRequest,
    TelegramAuthRequest,
    TokenResponse,
    UserResponse,
)
from app.config import settings
from app.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ──────────────── helpers ────────────────


def _issue_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.jwt_expire_days)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _validate_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """
    Validate Telegram WebApp initData per official docs.
    Returns parsed user dict on success, raises HTTPException on failure.
    """
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=400, detail="Missing hash in initData")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    auth_date = int(parsed.get("auth_date", 0))
    if datetime.utcnow().timestamp() - auth_date > 86400:
        raise HTTPException(status_code=401, detail="initData expired")

    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(status_code=400, detail="No user in initData")

    return json.loads(user_raw)


async def _verify_recaptcha(token: str) -> None:
    if not settings.recaptcha_secret_key:
        return  # skip verification if not configured
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": settings.recaptcha_secret_key, "response": token},
            timeout=10,
        )
    data = resp.json()
    if not data.get("success"):
        raise HTTPException(status_code=400, detail="reCAPTCHA verification failed")


# ──────────────── routes ────────────────


@router.post("/telegram", response_model=TokenResponse)
@limiter.limit("20/minute")
async def auth_telegram(
    request: Request,
    body: TelegramAuthRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    tg_user = _validate_telegram_init_data(body.init_data, settings.bot_token)

    telegram_id = tg_user["id"]
    full_name = (
        tg_user.get("first_name", "") + " " + tg_user.get("last_name", "")
    ).strip() or "Unknown"
    username = tg_user.get("username")

    stmt = select(User).where(User.telegram_id == telegram_id)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user:
        user.username = username
        user.full_name = full_name
        await session.commit()
    else:
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return TokenResponse(access_token=_issue_token(user.id))


@router.post("/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: EmailRegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    await _verify_recaptcha(body.recaptcha_token)

    stmt = select(User).where(User.email == body.email)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        full_name=body.full_name,
        email=body.email,
        password_hash=_hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return TokenResponse(access_token=_issue_token(user.id))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: EmailLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    stmt = select(User).where(User.email == body.email)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not _verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return TokenResponse(access_token=_issue_token(user.id))


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
