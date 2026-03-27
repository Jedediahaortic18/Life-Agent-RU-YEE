"""Hema 工具单元测试"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.interfaces.automation import ElementInfo
from plugins.agents.purchasing_agent.tools.hema_set_location import HemaSetLocationTool
from plugins.agents.purchasing_agent.tools.hema_search import HemaSearchTool
from plugins.agents.purchasing_agent.tools.hema_add_cart import HemaAddCartTool
from plugins.agents.purchasing_agent.tools.hema_cart_status import HemaCartStatusTool


def make_mock_registry(driver=None):
    """创建模拟 registry，返回带 driver 的 automation_u2 实例"""
    registry = MagicMock()
    adb_instance = MagicMock()
    adb_instance.driver = driver or AsyncMock()
    registry.get_instance.return_value = adb_instance
    return registry


def make_element(text="", resource_id="", bounds=(0, 0, 100, 50), clickable=True):
    return ElementInfo(
        text=text, resource_id=resource_id, bounds=bounds, clickable=clickable,
    )


# ── HemaSetLocationTool ──────────────────────────────

class TestHemaSetLocation:
    @pytest.fixture
    def tool(self):
        t = HemaSetLocationTool()
        driver = AsyncMock()
        driver.launch_app.return_value = True
        # wait_for_element: 地址栏 → 搜索栏 → 搜索结果 → 首页地址文本
        driver.wait_for_element.return_value = make_element(text="金台北街小区")
        driver.tap_element.return_value = True
        driver.input_text.return_value = True
        driver.press_key.return_value = True
        # find_element: ensure_hema_foreground 检查首页 → 地址搜索结果
        driver.find_element.return_value = [make_element(text="北京市朝阳区")]
        # _d.app_current() for ensure_hema_foreground
        driver._d = MagicMock()
        driver._d.app_current.return_value = {"package": "com.wudaokou.hippo"}
        t.set_registry(make_mock_registry(driver))
        return t

    async def test_success(self, tool):
        result = await tool.execute(address="北京市朝阳区", phone="13800000000")
        assert result.success is True
        assert "北京市朝阳区" in result.data["address"]

    async def test_missing_address(self, tool):
        result = await tool.execute(address="", phone="13800000000")
        assert result.success is False

    async def test_missing_phone(self, tool):
        result = await tool.execute(address="北京", phone="")
        assert result.success is False

    async def test_no_registry(self):
        tool = HemaSetLocationTool()
        result = await tool.execute(address="北京", phone="138")
        assert result.success is False
        assert "注册表" in result.error

    async def test_launch_failed(self):
        t = HemaSetLocationTool()
        driver = AsyncMock()
        driver._d = MagicMock()
        driver._d.app_current.return_value = {"package": "other.app"}
        driver.launch_app.return_value = False
        t.set_registry(make_mock_registry(driver))
        result = await t.execute(address="北京", phone="138")
        assert result.success is False
        assert "启动" in result.error

    async def test_address_already_matched(self):
        """当前盒马地址已包含用户指定地址，跳过切换"""
        t = HemaSetLocationTool()
        driver = AsyncMock()
        driver._d = MagicMock()
        driver._d.app_current.return_value = {"package": "com.wudaokou.hippo"}
        driver.find_element.return_value = [make_element(resource_id="home_page_titlebar_location_layout")]
        # wait_for_element 返回当前地址文本，包含用户指定地址
        driver.wait_for_element.return_value = make_element(text="北京市朝阳区金台北街小区")
        t.set_registry(make_mock_registry(driver))
        result = await t.execute(address="北京市朝阳区", phone="13800000000")
        assert result.success is True
        assert result.data["skipped"] is True
        assert "无需切换" in result.data["message"]
        # 不应该调用 tap_element（因为跳过了地址切换流程）
        driver.tap_element.assert_not_called()

    async def test_addr_bar_not_found(self):
        t = HemaSetLocationTool()
        driver = AsyncMock()
        driver._d = MagicMock()
        driver._d.app_current.return_value = {"package": "other.app"}
        driver.launch_app.return_value = True
        driver.wait_for_element.return_value = None
        t.set_registry(make_mock_registry(driver))
        result = await t.execute(address="北京", phone="138")
        assert result.success is False
        assert "地址栏" in result.error


# ── HemaSearchTool ───────────────────────────────────

class TestHemaSearch:
    @pytest.fixture
    def tool(self):
        t = HemaSearchTool()
        driver = AsyncMock()
        # wait_for_element: 搜索入口 → 输入框 → 确认按钮
        driver.wait_for_element.return_value = make_element(text="搜索")
        driver.tap_element.return_value = True
        driver.input_text.return_value = True
        driver.press_key.return_value = True
        # _d.app_current() for ensure_hema_foreground
        driver._d = MagicMock()
        driver._d.app_current.return_value = {"package": "com.wudaokou.hippo"}
        # find_element: ensure_hema_foreground首页检查 → cards → all_tvs
        home_el = [make_element(resource_id="home_page_titlebar_location_layout")]
        cards = [
            make_element(bounds=(0, 0, 1800, 250)),
            make_element(bounds=(0, 250, 1800, 500)),
        ]
        tvs = [
            # 卡片1内
            make_element(text="有机白菜 500g", bounds=(100, 50, 800, 100)),
            make_element(text="¥5.9/袋", bounds=(100, 120, 400, 160)),
            # 卡片2内
            make_element(text="大白菜 约1kg", bounds=(100, 300, 800, 350)),
            make_element(text="¥3.5/份", bounds=(100, 370, 400, 410)),
        ]
        driver.find_element.side_effect = [home_el, cards, tvs]
        t.set_registry(make_mock_registry(driver))
        return t

    async def test_search_success(self, tool):
        result = await tool.execute(keyword="白菜")
        assert result.success is True
        assert result.data["total"] == 2
        assert len(result.data["products"]) == 2
        assert result.data["products"][0]["name"] == "有机白菜 500g"
        assert result.data["products"][0]["price"] == "¥5.9/袋"

    async def test_search_empty_keyword(self, tool):
        result = await tool.execute(keyword="")
        assert result.success is False

    async def test_no_registry(self):
        tool = HemaSearchTool()
        result = await tool.execute(keyword="白菜")
        assert result.success is False

    async def test_search_no_results(self):
        t = HemaSearchTool()
        driver = AsyncMock()
        driver._d = MagicMock()
        driver._d.app_current.return_value = {"package": "other.app"}
        driver.wait_for_element.return_value = make_element(text="搜索")
        driver.tap_element.return_value = True
        driver.input_text.return_value = True
        driver.press_key.return_value = True
        driver.find_element.side_effect = [[], []]  # no cards, no tvs
        t.set_registry(make_mock_registry(driver))
        result = await t.execute(keyword="火星特产")
        assert result.success is True
        assert result.data["products"] == []

    async def test_search_entry_not_found(self):
        t = HemaSearchTool()
        driver = AsyncMock()
        driver._d = MagicMock()
        driver._d.app_current.return_value = {"package": "other.app"}
        driver.wait_for_element.return_value = None
        t.set_registry(make_mock_registry(driver))
        result = await t.execute(keyword="白菜")
        assert result.success is False
        assert "搜索" in result.error


# ── HemaAddCartTool ──────────────────────────────────

class TestHemaAddCart:
    @pytest.fixture
    def tool(self):
        t = HemaAddCartTool()
        driver = AsyncMock()
        driver.find_element.side_effect = [
            [make_element(text="加入购物车")],  # add buttons
            [make_element(text="3", resource_id="tv_badge_count_hint")],  # badge
        ]
        driver.tap_element.return_value = True
        t.set_registry(make_mock_registry(driver))
        return t

    async def test_add_success(self, tool):
        result = await tool.execute(product_name="白菜", quantity=1)
        assert result.success is True
        assert "白菜" in result.data["message"]
        assert result.data["cart_count"] == "3"

    async def test_no_registry(self):
        tool = HemaAddCartTool()
        result = await tool.execute(product_name="白菜")
        assert result.success is False

    async def test_no_add_button(self):
        t = HemaAddCartTool()
        driver = AsyncMock()
        driver.find_element.return_value = []
        t.set_registry(make_mock_registry(driver))
        result = await t.execute(product_name="白菜")
        assert result.success is False
        assert "按钮" in result.error

    async def test_index_out_of_range(self):
        t = HemaAddCartTool()
        driver = AsyncMock()
        driver.find_element.return_value = [make_element(text="加入购物车")]
        t.set_registry(make_mock_registry(driver))
        result = await t.execute(product_index=5, product_name="白菜")
        assert result.success is False
        assert "超出范围" in result.error


# ── HemaCartStatusTool ───────────────────────────────

def _make_u2_selector_mock(items_by_class: dict[str, list[dict]]) -> MagicMock:
    """创建 u2 设备 mock，支持 d(className=...) 选择器模式

    items_by_class: {class_name: [{contentDescription, bounds_top}, ...]}
    """
    d_mock = MagicMock()

    def make_selector(className="", **_kwargs):
        selector = MagicMock()
        entries = items_by_class.get(className, [])
        selector.count = len(entries)
        for i, entry in enumerate(entries):
            el = MagicMock()
            el.info = {
                "contentDescription": entry.get("contentDescription", ""),
                "bounds": {"top": entry.get("bounds_top", 0), "left": 0, "right": 100, "bottom": 50},
                "text": entry.get("text", ""),
                "className": className,
                "resourceName": None,
                "clickable": False,
                "enabled": True,
            }
            selector.__getitem__ = MagicMock(side_effect=lambda idx, entries=entries: MagicMock(
                info={
                    "contentDescription": entries[idx].get("contentDescription", ""),
                    "bounds": {"top": entries[idx].get("bounds_top", 0), "left": 0, "right": 100, "bottom": 50},
                    "text": entries[idx].get("text", ""),
                    "className": className,
                    "resourceName": None,
                    "clickable": False,
                    "enabled": True,
                }
            ))
        return selector

    d_mock.side_effect = make_selector
    d_mock.app_current.return_value = {"package": "com.wudaokou.hippo", "activity": ".CartActivity"}
    return d_mock


class TestHemaCartStatus:
    @pytest.fixture
    def tool(self):
        t = HemaCartStatusTool()
        driver = AsyncMock()
        driver.wait_for_element.return_value = make_element(text="购物车")
        driver.tap_element.return_value = True
        driver.find_element.return_value = []
        # mock _d for _parse_cart（使用 u2 底层 API）
        driver._d = _make_u2_selector_mock({
            "android.widget.EditText": [
                {"contentDescription": "购买数量2", "bounds_top": 500},
                {"contentDescription": "购买数量1", "bounds_top": 800},
            ],
            "android.widget.FrameLayout": [
                {"contentDescription": "￥4.5/盒", "bounds_top": 490},
                {"contentDescription": "￥5.9/份", "bounds_top": 790},
            ],
            "android.view.View": [
                {"contentDescription": "盒马日日鲜 冰鲜 鸡小胸 300g", "bounds_top": 300},
                {"contentDescription": "有机白菜 约500g", "bounds_top": 600},
            ],
        })
        t.set_registry(make_mock_registry(driver))
        return t

    async def test_cart_with_items(self, tool):
        result = await tool.execute()
        assert result.success is True
        assert result.data["item_count"] == 2
        assert result.data["items"][0]["name"] == "盒马日日鲜 冰鲜 鸡小胸 300g"
        assert result.data["items"][0]["price"] == "￥4.5/盒"
        assert result.data["items"][0]["quantity"] == 2
        assert result.data["items"][1]["name"] == "有机白菜 约500g"

    async def test_empty_cart(self):
        t = HemaCartStatusTool()
        driver = AsyncMock()
        driver.wait_for_element.return_value = make_element(text="购物车")
        driver.tap_element.return_value = True
        driver.find_element.return_value = []
        driver._d = _make_u2_selector_mock({})
        t.set_registry(make_mock_registry(driver))
        result = await t.execute()
        assert result.success is True
        assert result.data["items"] == []

    async def test_no_registry(self):
        tool = HemaCartStatusTool()
        result = await tool.execute()
        assert result.success is False

    async def test_cart_entry_not_found(self):
        t = HemaCartStatusTool()
        driver = AsyncMock()
        driver.wait_for_element.return_value = None
        t.set_registry(make_mock_registry(driver))
        result = await t.execute()
        assert result.success is False
        assert "购物车" in result.error
