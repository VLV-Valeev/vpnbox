# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is VPNBox

Multi-tenant SaaS platform for selling VPN subscriptions through Telegram. The bot handles payments, activates accounts on 3X-UI VPN panels, and provides a Next.js web dashboard. All branding, plans, and payment provider credentials are stored per-client in the database (not hardcoded).

## Commands

### Python backend

```bash
# Activate venv (Linux)
source venv/bin/activate

# Run bot
python run_bot.py

# Run API server (port 8000)
python run_api.py

# Run Celery worker + beat scheduler
celery -A app.worker.celery_app worker --loglevel=info --beat

# Database migrations
bash migrate.sh
```

### Web frontend

```bash
cd web
npm run dev          # dev server on port 3000
npm run build        # production build
npm run type-check   # TypeScript check
npm run lint         # ESLint
```

### PM2 (production)

```bash
pm2 start bot-ecosystem.config.js   # bot + worker + beat
pm2 start web-ecosystem.config.js   # API + web
pm2 logs vpnbox-bot
pm2 status
```

### Database

```bash
# psql direct
psql postgresql://vpnbox:PASSWORD@localhost:5432/vpnbox

# Backup / restore
pg_dump <url> | gzip > backup.sql.gz
gunzip -c backup.sql.gz | psql <url>
```

## Architecture

### Process boundaries

- **run_bot.py** — Aiogram 3 Telegram bot (long polling)
- **run_api.py** — FastAPI REST API (uvicorn, port 8000), used by Next.js web app
- **celery worker** — background tasks (payment checking, subscription expiry, VPN health)
- **web/** — Next.js 15 frontend served on port 3000; authenticates users via Telegram WebApp init_data or JWT

All four share the same PostgreSQL DB and Redis instance.

### Key layers

| Layer | Path | Role |
|---|---|---|
| Bot handlers | `app/bot/handlers/` | Telegram command/callback routing |
| API routes | `app/api/routes/` | REST endpoints for the web app |
| Services | `app/services/` | Business logic (subscriptions, VPN, payments) |
| Repositories | `app/db/repo.py` | All DB queries, repository pattern |
| Models | `app/db/models.py` | SQLAlchemy ORM |
| VPN layer | `app/vpn/` | 3X-UI panel clients + load-balanced PanelManager |
| Payments | `app/services/payments/` | Pluggable providers behind `BasePaymentProvider` |
| Tasks | `app/worker/tasks.py` | Celery beat tasks |
| Config | `app/config.py` | Pydantic Settings — all env vars live here |

### Multi-tenancy

Each bot deployment has one `Client` row in the DB that stores service name, VPN app deep links, enabled payment providers (with credentials as JSON), and terms URLs. Plans are in `ClientPlan`. This means the same codebase can serve multiple brands with zero code changes.

### Payment flow

1. User selects plan → `payment factory` instantiates the provider
2. `provider.create_payment()` → store as PENDING in DB
3. Fast async polling (3 s interval, 15 min window) for immediate UX feedback
4. Celery beat checks every 30 s as reliability fallback
5. On `SUCCEEDED` → `subscription_service.activate_subscription()` → creates VPN account via `PanelManager`

### VPN server management

`PanelManager` (`app/vpn/panel_manager.py`) is a singleton that holds clients for all `Server` rows. It load-balances new accounts across panels by current user count. Celery pings panels every 5 minutes to update health status.

## Environment

Copy `.env.example` to `.env`. Critical vars:

- `BOT_TOKEN`, `ADMIN_ID` — Telegram
- `DATABASE_URL` — `postgresql+asyncpg://...`
- `REDIS_URL`
- `VPN_SERVERS` — JSON array of 3X-UI panel configs
- `JWT_SECRET` — for web API auth
- Payment provider credentials (`YOOKASSA_*`, `FREEKASSA_*`, `PLATEGA_*`, `CRYPTOCLOUD_*`)

## Adding a payment provider

1. Create `app/services/payments/<name>_provider.py` implementing `BasePaymentProvider` (`app/services/payments/base.py`)
2. Register it in `app/services/payments/factory.py`
3. Add provider credentials to `app/config.py` and `.env.example`
4. Add the provider slug to `ClientPaymentProvider` records in DB

## Adding a VPN panel type

1. Create `app/vpn/<type>.py` implementing `BasePanelClient` (`app/vpn/base.py`)
2. Register it in `app/vpn/panel_factory.py`

## Migrations

`migrate.sh` auto-generates an Alembic migration from model changes and applies it (with a DB backup first). For manual control:

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```
