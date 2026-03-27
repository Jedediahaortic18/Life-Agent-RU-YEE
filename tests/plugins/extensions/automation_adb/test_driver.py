"""AdbAutomationDriver 单元测试"""
from unittest.mock import AsyncMock, patch

import pytest

from core.interfaces.automation import ElementInfo
from plugins.extensions.automation_adb.adb_client import AdbClient, AdbError
from plugins.extensions.automation_adb.driver import AdbAutomationDriver, _parse_ui_xml, _parse_bounds


SAMPLE_UI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]" clickable="false" enabled="true">
    <node index="0" text="搜索" resource-id="com.wudaokou.hippo:id/search_bar" class="android.widget.TextView" bounds="[100,200][400,260]" clickable="true" enabled="true" />
    <node index="1" text="购物车" resource-id="com.wudaokou.hippo:id/tab_cart" class="android.widget.TextView" bounds="[800,2300][1000,2380]" clickable="true" enabled="true" />
    <node index="2" text="白菜" resource-id="com.wudaokou.hippo:id/product_name" class="android.widget.TextView" bounds="[50,400][500,460]" clickable="false" enabled="true" />
  </node>
</hierarchy>"""


@pytest.fixture
def mock_adb():
    return AsyncMock(spec=AdbClient)


@pytest.fixture
def driver(mock_adb):
    return AdbAutomationDriver(mock_adb)


class TestParseBounds:
    def test_valid(self):
        assert _parse_bounds("[100,200][300,400]") == (100, 200, 300, 400)

    def test_invalid(self):
        assert _parse_bounds("invalid") == (0, 0, 0, 0)

    def test_empty(self):
        assert _parse_bounds("") == (0, 0, 0, 0)


class TestParseUiXml:
    def test_find_by_text(self):
        results = _parse_ui_xml(SAMPLE_UI_XML, text="搜索")
        assert len(results) == 1
        assert results[0].text == "搜索"
        assert results[0].clickable is True
        assert results[0].bounds == (100, 200, 400, 260)

    def test_find_by_resource_id(self):
        results = _parse_ui_xml(SAMPLE_UI_XML, resource_id="tab_cart")
        assert len(results) == 1
        assert results[0].text == "购物车"

    def test_find_by_class(self):
        results = _parse_ui_xml(SAMPLE_UI_XML, class_name="TextView")
        assert len(results) == 3

    def test_no_match(self):
        results = _parse_ui_xml(SAMPLE_UI_XML, text="不存在的元素")
        assert results == []

    def test_with_noise_before_xml(self):
        noisy = "UI hierchary dumped to: /dev/tty\n" + SAMPLE_UI_XML
        results = _parse_ui_xml(noisy, text="白菜")
        assert len(results) == 1
        assert results[0].text == "白菜"

    def test_invalid_xml(self):
        results = _parse_ui_xml("not xml at all")
        assert results == []


class TestDriverLaunchApp:
    async def test_success(self, driver, mock_adb):
        mock_adb.start_activity.return_value = "Starting..."
        assert await driver.launch_app("com.example.app") is True
        mock_adb.start_activity.assert_called_once_with("com.example.app", None)

    async def test_with_activity(self, driver, mock_adb):
        mock_adb.start_activity.return_value = "Starting..."
        assert await driver.launch_app("com.example.app", ".MainActivity") is True
        mock_adb.start_activity.assert_called_once_with("com.example.app", ".MainActivity")

    async def test_failure(self, driver, mock_adb):
        mock_adb.start_activity.side_effect = AdbError("not found")
        assert await driver.launch_app("bad.package") is False


class TestDriverTap:
    async def test_success(self, driver, mock_adb):
        mock_adb.input_tap.return_value = ""
        assert await driver.tap(500, 800) is True
        mock_adb.input_tap.assert_called_once_with(500, 800)


class TestDriverInputText:
    async def test_ascii(self, driver, mock_adb):
        mock_adb.input_text.return_value = ""
        assert await driver.input_text("hello") is True
        mock_adb.input_text.assert_called_once_with("hello")

    async def test_cjk_uses_broadcast(self, driver, mock_adb):
        mock_adb.broadcast_text.return_value = ""
        assert await driver.input_text("白菜") is True
        mock_adb.broadcast_text.assert_called_once_with("白菜")


class TestDriverFindElement:
    async def test_find_success(self, driver, mock_adb):
        mock_adb.dump_ui.return_value = SAMPLE_UI_XML
        results = await driver.find_element(text="搜索")
        assert len(results) == 1
        assert results[0].text == "搜索"

    async def test_find_adb_error(self, driver, mock_adb):
        mock_adb.dump_ui.side_effect = AdbError("timeout")
        results = await driver.find_element(text="搜索")
        assert results == []


class TestDriverScreenshot:
    async def test_screenshot(self, driver, mock_adb):
        mock_adb.screencap.return_value = b"\x89PNG..."
        result = await driver.screenshot()
        assert result == b"\x89PNG..."
