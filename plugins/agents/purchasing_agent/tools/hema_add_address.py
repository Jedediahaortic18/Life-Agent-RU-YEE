"""HemaAddAddressTool - 在盒马APP中新增收货地址"""
from __future__ import annotations

import asyncio
from typing import Any

from core.interfaces.tool import BaseTool, ToolResult
from plugins.agents.purchasing_agent.tools._constants import UI_SETTLE_DELAY, PAGE_LOAD_DELAY
from plugins.agents.purchasing_agent.tools._driver_mixin import (
    get_automation_driver, DeviceNotConnectedError,
    ensure_hema_foreground, dismiss_popups,
)


class HemaAddAddressTool(BaseTool):
    """在盒马APP中新增一条收货地址（小区搜索 → 填写门牌号/联系人/手机号 → 保存）"""

    name = "hema_add_address"
    description = "在盒马APP中新增收货地址。需提供小区关键词、门牌号、联系人、手机号。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "小区/写字楼搜索关键词，如：金台北街",
            },
            "door_number": {
                "type": "string",
                "description": "门牌号，如：5号楼1单元1101",
            },
            "name": {
                "type": "string",
                "description": "收货人姓名",
            },
            "phone": {
                "type": "string",
                "description": "联系手机号",
            },
        },
        "required": ["keyword", "door_number", "name", "phone"],
    }

    def __init__(self) -> None:
        self._registry = None

    def set_registry(self, registry: Any) -> None:
        self._registry = registry

    async def execute(self, **params: Any) -> ToolResult:
        keyword = params.get("keyword", "")
        door_number = params.get("door_number", "")
        name = params.get("name", "")
        phone = params.get("phone", "")

        if not all([keyword, door_number, name, phone]):
            return ToolResult(success=False, error="关键词、门牌号、联系人、手机号均不能为空")

        if not self._registry:
            return ToolResult(success=False, error="插件注册表未注入")

        try:
            driver = await get_automation_driver(self._registry)
            steps_done: list[str] = []

            # 1. 确保盒马在前台（统一使用共享方法）
            self._report_progress("启动盒马APP...")
            await ensure_hema_foreground(driver)
            steps_done.append("启动盒马")

            # 2. 进入「我的」tab
            self._report_progress("进入我的页面...")
            clicked = await driver.click_text("我的", timeout=3.0)
            if not clicked:
                return ToolResult(success=False, error="未找到「我的」入口")
            await asyncio.sleep(PAGE_LOAD_DELAY)
            await dismiss_popups(driver)
            steps_done.append("进入我的页面")

            # 3. 点击「收货地址」
            self._report_progress("打开收货地址...")
            clicked = await driver.click_text("收货地址", timeout=3.0)
            if not clicked:
                return ToolResult(success=False, error="未找到「收货地址」入口")
            await asyncio.sleep(PAGE_LOAD_DELAY)
            steps_done.append("进入收货地址页面")

            # 4. 点击「新增收货地址」
            self._report_progress("新增收货地址...")
            clicked = await driver.click_text("新增收货地址", timeout=3.0)
            if not clicked:
                return ToolResult(success=False, error="未找到「新增收货地址」按钮")
            await asyncio.sleep(PAGE_LOAD_DELAY)
            steps_done.append("打开新增地址表单")

            # 5. 搜索小区
            self._report_progress(f"搜索地址：{keyword}")
            search_input = await driver.find_element(text="小区/写字楼/学校")
            if not search_input:
                search_input = await driver.find_element(text="搜索小区")
            if search_input:
                await driver.tap_element(search_input[0])
                await asyncio.sleep(UI_SETTLE_DELAY)
                await driver.input_text(keyword)
                await asyncio.sleep(PAGE_LOAD_DELAY)
            else:
                return ToolResult(success=False, error="未找到地址搜索框")

            # 6. 选择第一个搜索结果
            results = await driver.find_element(text=keyword)
            selected_addr = ""
            if results:
                await driver.tap_element(results[0])
                selected_addr = results[0].text
                await asyncio.sleep(1)
                steps_done.append(f"选择地址: {selected_addr}")
            else:
                return ToolResult(
                    success=False,
                    error=f"搜索「{keyword}」无结果，请检查关键词",
                )

            # 7. 填写门牌号
            self._report_progress("填写详细信息...")
            door_input = await driver.find_element(text="例：8号楼808室")
            if not door_input:
                door_input = await driver.find_element(text="门牌号")
            if door_input:
                await driver.tap_element(door_input[0])
                await asyncio.sleep(UI_SETTLE_DELAY)
                await driver.input_text(door_number)
                await asyncio.sleep(UI_SETTLE_DELAY)
                steps_done.append(f"填写门牌号: {door_number}")

            # 8. 填写联系人
            name_input = await driver.find_element(text="收货人姓名")
            if name_input:
                await driver.tap_element(name_input[0])
                await asyncio.sleep(UI_SETTLE_DELAY)
                await driver.input_text(name)
                await asyncio.sleep(UI_SETTLE_DELAY)
                steps_done.append(f"填写联系人: {name}")

            # 9. 填写手机号
            phone_input = await driver.find_element(text="配送员联系您的手机号")
            if not phone_input:
                phone_input = await driver.find_element(text="手机号")
            if phone_input:
                await driver.tap_element(phone_input[0])
                await asyncio.sleep(UI_SETTLE_DELAY)
                await driver.input_text(phone)
                await asyncio.sleep(UI_SETTLE_DELAY)
                steps_done.append(f"填写手机号: {phone}")

            # 10. 点击保存
            self._report_progress("保存地址...")
            clicked = await driver.click_text("保存", timeout=3.0)
            if not clicked:
                return ToolResult(
                    success=False,
                    error="未找到保存按钮",
                    data={"steps_done": steps_done},
                )
            await asyncio.sleep(PAGE_LOAD_DELAY)
            steps_done.append("保存成功")

            return ToolResult(
                success=True,
                data={
                    "message": f"已新增收货地址: {selected_addr} {door_number}",
                    "name": name,
                    "phone": phone,
                    "address": f"{selected_addr} {door_number}",
                    "steps_done": steps_done,
                },
            )

        except DeviceNotConnectedError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"新增地址失败: {e}")
