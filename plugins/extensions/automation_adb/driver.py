"""AdbAutomationDriver - ADB 实现 AutomationDriver 接口"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from loguru import logger

from core.interfaces.automation import AutomationDriver, ElementInfo
from plugins.extensions.automation_adb.adb_client import AdbClient, AdbError


# Android 按键常量
KEY_BACK = 4
KEY_HOME = 3
KEY_ENTER = 66
KEY_SEARCH = 84
KEY_DEL = 67


class AdbAutomationDriver(AutomationDriver):
    """基于 ADB 的 Android 自动化驱动"""

    def __init__(self, adb_client: AdbClient) -> None:
        self._adb = adb_client

    async def launch_app(self, package: str, activity: str | None = None) -> bool:
        try:
            await self._adb.start_activity(package, activity)
            return True
        except AdbError as e:
            logger.error(f"Failed to launch app {package}: {e}")
            return False

    async def tap(self, x: int, y: int) -> bool:
        try:
            await self._adb.input_tap(x, y)
            return True
        except AdbError as e:
            logger.error(f"Failed to tap ({x}, {y}): {e}")
            return False

    async def input_text(self, text: str) -> bool:
        """输入文本，中文走 ADBKeyBoard broadcast，ASCII 走 input text"""
        try:
            has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)
            if has_cjk:
                await self._adb.broadcast_text(text)
            else:
                await self._adb.input_text(text)
            return True
        except AdbError as e:
            logger.error(f"Failed to input text: {e}")
            return False

    async def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300,
    ) -> bool:
        try:
            await self._adb.input_swipe(x1, y1, x2, y2, duration_ms)
            return True
        except AdbError as e:
            logger.error(f"Failed to swipe: {e}")
            return False

    async def screenshot(self) -> bytes:
        return await self._adb.screencap()

    async def find_element(
        self,
        text: str | None = None,
        resource_id: str | None = None,
        class_name: str | None = None,
        content_desc: str | None = None,
    ) -> list[ElementInfo]:
        """通过 uiautomator dump 查找 UI 元素"""
        try:
            xml_str = await self._adb.dump_ui()
            return _parse_ui_xml(
                xml_str, text=text, resource_id=resource_id,
                class_name=class_name, content_desc=content_desc,
            )
        except AdbError as e:
            logger.error(f"Failed to find element: {e}")
            return []
        except ET.ParseError as e:
            logger.error(f"Failed to parse UI XML: {e}")
            return []

    async def press_key(self, keycode: int) -> bool:
        try:
            await self._adb.input_keyevent(keycode)
            return True
        except AdbError as e:
            logger.error(f"Failed to press key {keycode}: {e}")
            return False


# ── XML 解析 ─────────────────────────────────────────

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _parse_bounds(bounds_str: str) -> tuple[int, int, int, int]:
    """解析 bounds 属性，如 '[0,0][1080,2400]'"""
    m = _BOUNDS_RE.match(bounds_str)
    if not m:
        return (0, 0, 0, 0)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def _parse_ui_xml(
    xml_str: str,
    text: str | None = None,
    resource_id: str | None = None,
    class_name: str | None = None,
    content_desc: str | None = None,
) -> list[ElementInfo]:
    """解析 uiautomator dump XML，按条件过滤元素"""
    # 清理 XML 前的噪音输出
    xml_start = xml_str.find("<?xml")
    if xml_start == -1:
        xml_start = xml_str.find("<hierarchy")
    if xml_start == -1:
        return []
    xml_str = xml_str[xml_start:]

    root = ET.fromstring(xml_str)
    results: list[ElementInfo] = []

    for node in root.iter("node"):
        node_text = node.get("text", "")
        node_rid = node.get("resource-id", "")
        node_cls = node.get("class", "")
        node_bounds = node.get("bounds", "")
        node_clickable = node.get("clickable", "false") == "true"
        node_enabled = node.get("enabled", "true") == "true"
        node_desc = node.get("content-desc", "")

        # 过滤条件
        if text and text not in node_text:
            continue
        if resource_id and resource_id not in node_rid:
            continue
        if class_name and class_name not in node_cls:
            continue
        if content_desc and content_desc not in node_desc:
            continue

        results.append(ElementInfo(
            text=node_text,
            resource_id=node_rid,
            class_name=node_cls,
            bounds=_parse_bounds(node_bounds),
            clickable=node_clickable,
            enabled=node_enabled,
        ))

    return results
