"""AutomationU2Extension 单元测试"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plugins.extensions.automation_u2.extension import AutomationU2Extension


@pytest.fixture()
def ext():
    return AutomationU2Extension()


def test_init(ext):
    assert ext.driver is None
    assert ext._device is None
    assert ext._device_addr == ""


async def test_on_unload(ext):
    ext.driver = MagicMock()
    ext._device = MagicMock()

    await ext.on_unload()

    assert ext.driver is None
    assert ext._device is None


def test_connect_device_with_addr(ext):
    mock_u2 = MagicMock()
    mock_device = MagicMock()
    mock_device.device_info = {"productName": "Test", "sdkInt": 30}
    mock_u2.connect.return_value = mock_device

    ext._connect_device(mock_u2, "192.168.1.100")

    mock_u2.connect.assert_called_once_with("192.168.1.100")
    assert ext._device is mock_device
    assert ext.driver is not None


def test_connect_device_auto(ext):
    mock_u2 = MagicMock()
    mock_device = MagicMock()
    mock_device.device_info = {"productName": "Auto", "sdkInt": 31}
    mock_u2.connect.return_value = mock_device

    ext._connect_device(mock_u2, "")

    mock_u2.connect.assert_called_once_with()
    assert ext._device is mock_device


def test_connect_device_failure(ext):
    mock_u2 = MagicMock()
    mock_u2.connect.side_effect = ConnectionError("device not found")

    with pytest.raises(ConnectionError):
        ext._connect_device(mock_u2, "bad_addr")


async def test_on_load_registers_routes(ext):
    """验证 on_load 注册了 API 路由"""
    mock_app = MagicMock()
    mock_registry = MagicMock()
    mock_manifest = MagicMock()
    mock_manifest._config = {"device_addr": "10.0.0.1", "connect_timeout": 5}
    mock_registry.get_manifest.return_value = mock_manifest

    with patch("uiautomator2.connect", side_effect=ConnectionError("no device")):
        await ext.on_load(mock_app, mock_registry)

    # 应该调用了 include_router
    mock_app.include_router.assert_called_once()
    call_kwargs = mock_app.include_router.call_args
    assert call_kwargs[1]["prefix"] == "/api" or call_kwargs.kwargs.get("prefix") == "/api"

    # config 应被正确读取
    assert ext._device_addr == "10.0.0.1"
