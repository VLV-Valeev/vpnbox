from __future__ import annotations

import logging
from sqlalchemy import text

from app.vpn import PanelManager, ServerConfig, CreateUserParams, VPNUser
from app.config import settings

_logger = logging.getLogger(__name__)

_manager: PanelManager | None = None


async def _load_configs_from_db() -> list[ServerConfig]:
    from app.db.engine import async_session
    from app.db.models import Server
    from sqlalchemy import select

    async with async_session() as session:
        total = (await session.execute(select(Server))).scalars().all()
        active = [s for s in total if s.is_active]

    if not active:
        return []

    return [
        ServerConfig(
            id=s.id,
            name=s.name,
            panel_type=s.panel_type,
            url=s.url,
            username=s.username,
            password=s.password,
            country=s.country,
            inbound_id=s.inbound_id,
            max_users=s.max_users,
            is_active=s.is_active,
        )
        for s in active
    ]


async def _import_env_servers(raw: list[dict]) -> list[ServerConfig]:
    from app.db.engine import async_session

    try:
        async with async_session() as session:
            for s in raw:
                sid = s.get("id")
                if sid is None:
                    continue
                _logger.info("Importing VPN server id=%s url=%s", sid, s.get("url"))
                params = {
                    "id":         sid,
                    "name":       s.get("name", f"Server {sid}"),
                    "panel_type": s.get("panel_type", "3xui"),
                    "url":        s.get("url", ""),
                    "username":   s.get("username", ""),
                    "password":   s.get("password", ""),
                    "country":    s.get("country", "🌍"),
                    "inbound_id": int(s.get("inbound_id", 1)),
                    "max_users":  int(s.get("max_users", 500)),
                    "is_active":  True,
                }
                await session.execute(
                    text(
                        "INSERT INTO servers (id, name, panel_type, url, username, password, "
                        "country, inbound_id, max_users, is_active, created_at) "
                        "VALUES (:id, :name, :panel_type, :url, :username, :password, "
                        ":country, :inbound_id, :max_users, :is_active, NOW()) "
                        "ON CONFLICT (id) DO UPDATE SET "
                        "name = EXCLUDED.name, panel_type = EXCLUDED.panel_type, "
                        "url = EXCLUDED.url, username = EXCLUDED.username, "
                        "password = EXCLUDED.password, country = EXCLUDED.country, "
                        "inbound_id = EXCLUDED.inbound_id, max_users = EXCLUDED.max_users, "
                        "is_active = TRUE"
                    ),
                    params,
                )
            await session.execute(text(
                "SELECT setval('servers_id_seq', GREATEST((SELECT COALESCE(MAX(id),0) FROM servers), 1))"
            ))
            await session.commit()
    except Exception as e:
        _logger.error("Failed to import VPN servers from .env into DB: %s", e)

    return await _load_configs_from_db()


async def _build_manager() -> PanelManager:
    # Всегда синхронизируем VPN_SERVERS из .env в БД (upsert)
    try:
        raw = settings.get_vpn_servers()
    except Exception:
        raw = []

    if raw:
        configs = await _import_env_servers(raw)
    else:
        configs = await _load_configs_from_db()

    manager = PanelManager(configs)
    await manager.start()
    return manager


async def get_manager() -> PanelManager:
    global _manager
    if _manager is None:
        _manager = await _build_manager()
    elif _manager.get_best_server() is None:
        # Все серверы недоступны — пробуем переподключиться
        _logger.warning("All VPN servers unhealthy, running healthcheck...")
        await _manager.healthcheck()
    return _manager


async def reload_manager() -> PanelManager:
    global _manager
    if _manager:
        await _manager.close()
        _manager = None
    _manager = await _build_manager()
    return _manager


async def create_vpn_user(
    username: str, traffic_gb: int, expire_days: int, remark: str | None = None,
) -> tuple[VPNUser, int]:
    manager = await get_manager()
    params = CreateUserParams(
        username=username, traffic_gb=traffic_gb, expire_days=expire_days, remark=remark,
    )
    return await manager.create_user(params)


async def get_vpn_user(username: str, server_id: int) -> VPNUser | None:
    manager = await get_manager()
    try:
        return await manager.get_user(username, server_id)
    except Exception:
        return None


async def extend_vpn_user(
    username: str, server_id: int, extra_days: int, extra_gb: float = 0,
) -> None:
    manager = await get_manager()
    await manager.extend_user(username, server_id, extra_days, extra_gb)


async def delete_vpn_user(username: str, server_id: int) -> None:
    manager = await get_manager()
    try:
        await manager.delete_user(username, server_id)
    except Exception:
        pass


async def healthcheck() -> dict:
    manager = await get_manager()
    return await manager.healthcheck()


async def close() -> None:
    global _manager
    if _manager:
        await _manager.close()
        _manager = None
