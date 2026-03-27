"""HemaSetLocationTool - 设置盒马收货地址"""
from __future__ import annotations

import asyncio
from typing import Any

from core.interfaces.tool import BaseTool, ToolResult
from plugins.agents.purchasing_agent.tools._constants import (
    RID_HOME_LOCATION_TEXT, RID_HOME_LOCATION_LAYOUT,
    RID_SELECT_ADDRESS_EDIT, RID_ADDRESS_TITLE,
    UI_SETTLE_DELAY,
)
from plugins.agents.purchasing_agent.tools._driver_mixin import (
    get_automation_driver, DeviceNotConnectedError,
    ensure_hema_foreground, dismiss_popups,
)


class HemaSetLocationTool(BaseTool):
    """设置盒马APP收货地址"""

    name = "hema_set_location"
    description = "设置盒马APP的收货地址和手机号。首次使用时需要调用此工具。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "收货地址关键词，如：金台北街小区",
            },
            "phone": {
                "type": "string",
                "description": "联系手机号（可选）",
                "default": "",
            },
        },
        "required": ["address"],
    }

    def __init__(self) -> None:
        self._registry = None

    def set_registry(self, registry: Any) -> None:
        self._registry = registry

    async def execute(self, **params: Any) -> ToolResult:
        address = params.get("address", "")
        phone = params.get("phone", "")

        if not address:
            return ToolResult(success=False, error="地址不能为空")

        if not self._registry:
            return ToolResult(success=False, error="插件注册表未注入")

        try:
            driver = await get_automation_driver(self._registry)

            # 1. 确保盒马在前台首页
            self._report_progress("正在打开盒马APP...")
            await ensure_hema_foreground(driver)

            # 2. 读取当前地址，如果已匹配则跳过
            self._report_progress("检查当前收货地址...")
            loc_text_el = await driver.wait_for_element(
                resource_id=RID_HOME_LOCATION_TEXT,
                timeout=5,
            )
            if loc_text_el:
                current_addr = loc_text_el.text.strip()
                if current_addr and address in current_addr:
                    return ToolResult(
                        success=True,
                        data={
                            "address": address,
                            "phone": phone,
                            "current_location": current_addr,
                            "message": f"地址已匹配，无需切换: {current_addr}",
                            "skipped": True,
                        },
                    )

            # 3. 点击首页地址栏 → 进入「选择地址」页
            self._report_progress("点击地址栏，准备切换地址...")
            addr_layout = await driver.wait_for_element(
                resource_id=RID_HOME_LOCATION_LAYOUT,
                timeout=15,
            )
            if not addr_layout:
                return ToolResult(
                    success=False,
                    error="未找到首页地址栏，盒马APP可能未加载完成",
                )
            await driver.tap_element(addr_layout)

            # 等待地址选择页加载（检测搜索框出现）
            search_edit = await driver.wait_for_element(
                resource_id=RID_SELECT_ADDRESS_EDIT,
                timeout=5,
            )

            # 3.5 处理可能弹出的定位权限/门店切换弹窗
            await self._dismiss_location_dialog(driver)

            if not search_edit:
                # 弹窗关闭后重试
                search_edit = await driver.wait_for_element(
                    resource_id=RID_SELECT_ADDRESS_EDIT,
                    timeout=3,
                )

            # 4. 点击搜索框并输入地址关键词
            self._report_progress(f"搜索地址：{address}")
            if not search_edit:
                return ToolResult(
                    success=False,
                    error="未找到地址搜索框，可能不在地址选择页",
                )
            await driver.tap_element(search_edit)
            await asyncio.sleep(UI_SETTLE_DELAY)
            await driver.input_text(address)

            # 等待搜索建议列表加载
            await driver.wait_for_element(
                resource_id=RID_ADDRESS_TITLE,
                timeout=4,
            )

            # 5. 从搜索结果中选择匹配的地址
            self._report_progress("选择匹配的地址...")
            selected_name = await self._select_matching_result(driver, address)
            if not selected_name:
                return ToolResult(
                    success=False,
                    error=f"搜索「{address}」无匹配结果，请检查地址关键词",
                )

            # 6. 地址切换后可能有确认弹窗（门店切换确认等），逐层处理
            for _ in range(3):
                await asyncio.sleep(1.5)
                # 检查是否有「确认切换」「确定」类弹窗
                confirm_btn = await driver.find_element(text="确认切换")
                if not confirm_btn:
                    confirm_btn = await driver.find_element(text="确定")
                if confirm_btn:
                    await driver.tap_element(confirm_btn[0])
                    await asyncio.sleep(1)
                    continue
                # 通用弹窗关闭
                await dismiss_popups(driver, max_rounds=1)
                break

            # 7. 验证地址是否已切换（等待首页地址文字更新）
            self._report_progress("验证地址切换结果...")
            loc_text_el = await driver.wait_for_element(
                resource_id=RID_HOME_LOCATION_TEXT,
                timeout=8,
            )
            current_addr = loc_text_el.text if loc_text_el else ""

            if not current_addr:
                # 可能还有弹窗，再关一轮
                await dismiss_popups(driver)
                loc_text_el = await driver.wait_for_element(
                    resource_id=RID_HOME_LOCATION_TEXT,
                    timeout=5,
                )
                current_addr = loc_text_el.text if loc_text_el else ""

            return ToolResult(
                success=True,
                data={
                    "address": address,
                    "phone": phone,
                    "current_location": current_addr,
                    "selected": selected_name,
                    "message": f"已切换收货地址: {current_addr or selected_name}",
                },
            )

        except DeviceNotConnectedError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"设置地址失败: {e}")

    async def _dismiss_location_dialog(self, driver: Any) -> None:
        """关闭可能弹出的定位权限提示弹窗"""
        close_btn = await driver.wait_for_element(
            resource_id="com.wudaokou.hippo:id/uikit_menu_close",
            timeout=2,
        )
        if close_btn:
            await driver.tap_element(close_btn)
            await asyncio.sleep(0.5)

        # 处理其他常见弹窗
        await dismiss_popups(driver, max_rounds=1)

    async def _select_matching_result(self, driver: Any, address: str) -> str:
        """从搜索结果列表中选择与 address 最匹配的项

        策略：优先精确匹配 title，其次包含匹配 title，最后 subtitle 包含匹配
        """
        titles = await driver.find_element(
            resource_id=RID_ADDRESS_TITLE,
        )
        if not titles:
            return ""

        # 优先：title 完全等于 address
        for el in titles:
            if el.text.strip() == address:
                await driver.tap_element(el)
                return el.text.strip()

        # 其次：title 包含 address
        for el in titles:
            if address in el.text.strip():
                await driver.tap_element(el)
                return el.text.strip()

        # 再次：address 包含 title（用户输入了更长的地址）
        for el in titles:
            title_text = el.text.strip()
            if title_text and title_text in address:
                await driver.tap_element(el)
                return title_text

        # 最后兜底：选第一个结果
        if titles:
            first = titles[0]
            await driver.tap_element(first)
            return first.text.strip()

        return ""
