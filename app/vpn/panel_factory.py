from typing import Literal
from .base import BasePanelClient
from .threexui import ThreeXUIClient


PanelType = Literal["3xui"]


async def create_panel_client(
    panel_type: PanelType,
    url: str,
    username: str,
    password: str,
    **kwargs,
) -> BasePanelClient:
    """
    Фабрика: создаёт и аутентифицирует нужный клиент.

    Пример:
        client = await create_panel_client("3xui", url, user, pwd, inbound_id=2)
    """
    if panel_type == "3xui":
        inbound_id = kwargs.get("inbound_id", 1)
        server_ip = kwargs.get("server_ip")
        client = ThreeXUIClient(url, username, password, inbound_id=inbound_id, server_ip=server_ip)
    else:
        raise ValueError(f"Unknown panel type: {panel_type}")

    await client.authenticate()
    return client
