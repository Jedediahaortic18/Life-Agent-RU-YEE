# Life-Agent-RU-YEE 前端 Demo 设计文档

## 概述

为 Life-Agent-RU-YEE 开源框架构建一个移动优先、桌面兼容的前端 Demo 展示页，让开发者快速体验 Agent 对话能力，直观感受 SSE 流式输出、Tool 调用过程和设备网关实时通信等核心特性。

## 目标与约束

- **目标用户**：开发者，快速体验框架能力
- **设备优先级**：移动优先，桌面可用
- **技术栈**：Vue 3 + Vite + TailwindCSS + TypeScript
- **架构**：单 SPA + Vue Router，2-3 个页面
- **原则**：最小依赖、轻量展示、YAGNI

## 项目结构

```
web/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── src/
│   ├── main.ts                    # 入口
│   ├── App.vue                    # 根组件 + 底部导航
│   ├── router/index.ts            # Vue Router
│   ├── api/                       # 后端 API 封装
│   │   ├── chat.ts                # SSE 流式 + 同步聊天
│   │   ├── plugins.ts             # 插件列表
│   │   ├── devices.ts             # WebSocket 设备通信
│   │   └── health.ts
│   ├── composables/               # 组合式函数
│   │   ├── useChat.ts             # 聊天状态管理
│   │   ├── useSSE.ts              # SSE 事件流处理
│   │   └── useWebSocket.ts        # WebSocket 连接管理
│   ├── views/
│   │   ├── ChatView.vue           # 聊天主界面
│   │   ├── DevicesView.vue        # 设备网关 Demo
│   │   └── PluginsView.vue        # 插件列表
│   ├── components/
│   │   ├── chat/
│   │   │   ├── MessageBubble.vue  # 消息气泡
│   │   │   ├── ToolCallCard.vue   # Tool 调用展示卡片
│   │   │   └── StreamingText.vue  # 流式文字渲染
│   │   ├── devices/
│   │   │   └── DeviceCard.vue     # 设备状态卡片
│   │   ├── BottomNav.vue          # 移动端底部导航
│   │   └── AppHeader.vue          # 顶部栏
│   └── styles/
│       └── main.css               # Tailwind 入口
```

## 页面设计

### 1. 聊天主界面 (`/`)

核心展示页面，全屏聊天布局。

**布局**：
- 顶部：Agent 名称 + 状态指示（通过 `GET /api/health` 轮询判断在线/离线，间隔 10s）
- 中间：消息列表，自动滚动
- 底部：输入框 + 发送按钮，固定定位

**SSE 流式渲染**：
- `useSSE.ts` 用 `fetch` + `ReadableStream` 解析 SSE 格式（标准 `EventSource` 不支持 POST）
- `text_delta` → 逐字追加到当前消息气泡，打字机效果
- `tool_call` → 插入 ToolCallCard，展示工具名称和参数（折叠态）
- `tool_output` → 更新对应 ToolCallCard，展示返回结果（可展开查看详情）
- `done` → 结束流式状态
- `error` → 显示错误提示
- `tool_error` → 更新对应 ToolCallCard 为错误状态，展示工具名和错误信息

**消息类型**：
- 用户消息：右对齐气泡
- Agent 文字回复：左对齐气泡，Markdown 渲染（`marked` 库）
- Tool 调用：左侧内嵌卡片，图标 + 工具名 + 折叠参数/结果

**状态管理**：`useChat.ts` 用 `ref` 管理消息数组，不引入 Pinia。

### 2. 设备网关 Demo (`/devices`)

框架亮点功能展示。

**布局**：
- 顶部：已连接设备数量统计
- 中间：设备卡片列表（设备名称、类型、在线状态、最后心跳时间）
- 底部：模拟发送消息面板（选择设备 → 输入消息 → 发送）

**WebSocket 连接**：
- `useWebSocket.ts` 连接 `ws://host/api/devices/ws`
- 实时接收设备上下线通知、心跳更新
- 断线自动重连（指数退避，最多 5 次）

**交互**：
- 设备卡片：绿色/灰色圆点标识在线/离线
- 点击设备卡片：展开详情（设备属性、消息历史）
- 模拟面板：向指定设备发消息，实时看到回复
- 页面顶部说明文字，引导开发者理解实时设备通信能力

### 3. 插件列表 (`/plugins`)

纯展示页面，不提供加载/卸载操作。

**布局**：
- 卡片列表，每张卡片包含：
  - 名称
  - 类型标签（agent/memory/search/extension），彩色区分
  - 版本号
  - 状态标签：loaded 绿色、unloaded 灰色
  - capabilities 列表

## 部署方案

### Docker 集成

`docker-compose.yml` 新增 nginx 服务：

```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
  volumes:
    - ./web/dist:/usr/share/nginx/html
    - ./nginx.conf:/etc/nginx/conf.d/default.conf
  depends_on:
    - app
```

nginx 职责：
- 托管 `web/dist/` 静态文件，监听 80 端口
- `/api/*` 反向代理到 FastAPI（8000）
- `/api/devices/ws` WebSocket 反向代理
- 前端通过相对路径 `/api/` 请求后端

### 开发模式

```bash
cd web && npm run dev    # Vite dev server，端口 5173
```

`vite.config.ts` 配置 proxy：
- `/api` → `http://localhost:8000`（Docker 映射到宿主机 8001 时改为 `http://localhost:8001`）

## 错误处理

- SSE 连接失败 → 聊天界面顶部 toast 提示"连接失败，请检查后端服务"，附重试按钮
- WebSocket 断线 → 设备页显示"连接中断"横幅，自动重连中显示加载动画
- API 请求失败 → 各页面就地展示错误状态（非全局弹窗），保持上下文

## 依赖清单

核心依赖（最小化）：
- `vue` 3
- `vue-router`
- `marked`（Markdown 渲染）
- `tailwindcss` + `postcss` + `autoprefixer`

不引入 UI 组件库，TailwindCSS 手写移动优先样式。

## 测试策略

- **单元测试**：Vitest 测试 composables（useChat、useSSE、useWebSocket 的状态逻辑）
- **组件测试**：`@vue/test-utils` 测试关键组件（MessageBubble 渲染、ToolCallCard 折叠展开）
- **不做 E2E**：Demo 级别，手动验证即可

## 后端 API 对接

前端仅使用以下端点：

| 端点 | 方法 | 前端用途 |
|------|------|----------|
| `/api/chat` | POST (SSE) | 聊天页流式对话 |
| `/api/plugins` | GET | 插件页列表展示 |
| `/api/health` | GET | 聊天页顶部在线/离线状态指示（轮询，间隔 10s） |
| `/api/devices/ws` | WebSocket | 设备页实时通信 |

> 注：后端还提供 `POST /api/chat/sync`、`POST /api/plugins/{name}/load|unload|reload` 等端点，但 Demo 前端不使用。`api/plugins.ts` 仅封装 `GET /api/plugins`。

### 请求/响应契约

#### POST /api/chat（SSE 流式）

请求体：
```json
{ "message": "帮我推荐3道低卡午餐", "session_id": "optional-uuid" }
```

SSE 事件流：
```
event: text_delta
data: {"content": "..."}

event: tool_call
data: {"tool": "dish_query", "params": {"keyword": "低卡"}}

event: tool_output
data: {"tool": "dish_query", "result": {"success": true, "data": [...], "error": null}}

event: done
data: {"session_id": "uuid", "agent": "meal_agent"}

event: error
data: {"error": "连接失败", "suggestion": "请检查 LLM provider 配置"}
```

#### GET /api/plugins

响应体：
```json
{
  "success": true,
  "data": [
    {
      "name": "meal_agent",
      "type": "agent",
      "version": "0.1.0",
      "status": "loaded",
      "capabilities": ["meal_planning", "nutrition_calculation", "dish_recommendation"]
    }
  ]
}
```

#### GET /api/health

响应体：
```json
{ "status": "ok", "service": "Life-Agent-RU-YEE", "version": "0.1.0" }
```

### WebSocket 消息协议（`/api/devices/ws`）

消息格式统一为 `MessageEnvelope`（与后端 `protocol.py` 对齐）：

```typescript
interface MessageEnvelope {
  id: string                    // UUID，后端自动生成
  type: "chat" | "heartbeat" | "device_command" | "device_result" | "device_register" | "device_registered" | "error"
  device_id: string | null
  payload: Record<string, any>
  timestamp: string             // ISO 8601
  ack_required: boolean         // 默认 false，前端收到 true 时无需回复（Demo 忽略 ACK）
}
```

**接收消息**：
- `device_registered`：设备注册成功确认
- `heartbeat`：心跳更新，payload 含 `{ status: "online" | "offline" }`
- `device_result`：设备返回的执行结果
- `error`：错误消息

**发送消息**（模拟面板使用）：
- `device_command`：向指定设备发送命令，如 `{ type: "device_command", device_id: "xxx", payload: { action: "query", data: "..." } }`

> 注：`chat` 类型消息用于设备间聊天，Demo 中不主动使用，但前端应能接收并展示。

**设备数据结构**：
```typescript
interface Device {
  device_id: string
  name: string
  device_type: string
  status: "online" | "offline"
  last_heartbeat: string  // ISO 8601
  capabilities: string[]
}
```

## TypeScript 核心类型

```typescript
// 消息类型
interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: number
  toolCalls?: ToolCallInfo[]
}

interface ToolCallInfo {
  tool: string
  params: Record<string, any>
  result?: { success: boolean; data: any; error: string | null }
  collapsed: boolean
}

// SSE 事件（discriminated union）
type SSEEvent =
  | { event: "text_delta"; data: { content: string } }
  | { event: "tool_call"; data: { tool: string; params: Record<string, any> } }
  | { event: "tool_output"; data: { tool: string; result: { success: boolean; data: any; error: string | null } } }
  | { event: "tool_error"; data: { tool: string; error: string } }
  | { event: "done"; data: { session_id: string; agent: string } }
  | { event: "error"; data: { error: string; suggestion?: string } }

// 插件
interface Plugin {
  name: string
  type: "agent" | "memory" | "search" | "extension"
  version: string
  status: "loaded" | "unloaded"
  capabilities: string[]
}
```
