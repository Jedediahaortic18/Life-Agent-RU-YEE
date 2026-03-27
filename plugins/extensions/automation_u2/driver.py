"""U2AutomationDriver - uiautomator2 实现 AutomationDriver 接口"""
from __future__ import annotations

import asyncio
import re
from functools import partial
from typing import Any

from loguru import logger

from core.interfaces.automation import AutomationDriver, ElementInfo, DEFAULT_SCREEN_SIZE


class U2AutomationDriver(AutomationDriver):
    """基于 python-uiautomator2 的 Android 自动化驱动"""

    def __init__(self, device: Any) -> None:
        self._d = device  # uiautomator2.Device

    async def _run_sync(self, fn, *args, **kwargs):
        """在线程池中运行 u2 的同步方法"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    async def launch_app(self, package: str, activity: str | None = None) -> bool:
        try:
            if activity:
                await self._run_sync(self._d.app_start, package, activity)
            else:
                await self._run_sync(self._d.app_start, package)
            return True
        except Exception as e:
            logger.error(f"Failed to launch app {package}: {e}")
            return False

    async def tap(self, x: int, y: int) -> bool:
        try:
            await self._run_sync(self._d.click, x, y)
            return True
        except Exception as e:
            logger.error(f"Failed to tap ({x}, {y}): {e}")
            return False

    async def input_text(self, text: str) -> bool:
        """输入文本，u2 原生支持中文"""
        try:
            await self._run_sync(self._d.send_keys, text, clear=True)
            return True
        except Exception as e:
            logger.error(f"Failed to input text: {e}")
            return False

    async def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300,
    ) -> bool:
        try:
            await self._run_sync(
                self._d.swipe, x1, y1, x2, y2, duration_ms / 1000.0,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to swipe: {e}")
            return False

    async def screenshot(self) -> bytes:
        """截图，返回 PNG 字节"""
        import io
        img = await self._run_sync(self._d.screenshot)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    async def find_element(
        self,
        text: str | None = None,
        resource_id: str | None = None,
        class_name: str | None = None,
        content_desc: str | None = None,
    ) -> list[ElementInfo]:
        """查找 UI 元素"""
        try:
            kwargs: dict[str, str] = {}
            if text:
                kwargs["textContains"] = text
            if resource_id:
                kwargs["resourceIdMatches"] = f".*{re.escape(resource_id)}.*"
            if class_name:
                kwargs["classNameMatches"] = f".*{re.escape(class_name)}.*"
            if content_desc:
                kwargs["descriptionContains"] = content_desc

            if not kwargs:
                return []

            selector = self._d(**kwargs)
            count = await self._run_sync(lambda: selector.count)
            if count == 0:
                return []

            results: list[ElementInfo] = []
            for i in range(min(count, 20)):  # 最多取 20 个
                try:
                    el = selector[i]
                    info = await self._run_sync(lambda: el.info)
                    bounds = info.get("bounds", {})
                    results.append(ElementInfo(
                        text=info.get("text") or "",
                        resource_id=info.get("resourceName") or "",
                        class_name=info.get("className") or "",
                        content_desc=info.get("contentDescription") or "",
                        bounds=(
                            bounds.get("left", 0),
                            bounds.get("top", 0),
                            bounds.get("right", 0),
                            bounds.get("bottom", 0),
                        ),
                        clickable=info.get("clickable", False),
                        enabled=info.get("enabled", True),
                    ))
                except Exception:
                    break

            return results

        except Exception as e:
            logger.error(f"Failed to find element: {e}")
            return []

    async def press_key(self, keycode: int) -> bool:
        """按键（BACK=4, HOME=3, ENTER=66）"""
        try:
            key_map = {4: "back", 3: "home", 66: "enter", 84: "search"}
            key_name = key_map.get(keycode)
            if key_name:
                await self._run_sync(self._d.press, key_name)
            else:
                await self._run_sync(self._d.press, keycode)
            return True
        except Exception as e:
            logger.error(f"Failed to press key {keycode}: {e}")
            return False

    # ── u2 特有便捷方法 ──────────────────────────────

    async def click_text(self, text: str, timeout: float = 5.0) -> bool:
        """直接点击包含指定文本的元素"""
        try:
            el = self._d(textContains=text)
            existed = await self._run_sync(
                lambda: el.wait(timeout=timeout),
            )
            if existed:
                await self._run_sync(el.click)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to click text '{text}': {e}")
            return False

    async def click_resource_id(self, resource_id: str, timeout: float = 5.0) -> bool:
        """直接点击指定 resource_id 的元素"""
        try:
            el = self._d(resourceIdMatches=f".*{re.escape(resource_id)}.*")
            existed = await self._run_sync(
                lambda: el.wait(timeout=timeout),
            )
            if existed:
                await self._run_sync(el.click)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to click resource_id '{resource_id}': {e}")
            return False

    async def health_check(self) -> bool:
        """检查 u2 设备连接是否存活"""
        try:
            info = await self._run_sync(lambda: self._d.info)
            return bool(info)
        except Exception:
            return False

    async def get_screen_size(self) -> tuple[int, int]:
        """返回屏幕 (width, height)"""
        try:
            size = await self._run_sync(self._d.window_size)
            return (size[0], size[1])
        except Exception:
            return DEFAULT_SCREEN_SIZE

    async def app_current(self) -> dict:
        """获取当前前台 APP 信息"""
        try:
            info = await self._run_sync(self._d.app_current)
            return info if isinstance(info, dict) else {}
        except Exception:
            return {}

    async def app_stop(self, package: str) -> bool:
        """强制停止指定 APP"""
        try:
            await self._run_sync(self._d.app_stop, package)
            return True
        except Exception as e:
            logger.error(f"Failed to stop app {package}: {e}")
            return False

    async def get_device_info(self) -> dict:
        """获取设备信息"""
        try:
            return await self._run_sync(lambda: dict(self._d.device_info))
        except Exception:
            return {}
