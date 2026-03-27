"""AutomationAdbExtension - ADB 自动化扩展插件"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from core.interfaces.extension import BaseExtension
from plugins.extensions.automation_adb.adb_client import AdbClient
from plugins.extensions.automation_adb.driver import AdbAutomationDriver

if TYPE_CHECKING:
    from fastapi import FastAPI
    from core.plugin_registry import PluginRegistry


class AutomationAdbExtension(BaseExtension):
    """ADB 自动化驱动扩展，提供 AutomationDriver 实例"""

    def __init__(self) -> None:
        self.driver: AdbAutomationDriver | None = None
        self._adb_client: AdbClient | None = None

    async def on_load(self, app: "FastAPI", registry: "PluginRegistry") -> None:
        """初始化 ADB 客户端和驱动"""
        # 从 plugin_config 读取配置
        manifest = registry.get_manifest("automation_adb")
        config = {}
        if manifest:
            config = getattr(manifest, "_config", {}) or {}

        device_serial = config.get("device_serial", "")
        adb_path = config.get("adb_path", "adb")
        timeout = config.get("command_timeout", 10)

        self._adb_client = AdbClient(
            device_serial=device_serial,
            adb_path=adb_path,
            timeout=timeout,
        )
        self.driver = AdbAutomationDriver(self._adb_client)

        # 注册健康检查路由
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/adb/status")
        async def adb_status():
            connected = await self._adb_client.is_connected()
            devices = []
            if connected:
                try:
                    devices = [
                        {"serial": d.serial, "state": d.state, "model": d.model}
                        for d in await self._adb_client.devices()
                    ]
                except Exception:
                    pass
            return {
                "connected": connected,
                "devices": devices,
                "config": {
                    "device_serial": device_serial or "(auto)",
                    "adb_path": adb_path,
                },
            }

        app.include_router(router, prefix="/api")
        logger.info(f"ADB automation driver initialized (serial={device_serial or 'auto'})")

    async def on_unload(self) -> None:
        """清理资源"""
        self.driver = None
        self._adb_client = None
        logger.info("ADB automation driver unloaded")
