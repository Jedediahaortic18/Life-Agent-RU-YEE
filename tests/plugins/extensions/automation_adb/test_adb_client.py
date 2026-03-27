"""AdbClient 单元测试"""
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from plugins.extensions.automation_adb.adb_client import AdbClient, AdbError, DeviceInfo


@pytest.fixture
def client():
    return AdbClient(device_serial="emulator-5554", adb_path="adb", timeout=5)


@pytest.fixture
def client_no_serial():
    return AdbClient()


class TestBuildCmd:
    def test_with_serial(self, client):
        cmd = client._build_cmd("devices", "-l")
        assert cmd == ["adb", "-s", "emulator-5554", "devices", "-l"]

    def test_without_serial(self, client_no_serial):
        cmd = client_no_serial._build_cmd("devices")
        assert cmd == ["adb", "devices"]


class TestShell:
    async def test_shell_success(self, client):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"OK\n", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await client.shell("echo OK")
        assert result.strip() == "OK"

    async def test_shell_error(self, client):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"error: device not found\n")
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(AdbError, match="device not found"):
                await client.shell("echo test")

    async def test_shell_timeout(self, client):
        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = asyncio.TimeoutError()
        mock_proc.kill = MagicMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(AdbError, match="timed out"):
                await client.shell("sleep 100")

    async def test_shell_binary_not_found(self, client):
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError()):
            with pytest.raises(AdbError, match="not found"):
                await client.shell("echo test")


class TestDevices:
    async def test_parse_devices(self, client):
        output = (
            "List of devices attached\n"
            "emulator-5554          device product:sdk model:Android_SDK transport_id:1\n"
            "192.168.1.100:5555     device model:Pixel_6\n"
        )
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (output.encode(), b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            devices = await client.devices()

        assert len(devices) == 2
        assert devices[0].serial == "emulator-5554"
        assert devices[0].state == "device"
        assert devices[0].model == "Android_SDK"
        assert devices[1].serial == "192.168.1.100:5555"
        assert devices[1].model == "Pixel_6"

    async def test_no_devices(self, client):
        output = "List of devices attached\n\n"
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (output.encode(), b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            devices = await client.devices()

        assert devices == []


class TestIsConnected:
    async def test_connected_with_serial(self, client):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (
            b"List of devices attached\nemulator-5554\tdevice\n", b""
        )
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            assert await client.is_connected() is True

    async def test_not_connected(self, client):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"List of devices attached\n\n", b"")
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            assert await client.is_connected() is False
