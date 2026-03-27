"""共享辅助：获取 AutomationDriver 实例"""
from __future__ import annotations

from typing import TYPE_CHECKING

from plugins.agents.purchasing_agent.tools._constants import (
    HEMA_PACKAGE, KEYCODE_BACK,
    RID_HOME_LOCATION_LAYOUT, RID_SEARCH_EDITTEXT,
    RID_CLOSE_BUTTONS, CLOSE_BUTTON_TEXTS,
    APP_SPLASH_WAIT,
)

if TYPE_CHECKING:
    from core.interfaces.automation import AutomationDriver
    from core.plugin_registry import PluginRegistry


class DeviceNotConnectedError(Exception):
    """设备未连接时抛出，携带用户友好的提示信息"""
    pass


DEVICE_ERROR_HINT = (
    "📱 安卓设备未连接，无法执行手机操作。\n"
    "请按以下步骤排查：\n\n"
    "【方式一：WiFi 连接】\n"
    "1. 确认手机和服务器在同一局域网内\n"
    "2. 确认手机上 ATX agent 正在运行（状态栏有小图标）\n"
    "3. 在 config.yaml 中设置 automation_u2.device_addr 为手机的局域网 IP\n"
    "4. 尝试手动重连：POST /api/u2/connect?addr=手机IP\n\n"
    "【方式二：USB 数据线连接】\n"
    "1. 用数据线将手机连接到服务器\n"
    "2. 手机开启「开发者选项」→「USB 调试」\n"
    "3. 运行 adb devices 确认设备已识别\n"
    "4. 将 config.yaml 中 automation_u2.device_addr 留空即可自动发现\n\n"
    "【首次使用需初始化】\n"
    "• USB 连接手机后执行: python -m uiautomator2 init\n\n"
    "【未安装 adb？】\n"
    "• macOS: brew install android-platform-tools\n"
    "• Ubuntu/Debian: sudo apt install adb\n"
    "• Windows: https://developer.android.com/tools/releases/platform-tools 下载解压并加入 PATH"
)


async def get_automation_driver(registry: "PluginRegistry") -> "AutomationDriver":
    """从 PluginRegistry 获取 automation driver 实例，连接异常时抛出 DeviceNotConnectedError"""
    instance = registry.get_instance("automation_u2")
    if instance is None:
        raise DeviceNotConnectedError(DEVICE_ERROR_HINT)

    driver = getattr(instance, "driver", None)
    if driver is None:
        raise DeviceNotConnectedError(DEVICE_ERROR_HINT)

    # 健康检查：确认设备连接存活
    try:
        alive = await driver.health_check()
        if not alive:
            raise ConnectionError("device health check failed")
    except DeviceNotConnectedError:
        raise
    except Exception as exc:
        raise DeviceNotConnectedError(DEVICE_ERROR_HINT) from exc

    return driver


async def _is_hema_home(driver: "AutomationDriver") -> bool:
    """检查是否在盒马首页（地址栏可见）"""
    home_el = await driver.find_element(resource_id=RID_HOME_LOCATION_LAYOUT)
    return bool(home_el)


async def dismiss_popups(driver: "AutomationDriver", max_rounds: int = 3) -> None:
    """尝试关闭盒马常见弹窗（地址切换提示、活动广告等）。

    策略：
    1. 查找已知关闭按钮 resource_id
    2. 查找通用「我知道了」「关闭」「取消」文字按钮
    3. 多轮尝试，直到无弹窗或达上限
    """
    import asyncio

    for _ in range(max_rounds):
        dismissed = False

        # 按 resource_id 查找关闭按钮
        for rid in RID_CLOSE_BUTTONS:
            btn = await driver.find_element(resource_id=rid)
            if btn:
                try:
                    await driver.tap_element(btn[0] if isinstance(btn, list) else btn)
                    await asyncio.sleep(1)
                    dismissed = True
                    break
                except Exception:
                    pass

        if dismissed:
            continue

        # 按文字查找关闭按钮
        for text in CLOSE_BUTTON_TEXTS:
            btn = await driver.find_element(text=text)
            if btn:
                try:
                    await driver.tap_element(btn[0] if isinstance(btn, list) else btn)
                    await asyncio.sleep(1)
                    dismissed = True
                    break
                except Exception:
                    pass

        if not dismissed:
            break


async def ensure_hema_foreground(driver: "AutomationDriver") -> None:
    """确保盒马 APP 在前台首页。如果不在首页会尝试多种方式返回。"""
    import asyncio

    # 检查盒马是否已在前台
    current_pkg = ""
    try:
        current = await driver.app_current()
        current_pkg = current.get("package", "")
    except Exception:
        pass

    if current_pkg == HEMA_PACKAGE:
        # 已在前台，检查是否在首页
        if await _is_hema_home(driver):
            await dismiss_popups(driver)
            return

        # 方式1：按 back 最多 5 次尝试返回首页
        for _ in range(5):
            await driver.press_key(KEYCODE_BACK)
            await asyncio.sleep(1)
            if await _is_hema_home(driver):
                await dismiss_popups(driver)
                return

        # 方式2：尝试点击底部「首页」tab
        try:
            tabs = await driver.find_element(text="首页")
            if tabs:
                await driver.tap_element(tabs[0])
                await asyncio.sleep(2)
                if await _is_hema_home(driver):
                    await dismiss_popups(driver)
                    return
        except Exception:
            pass

        # 方式3：强制重启 APP
        try:
            await driver.app_stop(HEMA_PACKAGE)
            await asyncio.sleep(1)
        except Exception:
            pass
        await driver.launch_app(HEMA_PACKAGE)
        await asyncio.sleep(APP_SPLASH_WAIT)
        await dismiss_popups(driver)
        return

    # 不在前台，启动 APP
    launched = await driver.launch_app(HEMA_PACKAGE)
    if launched is False:
        raise DeviceNotConnectedError("启动盒马APP失败，请检查设备连接")
    await asyncio.sleep(6)  # 闪屏页需要更长时间
    await dismiss_popups(driver)


async def is_on_search_page(driver: "AutomationDriver") -> bool:
    """检查当前是否在盒马搜索/搜索结果页（搜索输入框可见）"""
    el = await driver.find_element(resource_id=RID_SEARCH_EDITTEXT)
    return bool(el)


async def scroll_down(driver: "AutomationDriver", ratio: float = 0.4) -> None:
    """向下滑动屏幕，ratio 为滑动距离占屏幕高度的比例"""
    import asyncio
    w, h = await driver.get_screen_size()
    x = w // 2
    y_start = int(h * 0.7)
    y_end = int(h * (0.7 - ratio))
    await driver.swipe(x, y_start, x, y_end, duration_ms=400)
    await asyncio.sleep(1.5)
