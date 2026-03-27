"""AdbClient - 底层 ADB 命令封装"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from loguru import logger


class AdbError(Exception):
    """ADB 命令执行错误"""


@dataclass
class DeviceInfo:
    serial: str
    state: str  # device | offline | unauthorized
    model: str = ""


class AdbClient:
    """通过 subprocess 调用 adb 二进制的低级客户端"""

    def __init__(
        self,
        device_serial: str = "",
        adb_path: str = "adb",
        timeout: int = 10,
    ) -> None:
        self._serial = device_serial
        self._adb = adb_path
        self._timeout = timeout

    def _build_cmd(self, *args: str) -> list[str]:
        """构建 adb 命令"""
        cmd = [self._adb]
        if self._serial:
            cmd.extend(["-s", self._serial])
        cmd.extend(args)
        return cmd

    async def _run(self, *args: str, timeout: int | None = None) -> str:
        """执行 adb 命令并返回 stdout"""
        cmd = self._build_cmd(*args)
        effective_timeout = timeout or self._timeout

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise AdbError(f"ADB command timed out ({effective_timeout}s): {' '.join(cmd)}")
        except FileNotFoundError:
            raise AdbError(f"ADB binary not found: {self._adb}")

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise AdbError(f"ADB error (exit {proc.returncode}): {err_msg}")

        return stdout.decode("utf-8", errors="replace")

    async def _run_bytes(self, *args: str, timeout: int | None = None) -> bytes:
        """执行 adb 命令并返回原始 stdout 字节"""
        cmd = self._build_cmd(*args)
        effective_timeout = timeout or self._timeout

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise AdbError(f"ADB command timed out ({effective_timeout}s): {' '.join(cmd)}")
        except FileNotFoundError:
            raise AdbError(f"ADB binary not found: {self._adb}")

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise AdbError(f"ADB error (exit {proc.returncode}): {err_msg}")

        return stdout

    async def shell(self, cmd: str) -> str:
        """执行 adb shell 命令"""
        return await self._run("shell", cmd)

    async def devices(self) -> list[DeviceInfo]:
        """列出已连接设备"""
        output = await self._run("devices", "-l")
        result: list[DeviceInfo] = []
        for line in output.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            state = parts[1]
            model = ""
            for part in parts[2:]:
                if part.startswith("model:"):
                    model = part.split(":", 1)[1]
            result.append(DeviceInfo(serial=serial, state=state, model=model))
        return result

    async def connect(self, host: str, port: int = 5555) -> bool:
        """ADB over WiFi 连接"""
        try:
            output = await self._run("connect", f"{host}:{port}")
            return "connected" in output.lower()
        except AdbError as e:
            logger.warning(f"ADB connect failed: {e}")
            return False

    async def screencap(self) -> bytes:
        """截屏，返回 PNG 字节"""
        return await self._run_bytes("exec-out", "screencap", "-p", timeout=15)

    async def dump_ui(self) -> str:
        """导出当前界面 UI 层级 XML"""
        # 先 dump 到设备文件，再拉取内容
        await self.shell("uiautomator dump /sdcard/ui_dump.xml")
        return await self.shell("cat /sdcard/ui_dump.xml")

    async def input_tap(self, x: int, y: int) -> str:
        """点击屏幕坐标"""
        return await self.shell(f"input tap {x} {y}")

    async def input_swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300,
    ) -> str:
        """滑动"""
        return await self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    async def input_text(self, text: str) -> str:
        """输入文本（仅支持 ASCII）"""
        escaped = text.replace("'", "'\\''")
        return await self.shell(f"input text '{escaped}'")

    async def broadcast_text(self, text: str) -> str:
        """通过 ADBKeyBoard 输入中文文本"""
        escaped = text.replace("'", "'\\''")
        return await self.shell(
            f"am broadcast -a ADB_INPUT_TEXT --es msg '{escaped}'"
        )

    async def input_keyevent(self, keycode: int) -> str:
        """发送按键事件"""
        return await self.shell(f"input keyevent {keycode}")

    async def start_activity(self, package: str, activity: str | None = None) -> str:
        """启动 Activity"""
        if activity:
            return await self.shell(f"am start -n {package}/{activity}")
        return await self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    async def is_connected(self) -> bool:
        """检查设备是否连接"""
        try:
            devs = await self.devices()
            if self._serial:
                return any(d.serial == self._serial and d.state == "device" for d in devs)
            return any(d.state == "device" for d in devs)
        except AdbError:
            return False
