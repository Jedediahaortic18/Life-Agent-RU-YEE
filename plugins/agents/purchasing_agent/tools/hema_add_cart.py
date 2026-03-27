"""HemaAddCartTool - 将商品加入盒马购物车"""
from __future__ import annotations

import asyncio
from typing import Any

from core.interfaces.tool import BaseTool, ToolResult
from plugins.agents.purchasing_agent.tools._constants import (
    RID_CART_ICON, RID_CART_BADGE, RID_PRODUCT_CARD,
    MAX_VISIBLE_PRODUCTS, MIN_PRODUCT_NAME_LENGTH,
    FALLBACK_Y_PROXIMITY_PX, TAP_INTERVAL, CART_VERIFY_DELAY,
)
from plugins.agents.purchasing_agent.tools._driver_mixin import (
    get_automation_driver, DeviceNotConnectedError,
)


class HemaAddCartTool(BaseTool):
    """将搜索结果中的商品加入盒马购物车"""

    name = "hema_add_cart"
    description = "将盒马搜索结果中的商品加入购物车。建议先调用 hema_search 搜索商品。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "product_index": {
                "type": "integer",
                "description": "搜索结果中的商品序号（从0开始）",
                "default": 0,
            },
            "product_name": {
                "type": "string",
                "description": "商品名称（用于确认匹配）",
                "default": "",
            },
            "quantity": {
                "type": "integer",
                "description": "购买数量",
                "default": 1,
            },
        },
        "required": [],
    }

    def __init__(self) -> None:
        self._registry = None

    def set_registry(self, registry: Any) -> None:
        self._registry = registry

    async def execute(self, **params: Any) -> ToolResult:
        product_index = params.get("product_index", 0)
        product_name = params.get("product_name", "")
        quantity = params.get("quantity", 1)

        if not self._registry:
            return ToolResult(success=False, error="插件注册表未注入")

        try:
            driver = await get_automation_driver(self._registry)

            # 1. 构建商品卡片 → 加购按钮映射（通过 bounds 关联）
            self._report_progress(f"查找商品「{product_name or f'#{product_index}'}」...")
            cards = await self._build_product_map(driver)

            if not cards:
                return ToolResult(
                    success=False,
                    error="未找到可加购的商品，可能不在搜索结果页或页面未加载完成",
                )

            # 2. 匹配目标商品
            target = None
            if product_name:
                # 按名称匹配：精确 > 包含 > 序号兜底
                for c in cards:
                    if c["name"] == product_name:
                        target = c
                        break
                if not target:
                    for c in cards:
                        if product_name in c["name"] or c["name"] in product_name:
                            target = c
                            break

            if not target:
                if product_index < len(cards):
                    target = cards[product_index]
                else:
                    return ToolResult(
                        success=False,
                        error=f"商品序号 {product_index} 超出范围（共 {len(cards)} 个）",
                    )

            # 3. 名称不完全匹配时，自动选第一个最接近的（不打扰用户）
            auto_selected = False
            if product_name and target["name"] and product_name not in target["name"] and target["name"] not in product_name:
                auto_selected = True

            # 4. 点击加购按钮
            actual_name = target["name"] or f"商品#{target['index']}"
            self._report_progress(f"正在加购「{actual_name}」x{quantity}...")

            btn = target["button"]
            for i in range(quantity):
                await driver.tap_element(btn)
                if i < quantity - 1:
                    await asyncio.sleep(TAP_INTERVAL)

            # 5. 验证购物车角标
            await asyncio.sleep(CART_VERIFY_DELAY)
            badge = await driver.find_element(resource_id=RID_CART_BADGE)
            cart_count = badge[0].text if badge else "?"

            msg = f"已将「{actual_name}」x{quantity} 加入购物车"
            if auto_selected and product_name:
                msg = f"未找到「{product_name}」，已自动选择「{actual_name}」x{quantity} 加入购物车"

            return ToolResult(
                success=True,
                data={
                    "product_name": actual_name,
                    "product_index": target["index"],
                    "quantity": quantity,
                    "cart_count": cart_count,
                    "auto_selected": auto_selected,
                    "original_name": product_name if auto_selected else None,
                    "message": msg,
                },
            )

        except DeviceNotConnectedError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"加入购物车失败: {e}")

    async def _build_product_map(self, driver: Any) -> list[dict]:
        """构建商品卡片列表，每项包含 name/price/button(ElementInfo)/index。

        通过 bounds 将商品卡片内的名称、价格与对应的加购按钮关联。
        """
        from core.interfaces.automation import ElementInfo

        # 查找加购按钮
        add_buttons: list[ElementInfo] = await driver.find_element(
            resource_id=RID_CART_ICON,
        )
        if not add_buttons:
            add_buttons = await driver.find_element(content_desc="加入购物车")
        if not add_buttons:
            return []

        # 查找商品卡片区域
        cards_el = await driver.find_element(resource_id=RID_PRODUCT_CARD)

        # 获取所有 TextView 用于匹配名称和价格
        all_tvs: list[ElementInfo] = await driver.find_element(
            class_name="android.widget.TextView",
        )

        results: list[dict] = []

        for idx, btn in enumerate(add_buttons[:MAX_VISIBLE_PRODUCTS]):
            btn_cx, btn_cy = btn.center

            # 找该按钮所属的商品卡片（bounds 包含按钮中心）
            card_bounds = None
            for card in (cards_el or []):
                cl, ct, cr, cb = card.bounds
                if cl <= btn_cx <= cr and ct <= btn_cy <= cb:
                    card_bounds = card.bounds
                    break

            name = ""
            price = ""

            if card_bounds:
                ct, cb = card_bounds[1], card_bounds[3]
                for tv in all_tvs:
                    tv_top, tv_bottom = tv.bounds[1], tv.bounds[3]
                    if tv_top >= ct and tv_bottom <= cb:
                        txt = tv.text.strip()
                        if txt.startswith("¥") and not price:
                            price = txt
                        elif len(txt) > MIN_PRODUCT_NAME_LENGTH and not txt.startswith("¥") and not name:
                            name = txt
            else:
                # 无卡片信息时，按 Y 坐标范围匹配（按钮上方区域内）
                for tv in all_tvs:
                    tv_cy = (tv.bounds[1] + tv.bounds[3]) // 2
                    if 0 < (btn_cy - tv_cy) < FALLBACK_Y_PROXIMITY_PX:
                        txt = tv.text.strip()
                        if txt.startswith("¥") and not price:
                            price = txt
                        elif len(txt) > MIN_PRODUCT_NAME_LENGTH and not txt.startswith("¥") and not name:
                            name = txt

            results.append({
                "index": idx,
                "name": name,
                "price": price,
                "button": btn,
            })

        return results
