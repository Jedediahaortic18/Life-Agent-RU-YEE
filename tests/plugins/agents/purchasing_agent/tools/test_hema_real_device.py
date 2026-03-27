"""盒马工具真机集成测试

需要 USB 连接安卓设备，盒马 APP 已安装并已登录。
运行方式：
    python -m pytest tests/plugins/agents/purchasing_agent/tools/test_hema_real_device.py -v -s

使用 -s 可以看到实时输出。
标记为 real_device，可在 CI 中跳过。
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import uiautomator2 as u2

from plugins.extensions.automation_u2.driver import U2AutomationDriver
from plugins.agents.purchasing_agent.tools.hema_set_location import HemaSetLocationTool
from plugins.agents.purchasing_agent.tools.hema_search import HemaSearchTool
from plugins.agents.purchasing_agent.tools.hema_add_cart import HemaAddCartTool
from plugins.agents.purchasing_agent.tools.hema_cart_status import HemaCartStatusTool


# 跳过条件：无设备连接时自动 skip
def _get_device():
    try:
        d = u2.connect()
        d.device_info  # noqa: B018 — 触发连接验证
        return d
    except Exception:
        return None


_device = _get_device()
pytestmark = pytest.mark.skipif(_device is None, reason="无 USB 连接的安卓设备")


def make_real_registry(driver: U2AutomationDriver) -> MagicMock:
    """构造真实 driver 的 mock registry"""
    registry = MagicMock()
    instance = MagicMock()
    instance.driver = driver
    # 让 get_automation_driver 里的健康检查通过
    instance.driver._d = driver._d
    registry.get_instance.return_value = instance
    return registry


@pytest.fixture(scope="module")
def driver():
    """模块级别的真机 driver"""
    assert _device is not None
    return U2AutomationDriver(_device)


@pytest.fixture(scope="module")
def registry(driver):
    return make_real_registry(driver)


# ── 测试 1: hema_set_location（地址已匹配时跳过）──────────
class TestRealSetLocation:
    async def test_read_current_location(self, driver, registry):
        """验证能读取盒马首页当前地址"""
        import asyncio
        from plugins.agents.purchasing_agent.tools._driver_mixin import ensure_hema_foreground, HEMA_PACKAGE

        # 确保盒马在前台首页（可能需要启动或从其他页面返回）
        await ensure_hema_foreground(driver)
        # 额外等待确保首页完全加载（从购物车页返回可能需要时间）
        await asyncio.sleep(3)

        # 读取当前地址
        loc_el = await driver.wait_for_element(
            resource_id="com.wudaokou.hippo:id/home_page_titlebar_location_text",
            timeout=15,
        )
        assert loc_el is not None, "未找到首页地址文本，盒马可能不在首页"
        print(f"\n当前盒马地址: {loc_el.text}")
        assert len(loc_el.text) > 0

    async def test_set_location_skip_if_matched(self, driver, registry):
        """如果当前地址已匹配，工具应跳过切换"""
        # 先获取当前地址
        from plugins.agents.purchasing_agent.tools._driver_mixin import ensure_hema_foreground
        await ensure_hema_foreground(driver)

        loc_el = await driver.wait_for_element(
            resource_id="com.wudaokou.hippo:id/home_page_titlebar_location_text",
            timeout=10,
        )
        assert loc_el is not None
        current_addr = loc_el.text.strip()
        print(f"\n当前地址: {current_addr}")

        # 用当前地址调 set_location，应该跳过
        tool = HemaSetLocationTool()
        tool.set_registry(registry)
        result = await tool.execute(address=current_addr, phone="13800000000")
        print(f"结果: {result}")
        assert result.success is True
        assert result.data.get("skipped") is True, f"地址 '{current_addr}' 应该匹配并跳过，但未跳过"


# ── 测试 2: hema_search ──────────────────────────────────
class TestRealSearch:
    async def test_search_common_item(self, driver, registry):
        """搜索常见商品（鸡蛋），验证返回结果"""
        tool = HemaSearchTool()
        tool.set_registry(registry)
        result = await tool.execute(keyword="鸡蛋")
        print(f"\n搜索'鸡蛋'结果: success={result.success}")
        if result.success and result.data:
            print(f"  找到 {result.data.get('total', 0)} 个商品")
            for p in result.data.get("products", [])[:3]:
                print(f"  - {p.get('name', '?')} {p.get('price', '?')}")
        assert result.success is True
        assert result.data is not None
        # 鸡蛋应该在大多数区域都有
        assert result.data.get("total", 0) > 0, "鸡蛋搜索结果不应为空"

    async def test_search_uncommon_item(self, driver, registry):
        """搜索罕见商品（盒马可能显示推荐商品而非空结果）"""
        tool = HemaSearchTool()
        tool.set_registry(registry)
        result = await tool.execute(keyword="火星岩石特产xyz123")
        print(f"\n搜索罕见商品结果: success={result.success}, total={result.data.get('total', 0)}")
        assert result.success is True
        # 盒马搜不到时可能显示推荐商品，这也是正常行为
        assert result.data is not None


# ── 测试 3: hema_add_cart ────────────────────────────────
class TestRealAddCart:
    async def test_add_first_search_result(self, driver, registry):
        """先搜索再加购第一个结果"""
        # 1. 先搜索
        search_tool = HemaSearchTool()
        search_tool.set_registry(registry)
        search_result = await search_tool.execute(keyword="鸡蛋")
        assert search_result.success is True
        products = search_result.data.get("products", [])
        assert len(products) > 0, "没有搜索结果，无法测试加购"
        print(f"\n搜索到 {len(products)} 个商品，准备加购第一个: {products[0].get('name')}")

        # 2. 加购第一个商品
        cart_tool = HemaAddCartTool()
        cart_tool.set_registry(registry)
        result = await cart_tool.execute(
            product_name=products[0].get("name", "鸡蛋"),
            product_index=0,
            quantity=1,
        )
        print(f"加购结果: {result}")
        assert result.success is True


# ── 测试 4: hema_cart_status ─────────────────────────────
class TestRealCartStatus:
    async def test_view_cart(self, driver, registry):
        """查看购物车状态"""
        tool = HemaCartStatusTool()
        tool.set_registry(registry)
        result = await tool.execute()
        print(f"\n购物车状态: success={result.success}")
        if result.success and result.data:
            items = result.data.get("items", [])
            print(f"  购物车共 {result.data.get('item_count', 0)} 件商品")
            for item in items[:5]:
                print(f"  - {item.get('name', '?')} {item.get('price', '?')}")
            total = result.data.get("total_price", "")
            if total:
                print(f"  合计: {total}")
        assert result.success is True
