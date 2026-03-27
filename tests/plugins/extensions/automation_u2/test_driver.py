"""U2AutomationDriver 单元测试"""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from plugins.extensions.automation_u2.driver import U2AutomationDriver


@pytest.fixture()
def mock_device():
    """创建 mock u2 device"""
    device = MagicMock()
    device.device_info = {"productName": "Pixel", "sdkInt": 33}
    return device


@pytest.fixture()
def driver(mock_device):
    return U2AutomationDriver(mock_device)


# ── launch_app ──────────────────────────────────────


async def test_launch_app_with_activity(driver, mock_device):
    result = await driver.launch_app("com.test.app", "MainActivity")
    mock_device.app_start.assert_called_once_with("com.test.app", "MainActivity")
    assert result is True


async def test_launch_app_without_activity(driver, mock_device):
    result = await driver.launch_app("com.test.app")
    mock_device.app_start.assert_called_once_with("com.test.app")
    assert result is True


async def test_launch_app_failure(driver, mock_device):
    mock_device.app_start.side_effect = RuntimeError("device offline")
    result = await driver.launch_app("com.test.app")
    assert result is False


# ── tap ─────────────────────────────────────────────


async def test_tap(driver, mock_device):
    result = await driver.tap(100, 200)
    mock_device.click.assert_called_once_with(100, 200)
    assert result is True


async def test_tap_failure(driver, mock_device):
    mock_device.click.side_effect = RuntimeError("fail")
    result = await driver.tap(100, 200)
    assert result is False


# ── input_text ──────────────────────────────────────


async def test_input_text(driver, mock_device):
    result = await driver.input_text("你好世界")
    mock_device.send_keys.assert_called_once_with("你好世界", clear=True)
    assert result is True


async def test_input_text_failure(driver, mock_device):
    mock_device.send_keys.side_effect = RuntimeError("fail")
    result = await driver.input_text("test")
    assert result is False


# ── swipe ───────────────────────────────────────────


async def test_swipe(driver, mock_device):
    result = await driver.swipe(0, 500, 0, 100, 300)
    mock_device.swipe.assert_called_once_with(0, 500, 0, 100, 0.3)
    assert result is True


# ── screenshot ──────────────────────────────────────


async def test_screenshot(driver, mock_device):
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    mock_device.screenshot.return_value = img

    data = await driver.screenshot()
    assert isinstance(data, bytes)
    assert data[:4] == b"\x89PNG"


# ── press_key ───────────────────────────────────────


async def test_press_key_named(driver, mock_device):
    """BACK=4 应映射为 'back'"""
    result = await driver.press_key(4)
    mock_device.press.assert_called_once_with("back")
    assert result is True


async def test_press_key_raw(driver, mock_device):
    """未映射的 keycode 直接传递"""
    result = await driver.press_key(999)
    mock_device.press.assert_called_once_with(999)
    assert result is True


# ── find_element ────────────────────────────────────


async def test_find_element_empty_params(driver):
    """无参数返回空列表"""
    result = await driver.find_element()
    assert result == []


async def test_find_element_by_text(driver, mock_device):
    """按文本搜索"""
    mock_selector = MagicMock()
    mock_selector.count = 1
    mock_el = MagicMock()
    mock_el.info = {
        "text": "购买",
        "resourceName": "btn_buy",
        "className": "android.widget.Button",
        "bounds": {"left": 10, "top": 20, "right": 110, "bottom": 70},
        "clickable": True,
        "enabled": True,
    }
    mock_selector.__getitem__ = MagicMock(return_value=mock_el)
    mock_device.return_value = mock_selector

    result = await driver.find_element(text="购买")
    assert len(result) == 1
    assert result[0].text == "购买"
    assert result[0].resource_id == "btn_buy"
    assert result[0].clickable is True
    assert result[0].center == (60, 45)


async def test_find_element_no_match(driver, mock_device):
    """无匹配元素"""
    mock_selector = MagicMock()
    mock_selector.count = 0
    mock_device.return_value = mock_selector

    result = await driver.find_element(text="不存在")
    assert result == []


# ── click_text / click_resource_id ──────────────────


async def test_click_text_found(driver, mock_device):
    mock_el = MagicMock()
    mock_el.wait.return_value = True
    mock_device.return_value = mock_el

    result = await driver.click_text("确认")
    assert result is True
    mock_el.click.assert_called_once()


async def test_click_text_not_found(driver, mock_device):
    mock_el = MagicMock()
    mock_el.wait.return_value = False
    mock_device.return_value = mock_el

    result = await driver.click_text("不存在", timeout=1.0)
    assert result is False


async def test_click_resource_id_found(driver, mock_device):
    mock_el = MagicMock()
    mock_el.wait.return_value = True
    mock_device.return_value = mock_el

    result = await driver.click_resource_id("btn_confirm")
    assert result is True


# ── get_device_info ─────────────────────────────────


async def test_get_device_info(driver, mock_device):
    mock_device.device_info = {"productName": "Pixel", "sdkInt": 33}
    result = await driver.get_device_info()
    assert result == {"productName": "Pixel", "sdkInt": 33}


async def test_get_device_info_failure(driver, mock_device):
    type(mock_device).device_info = PropertyMock(side_effect=RuntimeError("fail"))
    result = await driver.get_device_info()
    assert result == {}
