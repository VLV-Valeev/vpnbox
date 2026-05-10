from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class VPNUser:
    username: str
    subscription_url: str
    traffic_limit_gb: float
    traffic_used_gb: float
    expires_at: Optional[datetime]
    is_active: bool
    raw: dict


@dataclass
class CreateUserParams:
    username: str
    traffic_gb: float
    expire_days: int
    remark: Optional[str] = None


class BasePanelClient(ABC):

    @abstractmethod
    async def create_user(self, params: CreateUserParams) -> VPNUser:
        ...

    @abstractmethod
    async def get_user(self, username: str) -> Optional[VPNUser]:
        ...

    @abstractmethod
    async def extend_user(self, username: str, extra_days: int, extra_gb: float = 0) -> VPNUser:
        ...

    @abstractmethod
    async def reset_traffic(self, username: str) -> None:
        ...

    @abstractmethod
    async def delete_user(self, username: str) -> None:
        ...

    @abstractmethod
    async def get_stats(self) -> dict:
        ...
