import uuid
import json
import aiohttp
from datetime import datetime, timezone, timedelta
from typing import Optional

from .base import BasePanelClient, CreateUserParams, VPNUser


class ThreeXUIError(Exception):
    def __init__(self, msg: str):
        super().__init__(f"3X-UI: {msg}")


class ThreeXUIClient(BasePanelClient):
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        inbound_id: int = 1,
        server_ip: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self.inbound_id = inbound_id
        self.server_ip = server_ip or self._extract_ip_from_url(base_url)

        self._session: Optional[aiohttp.ClientSession] = None
        self._inbound_cache: Optional[dict] = None

    def _extract_ip_from_url(self, url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or parsed.netloc.split(":")[0]
        return host

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(cookie_jar=jar, connector=connector)
        return self._session

    async def authenticate(self) -> None:
        session = await self._get_session()
        url = f"{self.base_url}/login"
        payload = {"username": self._username, "password": self._password}

        async with session.post(url, json=payload, ssl=False) as resp:
            text = await resp.text()
            try:
                body = await resp.json()
            except Exception:
                raise ThreeXUIError(f"Auth failed: invalid response (not JSON): {text[:200]}")

            if body.get("success") is not True:
                msg = body.get("msg", "unknown error")
                raise ThreeXUIError(f"Auth failed: {msg}")

    async def _request(self, method: str, path: str, retry: bool = True, **kwargs) -> dict:
        session = await self._get_session()
        url = f"{self.base_url}{path}"

        async with session.request(method, url, ssl=False, **kwargs) as resp:
            text = await resp.text()

            if "<html" in text.lower():
                if retry:
                    await self.authenticate()
                    return await self._request(method, path, retry=False, **kwargs)
                raise ThreeXUIError(f"Still HTML after auth: {text[:200]}")

            try:
                body = await resp.json()
            except Exception:
                raise ThreeXUIError(f"Invalid JSON: {text[:200]}")

            if not body.get("success"):
                msg = body.get("msg", "Request failed")
                if "login" in msg.lower() or resp.status == 401:
                    if retry:
                        await self.authenticate()
                        return await self._request(method, path, retry=False, **kwargs)
                raise ThreeXUIError(msg)

            return body

    async def _get_inbound(self) -> dict:
        if self._inbound_cache:
            return self._inbound_cache

        body = await self._request(
            "GET",
            f"/panel/api/inbounds/get/{self.inbound_id}",
        )

        self._inbound_cache = body.get("obj") or body.get("data")
        return self._inbound_cache

    def _invalidate_inbound_cache(self):
        self._inbound_cache = None

    async def _get_inbound_clients(self) -> list[dict]:
        inbound = await self._get_inbound()
        settings = json.loads(inbound.get("settings", "{}"))
        return settings.get("clients", [])

    def _make_vless_link(self, client_uuid: str, inbound: dict, remark: str | None = None) -> str:
        from urllib.parse import quote

        settings = json.loads(inbound.get("settings", "{}"))
        stream = json.loads(inbound.get("streamSettings", "{}"))

        port = inbound.get("port", 443)
        network = stream.get("network", "tcp")
        security = (stream.get("security") or "none").lower()
        server_address = self.server_ip

        if security == "reality":
            reality = stream.get("realitySettings", {})
            reality_settings = reality.get("settings", {})
            public_key = reality_settings.get("publicKey", "")
            short_ids = reality.get("shortIds", [])
            server_names = reality.get("serverNames", [])

            short_id = short_ids[0] if short_ids else "ab"
            sni = server_names[0] if server_names else self._extract_ip_from_url(self.base_url)

            query_params = [
                ("type", network),
                ("encryption", "none"),
                ("security", "reality"),
                ("pbk", public_key),
                ("fp", "chrome"),
                ("sni", sni),
                ("sid", short_id),
                ("spx", quote("/", safe="")),
            ]

        elif security == "tls":
            tls = stream.get("tlsSettings", {})
            sni_value = tls.get("serverName", server_address)

            query_params = [
                ("type", network),
                ("encryption", "none"),
                ("security", "tls"),
                ("sni", sni_value),
            ]

        else:
            query_params = [
                ("type", network),
                ("encryption", "none"),
            ]

        if network == "ws":
            ws = stream.get("wsSettings", {})
            query_params.append(("path", ws.get("path", "/")))
            query_params.append(("host", ws.get("headers", {}).get("Host", server_address)))

        query_params = [(k, v) for k, v in query_params if v]
        query = "&".join([f"{k}={v}" for k, v in query_params])

        if not remark:
            remark = f"main-vb_{client_uuid}"

        return f"vless://{client_uuid}@{server_address}:{port}?{query}#{remark}"

    @staticmethod
    def _gb_to_bytes(gb: float) -> int:
        return int(gb * 1024**3) if gb > 0 else 0

    @staticmethod
    def _bytes_to_gb(b: int) -> float:
        return round(b / 1024**3, 2) if b else 0.0

    @staticmethod
    def _days_to_ms(days: int) -> int:
        if days <= 0:
            return 0
        dt = datetime.now(timezone.utc) + timedelta(days=days)
        return int(dt.timestamp() * 1000)

    def _parse_client(self, client: dict, inbound: dict, remark: str | None = None) -> VPNUser:
        expire_ms = client.get("expiryTime") or 0

        expires_at = (
            datetime.fromtimestamp(expire_ms / 1000, tz=timezone.utc)
            if expire_ms > 0
            else None
        )

        up = client.get("up", 0) or 0
        down = client.get("down", 0) or 0
        total = client.get("total", 0) or 0

        uuid_ = client.get("id", "")
        client_remark = remark or client.get("comment") or f"VPN-{uuid_[:8]}"
        sub = self._make_vless_link(uuid_, inbound, remark=client_remark)

        active = client.get("enable", True)

        if expires_at and expires_at < datetime.now(timezone.utc):
            active = False

        if total > 0 and (up + down) >= total:
            active = False

        return VPNUser(
            username=client.get("email", uuid_),
            subscription_url=sub,
            traffic_limit_gb=self._bytes_to_gb(total),
            traffic_used_gb=self._bytes_to_gb(up + down),
            expires_at=expires_at,
            is_active=active,
            raw=client,
        )

    async def create_user(self, params: CreateUserParams) -> VPNUser:
        client_uuid = str(uuid.uuid4())
        remark = params.remark or f"VPN-{client_uuid[:8]}"

        client = {
            "id": client_uuid,
            "email": params.username,
            "enable": True,
            "expiryTime": self._days_to_ms(params.expire_days),
            "total": self._gb_to_bytes(params.traffic_gb),
            "up": 0,
            "down": 0,
            "subId": params.username,
            "tgId": "",
            "limitIp": 0,
            "comment": remark,
        }

        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client]}),
        }

        await self._request("POST", "/panel/api/inbounds/addClient", json=payload)
        self._invalidate_inbound_cache()

        inbound = await self._get_inbound()
        return self._parse_client(client, inbound, remark=remark)

    async def get_user(self, username: str) -> Optional[VPNUser]:
        clients = await self._get_inbound_clients()
        client = next((c for c in clients if c.get("email") == username), None)

        if not client:
            return None

        inbound = await self._get_inbound()
        return self._parse_client(client, inbound)

    async def extend_user(self, username: str, extra_days: int, extra_gb: float = 0) -> VPNUser:
        clients = await self._get_inbound_clients()
        client = next((c for c in clients if c.get("email") == username), None)

        if not client:
            raise ThreeXUIError(f"User {username} not found")

        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        exp = client.get("expiryTime", 0) or 0

        base = exp if exp > now else now
        client["expiryTime"] = base + extra_days * 86400 * 1000

        if extra_gb > 0:
            client["total"] = client.get("total", 0) + self._gb_to_bytes(extra_gb)

        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client]}),
        }

        await self._request(
            "POST",
            f"/panel/api/inbounds/updateClient/{client['id']}",
            json=payload,
        )

        self._invalidate_inbound_cache()

        inbound = await self._get_inbound()
        return self._parse_client(client, inbound)

    async def reset_traffic(self, username: str) -> None:
        clients = await self._get_inbound_clients()
        client = next((c for c in clients if c.get("email") == username), None)

        if client:
            await self._request(
                "POST",
                f"/panel/api/inbounds/{self.inbound_id}/resetClientTraffic/{username}",
            )
            self._invalidate_inbound_cache()

    async def delete_user(self, username: str) -> None:
        clients = await self._get_inbound_clients()
        client = next((c for c in clients if c.get("email") == username), None)

        if client:
            await self._request(
                "POST",
                f"/panel/api/inbounds/{self.inbound_id}/delClient/{client['id']}",
            )
            self._invalidate_inbound_cache()

    async def get_stats(self) -> dict:
        body = await self._request("GET", "/panel/api/inbounds/list")
        inbounds = body.get("obj", [])

        if not inbounds:
            body = await self._request("GET", "/panel/api/inbounds")
            inbounds = body.get("obj", []) or []

        total_up = sum(i.get("up", 0) for i in inbounds)
        total_down = sum(i.get("down", 0) for i in inbounds)

        return {
            "inbounds_count": len(inbounds),
            "uplink_gb": self._bytes_to_gb(total_up),
            "downlink_gb": self._bytes_to_gb(total_down),
            "users_active": sum(
                len(json.loads(i.get("settings", "{}")).get("clients", []))
                for i in inbounds
            ),
            "raw": inbounds,
        }

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
