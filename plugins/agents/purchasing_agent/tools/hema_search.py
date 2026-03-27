"""HemaSearchTool - 在盒马搜索商品"""
from __future__ import annotations

import asyncio
from typing import Any

from core.interfaces.tool import BaseTool, ToolResult
from plugins.agents.purchasing_agent.tools._constants import (
    RID_SEARCH_EDITTEXT, RID_PRODUCT_CARD, KEYCODE_ENTER,
    MAX_VISIBLE_PRODUCTS, MIN_PRODUCT_NAME_LENGTH, UI_SETTLE_DELAY,
)
from plugins.agents.purchasing_agent.tools._driver_mixin import (
    get_automation_driver, DeviceNotConnectedError,
    ensure_hema_foreground, dismiss_popups, is_on_search_page, scroll_down,
)


class HemaSearchTool(BaseTool):
    """在盒马APP中搜索商品"""

    name = "hema_search"
    description = "在盒马APP中搜索商品，返回搜索结果列表（名称、价格）。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词，如：白菜、鸡蛋、牛奶",
            },
        },
        "required": ["keyword"],
    }

    def __init__(self) -> None:
        self._registry = None

    def set_registry(self, registry: Any) -> None:
        self._registry = registry

    async def execute(self, **params: Any) -> ToolResult:
        keyword = params.get("keyword", "")
        if not keyword:
            return ToolResult(success=False, error="搜索关键词不能为空")

        if not self._registry:
            return ToolResult(success=False, error="插件注册表未注入")

        try:
            driver = await get_automation_driver(self._registry)

            # 1. 智能导航：优先复用搜索页，避免回首页
            on_search = await is_on_search_page(driver)

            if on_search:
                # 已在搜索页 → 直接清空输入新关键词
                self._report_progress(f"搜索：{keyword}")
                input_el = await driver.wait_for_element(
                    resource_id=RID_SEARCH_EDITTEXT,
                    timeout=3,
                )
                if input_el:
                    await driver.tap_element(input_el)
                    await asyncio.sleep(UI_SETTLE_DELAY)
                    # driver.input_text 内部使用 send_keys(clear=True)，会自动清空
                    await driver.input_text(keyword)
                else:
                    # 输入框不可交互，回退到首页流程
                    on_search = False

            if not on_search:
                # 从首页进入搜索
                self._report_progress("打开搜索页...")
                await ensure_hema_foreground(driver)

                search_entry = await driver.wait_for_element(
                    resource_id="com.wudaokou.hippo:id/home_page_titlebar_search_layout",
                    timeout=5,
                )
                if not search_entry:
                    # 弹窗可能遮挡
                    await dismiss_popups(driver)
                    await asyncio.sleep(0.5)
                    search_entry = await driver.wait_for_element(
                        resource_id="com.wudaokou.hippo:id/home_page_titlebar_search_layout",
                        timeout=5,
                    )
                if not search_entry:
                    return ToolResult(
                        success=False,
                        error="未找到搜索入口，盒马APP可能未在首页",
                    )
                await driver.tap_element(search_entry)

                # 等待搜索输入框出现
                self._report_progress(f"搜索：{keyword}")
                input_el = await driver.wait_for_element(
                    resource_id=RID_SEARCH_EDITTEXT,
                    timeout=5,
                )
                if not input_el:
                    return ToolResult(success=False, error="未找到搜索输入框")
                await driver.tap_element(input_el)
                await asyncio.sleep(UI_SETTLE_DELAY)
                await driver.input_text(keyword)

            # 2. 确认搜索
            await asyncio.sleep(0.3)
            confirm = await driver.wait_for_element(
                resource_id="com.wudaokou.hippo:id/search_item_confirm",
                timeout=3,
            )
            if confirm:
                await driver.tap_element(confirm)
            else:
                await driver.press_key(KEYCODE_ENTER)

            # 3. 等待搜索结果加载（用元素出现代替固定 sleep）
            self._report_progress("等待搜索结果...")
            result_card = await driver.wait_for_element(
                resource_id=RID_PRODUCT_CARD,
                timeout=6,
            )
            # 即使没找到 card 也继续尝试解析（可能是其他布局）
            if not result_card:
                await asyncio.sleep(2)

            # 4. 解析搜索结果
            self._report_progress("解析搜索结果...")
            products = await self._parse_search_results(driver)

            # 5. 首屏结果不足时滚动加载更多
            if len(products) < 3:
                self._report_progress("加载更多结果...")
                await scroll_down(driver)
                more = await self._parse_search_results(driver)
                # 合并去重（按 name）
                seen = {p["name"] for p in products}
                for p in more:
                    if p["name"] and p["name"] not in seen:
                        products.append(p)
                        seen.add(p["name"])

            if not products:
                # 提供引导信息
                suggestions = self._suggest_alternatives(keyword)
                return ToolResult(
                    success=True,
                    data={
                        "keyword": keyword,
                        "products": [],
                        "message": f"未搜索到「{keyword}」相关商品",
                        "suggestions": suggestions,
                    },
                )

            return ToolResult(
                success=True,
                data={
                    "keyword": keyword,
                    "products": products,
                    "total": len(products),
                    "message": f"搜索到 {len(products)} 个「{keyword}」相关商品",
                },
            )

        except DeviceNotConnectedError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"搜索失败: {e}")

    async def _parse_search_results(self, driver: Any) -> list[dict]:
        """解析搜索结果页的商品信息"""
        products: list[dict] = []

        cards = await driver.find_element(
            resource_id="com.wudaokou.hippo:id/scene_root_view-hm_search_goods_item_line_simple",
        )
        if not cards:
            return products

        all_tvs = await driver.find_element(class_name="android.widget.TextView")

        for idx, card in enumerate(cards[:MAX_VISIBLE_PRODUCTS]):
            card_top = card.bounds[1]
            card_bottom = card.bounds[3]

            name = ""
            price = ""

            for tv in all_tvs:
                tv_top = tv.bounds[1]
                tv_bottom = tv.bounds[3]
                if tv_top >= card_top and tv_bottom <= card_bottom:
                    txt = tv.text.strip()
                    if txt.startswith("¥") and not price:
                        price = txt
                    elif len(txt) > MIN_PRODUCT_NAME_LENGTH and not txt.startswith("¥") and not name:
                        name = txt

            if name or price:
                products.append({
                    "index": idx,
                    "name": name,
                    "price": price,
                })

        return products

    @staticmethod
    def _suggest_alternatives(keyword: str) -> list[str]:
        """根据关键词生成搜索建议"""
        tips: list[str] = []
        if len(keyword) > 4:
            tips.append(f"尝试简化关键词，如只搜「{keyword[:2]}」")
        tips.append("该商品可能不在当前配送区域的库存中")
        tips.append("尝试搜索同品类的替代商品")
        return tips
