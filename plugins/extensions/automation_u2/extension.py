"""AutomationU2Extension - uiautomator2 自动化扩展插件"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from core.interfaces.extension import BaseExtension

if TYPE_CHECKING:
    from fastapi import FastAPI
    from core.plugin_registry import PluginRegistry


class AutomationU2Extension(BaseExtension):
    """uiautomator2 自动化驱动扩展，提供 AutomationDriver 实例"""

    def __init__(self) -> None:
        self.driver = None
        self._device = None
        self._device_addr = ""

    async def on_load(self, app: "FastAPI", registry: "PluginRegistry") -> None:
        """初始化 u2 设备连接"""
        import uiautomator2 as u2
        from plugins.extensions.automation_u2.driver import U2AutomationDriver

        manifest = registry.get_manifest("automation_u2")
        config = getattr(manifest, "_config", {}) or {}
        self._device_addr = config.get("device_addr", "")
        connect_timeout = config.get("connect_timeout", 10)

        # 注册 API 路由
        from fastapi import APIRouter
        router = APIRouter()

        @router.get("/u2/status")
        async def u2_status():
            connected = self._device is not None
            device_info = {}
            if connected and self.driver:
                try:
                    device_info = await self.driver.get_device_info()
                except Exception:
                    connected = False
            return {
                "connected": connected,
                "device_addr": self._device_addr or "(auto)",
                "device_info": device_info,
            }

        @router.post("/u2/connect")
        async def u2_connect(addr: str = ""):
            """手动触发连接设备"""
            target = addr or self._device_addr
            try:
                self._connect_device(u2, target)
                return {"success": True, "message": f"已连接设备: {target or 'auto'}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

        app.include_router(router, prefix="/api")

        # 尝试初始连接（失败不阻塞启动）
        try:
            self._connect_device(u2, self._device_addr)
        except Exception as e:
            logger.warning(f"U2 initial connect failed (will retry on demand): {e}")

    def _connect_device(self, u2_module, addr: str = "") -> None:
        """连接设备"""
        if addr:
            self._device = u2_module.connect(addr)
        else:
            self._device = u2_module.connect()

        from plugins.extensions.automation_u2.driver import U2AutomationDriver
        self.driver = U2AutomationDriver(self._device)

        info = self._device.device_info
        logger.info(
            f"U2 device connected: {info.get('productName', 'unknown')} "
            f"(Android {info.get('sdkInt', '?')})"
        )

    async def on_unload(self) -> None:
        """清理资源"""
        self.driver = None
        self._device = None
        logger.info("U2 automation driver unloaded")
