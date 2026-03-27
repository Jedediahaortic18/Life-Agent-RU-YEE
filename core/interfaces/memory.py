"""BaseMemory - 记忆系统抽象接口"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MemoryItem(BaseModel):
    """记忆条目"""
    key: str
    value: Any
    memory_type: str  # short_term | long_term | structured
    score: float = 1.0
    created_at: datetime = datetime.now()
    metadata: dict = {}


class BaseMemory(ABC):
    """记忆系统抽象基类"""

    @abstractmethod
    async def store(self, key: str, value: Any, **metadata: Any) -> None:
        """存储记忆"""
        ...

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]:
        """语义检索记忆"""
        ...

    @abstractmethod
    async def retrieve_recent(self, n: int = 10) -> list[MemoryItem]:
        """获取最近 N 条记录"""
        ...

    @abstractmethod
    async def clear(self, scope: str = "session") -> None:
        """清除记忆"""
        ...
