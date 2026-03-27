"""AutomationDriver - 自动化驱动抽象接口"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


DEFAULT_SCREEN_SIZE = (1080, 1920)


class ElementInfo(BaseModel):
    """UI 元素信息"""
    text: str = ""
    resource_id: str = ""
    class_name: str = ""
    content_desc: str = ""  # contentDescription 属性
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, right, bottom
    clickable: bool = False
    enabled: bool = True

    @property
    def center(self) -> tuple[int, int]:
        """元素中心坐标"""
        return (
            (self.bounds[0] + self.bounds[2]) // 2,
            (self.bounds[1] + self.bounds[3]) // 2,
        )


class AutomationDriver(ABC):
    """
    自动化驱动接口，可插拔更换。

    实现方式：
    - ADB (adb shell 命令)
    - Accessibility Service (Android 无障碍服务)
    - Appium (自动化测试框架)
    """

    @abstractmethod
    async def launch_app(self, package: str, activity: str | None = None) -> bool:
        """启动 App"""
        ...

    @abstractmethod
    async def tap(self, x: int, y: int) -> bool:
        """点击坐标"""
        ...

    @abstractmethod
    async def input_text(self, text: str) -> bool:
        """输入文本（支持中文）"""
        ...

    @abstractmethod
    async def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300,
    ) -> bool:
        """滑动"""
        ...

    @abstractmethod
    async def screenshot(self) -> bytes:
        """截图，返回 PNG 字节"""
        ...

    @abstractmethod
    async def find_element(
        self,
        text: str | None = None,
        resource_id: str | None = None,
        class_name: str | None = None,
        content_desc: str | None = None,
    ) -> list[ElementInfo]:
        """查找 UI 元素"""
        ...

    @abstractmethod
    async def press_key(self, keycode: int) -> bool:
        """按键（如 BACK=4, HOME=3, ENTER=66）"""
        ...

    async def wait_for_element(
        self,
        text: str | None = None,
        resource_id: str | None = None,
        class_name: str | None = None,
        content_desc: str | None = None,
        timeout: float = 10.0,
        interval: float = 1.0,
    ) -> ElementInfo | None:
        """轮询等待元素出现"""
        import asyncio
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            elements = await self.find_element(
                text=text, resource_id=resource_id,
                class_name=class_name, content_desc=content_desc,
            )
            if elements:
                return elements[0]
            await asyncio.sleep(interval)
        return None

    async def tap_element(self, element: ElementInfo) -> bool:
        """点击元素中心"""
        x, y = element.center
        return await self.tap(x, y)

    async def get_screen_size(self) -> tuple[int, int]:
        """返回 (width, height)，子类应覆盖"""
        return DEFAULT_SCREEN_SIZE

    async def health_check(self) -> bool:
        """检查设备连接是否存活，子类应覆盖"""
        return True

    async def app_current(self) -> dict:
        """获取当前前台 APP 信息，返回 {"package": "...", "activity": "..."}"""
        return {}

    async def app_stop(self, package: str) -> bool:
        """强制停止指定 APP"""
        return False
