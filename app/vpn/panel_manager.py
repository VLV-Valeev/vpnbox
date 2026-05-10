import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from .base import BasePanelClient, CreateUserParams, VPNUser
from .panel_factory import create_panel_client, PanelType

_logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    id: int
    name: str
    panel_type: PanelType
    url: str
    username: str
    password: str
    country: str = "🌍"
    inbound_id: int = 1
    max_users: int = 500
    is_active: bool = True


@dataclass
class ServerState:
    config: ServerConfig
    client: Optional[BasePanelClient] = None
    users_count: int = 0
    is_healthy: bool = True
    last_error: Optional[str] = None


class PanelManager:
    def __init__(self, configs: list[ServerConfig]):
        self._configs = configs
        self._states: dict[int, ServerState] = {}

    async def start(self) -> None:
        tasks = [self._init_server(cfg) for cfg in self._configs]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _init_server(self, cfg: ServerConfig) -> None:
        state = ServerState(config=cfg)
        self._states[cfg.id] = state
        try:
            from urllib.parse import urlparse
            server_host = urlparse(cfg.url).hostname or cfg.url.split(":")[0]

            client = await create_panel_client(
                cfg.panel_type, cfg.url, cfg.username, cfg.password,
                inbound_id=cfg.inbound_id,
                server_ip=server_host,
            )
            state.client = client
            stats = await client.get_stats()
            state.users_count = stats.get("users_active", 0)
            state.is_healthy = True
        except Exception as e:
            state.is_healthy = False
            state.last_error = str(e)
            _logger.error("VPN server %s (%s) init failed: %s", cfg.id, cfg.url, e)

    def get_best_server(self) -> Optional[ServerState]:
        healthy = [
            s for s in self._states.values()
            if s.is_healthy and s.config.is_active and s.users_count < s.config.max_users
        ]
        if not healthy:
            return None
        return min(healthy, key=lambda s: s.users_count / s.config.max_users)

    def get_server(self, server_id: int) -> Optional[ServerState]:
        return self._states.get(server_id)

    async def create_user(self, params: CreateUserParams, server_id: Optional[int] = None) -> tuple[VPNUser, int]:
        if server_id:
            state = self.get_server(server_id)
            if not state or not state.is_healthy:
                raise RuntimeError(f"Server {server_id} unavailable")
        else:
            state = self.get_best_server()
            if not state:
                raise RuntimeError("No available VPN servers")

        user = await state.client.create_user(params)
        state.users_count += 1
        return user, state.config.id

    async def get_user(self, username: str, server_id: int) -> Optional[VPNUser]:
        state = self.get_server(server_id)
        if not state or not state.client:
            return None
        return await state.client.get_user(username)

    async def extend_user(self, username: str, server_id: int, extra_days: int, extra_gb: float = 0) -> VPNUser:
        state = self.get_server(server_id)
        if not state or not state.client:
            raise RuntimeError(f"Server {server_id} unavailable")
        return await state.client.extend_user(username, extra_days, extra_gb)

    async def delete_user(self, username: str, server_id: int) -> None:
        state = self.get_server(server_id)
        if state and state.client:
            await state.client.delete_user(username)
            state.users_count = max(0, state.users_count - 1)

    async def healthcheck(self) -> dict:
        results = {}
        for server_id, state in self._states.items():
            try:
                if not state.client:
                    await self._init_server(state.config)
                else:
                    stats = await state.client.get_stats()
                    state.users_count = stats.get("users_active", state.users_count)
                    state.is_healthy = True
                    state.last_error = None
                results[server_id] = {"healthy": True, "users": state.users_count}
            except Exception as e:
                state.is_healthy = False
                state.last_error = str(e)
                results[server_id] = {"healthy": False, "error": str(e)}
        return results

    def servers_info(self) -> list[dict]:
        return [
            {
                "id": s.config.id,
                "name": s.config.name,
                "country": s.config.country,
                "panel_type": s.config.panel_type,
                "users": s.users_count,
                "max_users": s.config.max_users,
                "healthy": s.is_healthy,
                "load_pct": round(s.users_count / s.config.max_users * 100, 1),
                "error": s.last_error,
            }
            for s in self._states.values()
        ]

    async def close(self) -> None:
        for state in self._states.values():
            if state.client:
                await state.client.close()
