# automation_u2 — uiautomator2 安卓自动化插件

通过 [python-uiautomator2](https://github.com/openatx/uiautomator2) 控制 Android 设备，为采购 Agent 等提供 UI 自动化能力。

## 环境要求

| 项目 | 要求 |
|------|------|
| 电脑 | macOS / Linux / Windows，已安装 ADB |
| 手机 | Android 5.0+，已开启 USB 调试 |
| Python | 3.11+，已安装 `uiautomator2` |

## 1. 安装 ADB

```bash
# macOS
brew install android-platform-tools

# Ubuntu/Debian
sudo apt install adb

# Windows
# 下载 https://developer.android.com/tools/releases/platform-tools 并加入 PATH
```

## 2. 手机开启 USB 调试

1. 打开「设置」→「关于手机」→ 连续点击「版本号」7 次，开启开发者模式
2. 返回「设置」→「开发者选项」→ 打开「USB 调试」
3. USB 数据线连接电脑
4. 手机弹出授权窗口，勾选「始终允许」并确认

## 3. 确认 ADB 连接

```bash
adb devices
```

输出示例：
```
List of devices attached
XXXXXXXX    device
```

如果显示 `unauthorized`，检查手机是否已授权调试。

## 4. 初始化 u2（仅首次）

u2 需要在手机上安装 ATX agent：

```bash
source .venv/bin/activate
python -m uiautomator2 init
```

完成后手机上会出现一个「ATX」图标。此步骤仅需执行一次。

## 5. 验证连接

```bash
source .venv/bin/activate
python -c "
import uiautomator2 as u2
d = u2.connect()  # USB 自动发现
print('设备:', d.device_info.get('productName'))
print('Android:', d.device_info.get('sdkInt'))
print('分辨率:', d.window_size())
print('当前APP:', d.app_current())
"
```

## 6. 测试盒马自动化

```bash
source .venv/bin/activate
python -c "
import uiautomator2 as u2
d = u2.connect()

# 启动盒马
d.app_start('com.wudaokou.hippo')
import time; time.sleep(3)

# 截图查看当前界面
d.screenshot('hema_screen.png')
print('截图已保存: hema_screen.png')

# 列出当前界面所有可点击元素
for el in d(clickable=True):
    info = el.info
    print(f'  {info[\"className\"]} | text={info.get(\"text\",\"\")} | id={info.get(\"resourceName\",\"\")}')
"
```

## 7. WiFi 无线连接（可选）

手机和电脑在同一局域网时，可以不用 USB 线：

```bash
# 获取手机 IP（先通过 USB 连接）
adb shell ip addr show wlan0 | grep "inet "

# WiFi 连接
python -c "
import uiautomator2 as u2
d = u2.connect('192.168.x.x')  # 替换为手机 IP
print(d.device_info)
"
```

WiFi 模式需要手机上的 ATX agent 保持运行（打开 ATX app 点击「启动」）。

## 8. 配置插件

在 `config.yaml` 中配置：

```yaml
plugins:
  extensions:
    - automation_u2

plugin_config:
  automation_u2:
    device_addr: ""          # 留空=USB自动发现，填IP=WiFi连接
    connect_timeout: 10      # 连接超时（秒）
```

## 9. 通过 API 管理连接

插件启动后注册了两个 API：

```bash
# 查看连接状态
curl http://localhost:8000/api/u2/status

# 手动连接设备（支持切换地址）
curl -X POST "http://localhost:8000/api/u2/connect?addr=192.168.1.100"
```

## 常见问题

### ATX agent 安装失败
- 确认手机已授权 USB 调试
- 部分手机需要关闭「USB 安装监控」或「安全设置」中的安装拦截
- 尝试 `adb install` 手动安装 APK（从 [ATX releases](https://github.com/openatx/atx-agent/releases) 下载）

### `connect()` 超时
- USB 模式：检查 `adb devices` 是否正常
- WiFi 模式：确认手机 ATX agent 已启动，且防火墙未拦截 7912 端口

### 操作盒马时元素找不到
- 盒马版本更新可能导致 resource_id 或布局变化
- 用 `d.dump_hierarchy()` 导出当前界面 XML 分析元素结构
- 用 `weditor` 可视化查看界面：`python -m weditor`
