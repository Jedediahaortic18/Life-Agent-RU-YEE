"""DeliveryAddressMemory - 收货地址管理插件"""
from __future__ import annotations

from typing import Any

from core.interfaces.memory import BaseMemory, MemoryItem


class DeliveryAddressMemory(BaseMemory):
    """收货地址管理，实际数据读写由 tools 完成，此类仅作为插件入口"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def store(self, key: str, value: Any, **metadata: Any) -> None:
        pass

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        return []

    async def retrieve_recent(self, n: int = 10) -> list[MemoryItem]:
        return []

    async def clear(self, scope: str = "session") -> None:
        pass
