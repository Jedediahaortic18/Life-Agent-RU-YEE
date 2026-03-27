"""ContextBus - Agent 间通信总线"""
from __future__ import annotations

import fnmatch
import asyncio
from typing import Any, Callable


class ContextBus:
    """
    Agent 间通信总线。
    默认内存实现，作用域为单次请求。
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._subscribers: list[tuple[str, Callable]] = []
        self._lock = asyncio.Lock()

    async def write(self, agent_id: str, slot: str, data: Any) -> None:
        """写入数据到指定 slot"""
        async with self._lock:
            if agent_id not in self._store:
                self._store[agent_id] = {}
            self._store[agent_id][slot] = data

        # 通知订阅者
        key = f"{agent_id}/{slot}"
        for pattern, callback in self._subscribers:
            if fnmatch.fnmatch(key, pattern):
                try:
                    await callback(agent_id, slot, data)
                except Exception:
                    pass  # 订阅者异常不影响主流程

    async def read(self, agent_id: str, slot: str) -> Any:
        """读取指定 slot 数据"""
        return self._store.get(agent_id, {}).get(slot)

    async def subscribe(
        self,
        slot_pattern: str,
        callback: Callable[[str, str, Any], Any],
    ) -> None:
        """
        监听 slot 写入事件。
        slot_pattern: 支持通配符，如 "meal_agent/*" 或 "*/*"
        callback(agent_id, slot, data): 写入时触发
        投递保证: at-most-once
        """
        self._subscribers.append((slot_pattern, callback))

    def clear(self) -> None:
        """清空所有数据（请求结束时调用）"""
        self._store.clear()
        self._subscribers.clear()
