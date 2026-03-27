"""HemaAddAddressTool 单元测试"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plugins.agents.purchasing_agent.tools.hema_add_address import HemaAddAddressTool


@pytest.fixture()
def tool():
    t = HemaAddAddressTool()
    t.set_registry(MagicMock())
    return t


@pytest.fixture()
def mock_driver():
    driver = AsyncMock()
    driver.launch_app.return_value = True
    driver.click_text.return_value = True
    driver.press_key.return_value = True
    driver.input_text.return_value = True

    mock_el = MagicMock()
    mock_el.text = "金台北街小区"
    driver.find_element.return_value = [mock_el]
    driver.tap_element.return_value = True

    return driver


def _patch_driver(tool, mock_driver):
    return patch(
        "plugins.agents.purchasing_agent.tools.hema_add_address.get_automation_driver",
        return_value=mock_driver,
    )


class TestHemaAddAddressToolMeta:

    def test_name(self):
        tool = HemaAddAddressTool()
        assert tool.name == "hema_add_address"

    def test_required_params(self):
        tool = HemaAddAddressTool()
        required = tool.parameters_schema["required"]
        assert "keyword" in required
        assert "door_number" in required
        assert "name" in required
        assert "phone" in required


class TestHemaAddAddressValidation:

    async def test_missing_params(self, tool):
        result = await tool.execute(keyword="", door_number="", name="", phone="")
        assert result.success is False
        assert "不能为空" in result.error

    async def test_no_registry(self):
        tool = HemaAddAddressTool()
        result = await tool.execute(
            keyword="金台", door_number="5号楼", name="时", phone="17600362005",
        )
        assert result.success is False
        assert "注册表" in result.error


class TestHemaAddAddressFlow:

    async def test_full_success(self, tool, mock_driver):
        with _patch_driver(tool, mock_driver):
            result = await tool.execute(
                keyword="金台北街",
                door_number="5号楼1单元1101",
                name="时",
                phone="17600362005",
            )

        assert result.success is True
        assert "金台北街小区" in result.data["address"]
        assert result.data["phone"] == "17600362005"
        assert len(result.data["steps_done"]) >= 5
        mock_driver.launch_app.assert_called_once()
        mock_driver.input_text.assert_called()

    async def test_launch_fail(self, tool, mock_driver):
        mock_driver.launch_app.return_value = False

        with _patch_driver(tool, mock_driver):
            result = await tool.execute(
                keyword="金台", door_number="1号", name="张", phone="138",
            )

        assert result.success is False
        assert "启动盒马" in result.error

    async def test_my_tab_not_found(self, tool, mock_driver):
        # click_text 第一次（关闭弹窗时 find_element 返回空）然后「我的」返回 False
        mock_driver.find_element.return_value = []
        mock_driver.click_text.return_value = False

        with _patch_driver(tool, mock_driver):
            result = await tool.execute(
                keyword="金台", door_number="1号", name="张", phone="138",
            )

        assert result.success is False
        assert "我的" in result.error

    async def test_search_no_results(self, tool, mock_driver):
        call_count = 0

        async def _click_text_side_effect(text, timeout=5.0):
            return True

        mock_driver.click_text = AsyncMock(side_effect=_click_text_side_effect)

        # find_element: 前几次返回空（弹窗关闭），搜索框返回元素，搜索结果返回空
        find_call_count = {"n": 0}
        search_input_el = MagicMock()
        search_input_el.text = "小区/写字楼/学校"

        async def _find_side_effect(**kwargs):
            find_call_count["n"] += 1
            text = kwargs.get("text", "")
            # 弹窗检测返回空
            if text in ("关闭弹窗", "温馨提示"):
                return []
            # 搜索框
            if text == "小区/写字楼/学校":
                return [search_input_el]
            # 搜索结果
            if text == "金台":
                return []
            return []

        mock_driver.find_element = AsyncMock(side_effect=_find_side_effect)

        with _patch_driver(tool, mock_driver):
            result = await tool.execute(
                keyword="金台", door_number="1号", name="张", phone="138",
            )

        assert result.success is False
        assert "无结果" in result.error

    async def test_save_button_not_found(self, tool, mock_driver):
        # 保存按钮找不到
        async def _click_text_side_effect(text, timeout=5.0):
            if text == "保存":
                return False
            return True

        mock_driver.click_text = AsyncMock(side_effect=_click_text_side_effect)

        with _patch_driver(tool, mock_driver):
            result = await tool.execute(
                keyword="金台北街",
                door_number="5号楼",
                name="时",
                phone="17600362005",
            )

        assert result.success is False
        assert "保存" in result.error
        # 即使保存失败，前面的步骤也应该记录
        assert len(result.data["steps_done"]) > 0
