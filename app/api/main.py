"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.limiter import limiter
from app.api.routes import auth, payment, plans, subscription
from app.config import settings
from app.db.engine import async_session, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Схема БД управляется Alembic'ом (`bash migrate.sh`).
    # API только подключается к уже существующей БД.
    async with async_session() as session:
        from app.services.client_service import init_client
        await init_client(session, settings.bot_token)

    from app.services import vpn_service
    try:
        await vpn_service.get_manager()
    except Exception:
        pass

    yield

    from app.services import vpn_service as vs
    await vs.close()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="VPNBox API",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    origins = [o.strip() for o in settings.api_cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api")
    app.include_router(plans.router, prefix="/api")
    app.include_router(subscription.router, prefix="/api")
    app.include_router(payment.router, prefix="/api")

    return app


app = create_app()
