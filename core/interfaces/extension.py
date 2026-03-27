"""BaseExtension - 扩展插件抽象接口"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from core.plugin_registry import PluginRegistry


class BaseExtension(ABC):
    """扩展插件基类，用于注册路由、WebSocket 等。加载后需重启才能卸载。"""

    @abstractmethod
    async def on_load(self, app: "FastAPI", registry: "PluginRegistry") -> None:
        """加载时挂载路由、WebSocket 等"""
        ...

    @abstractmethod
    async def on_unload(self) -> None:
        """卸载时清理资源"""
        ...
