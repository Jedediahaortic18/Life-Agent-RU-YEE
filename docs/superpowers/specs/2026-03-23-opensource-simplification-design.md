# Life-Agent-RU-YEE 开源简化设计文档

## 概述

将现有 compass-agent 饮食规划代下单 Agent 项目简化为一个适合开源的、可插拔架构的 Agent 框架项目。聚焦饮食规划垂直场景，面向开发者，让社区能快速体验核心流程并基于框架扩展自己的 Agent。

**原始项目：** `/Users/sMacmini4/Project/dongying/AI/compass-agent`

## 设计决策摘要

| 决策项 | 选择 | 与原项目的关系 |
|--------|------|---------------|
| 核心流程 | 饮食规划垂直场景（MealAgent） | 简化自 CompassAgent + MakeUpDishTool |
| 目标用户 | 开发者（二次开发、扩展 Agent） | — |
| Agent 框架 | 基于 OpenAI Agents SDK + BaseStreamAgent（SSE 流式） | 沿用原项目架构 |
| LLM 集成 | LiteLLM 多 provider 抽象（100+ 模型） | 沿用原项目，无需自建抽象层 |
| Tool 系统 | 可插拔 Tool，每个 Agent 声明自己的 Tools | 简化自原项目 24 个 Tool |
| 记忆系统 | 三层可插拔：short_term (Redis) / long_term (Mem0) / structured (Memobase) | 沿用原项目命名和实现 |
| Prompt 系统 | Jinja2 模板渲染 | 沿用原项目 |
| 设备网关 | device_gateway（WebSocket 网关，Extension 插件） | 开源项目亮点，全新设计 |
| 数据库 | PostgreSQL + Redis（MVP），Milvus 可选插件 | 简化自 MySQL+MongoDB+Milvus+PG+Redis |
| 基础设施 | Docker Compose 一键启动 | — |
| 配置方式 | .env 多环境 + config.yaml 插件配置 | .env 沿用原项目，config.yaml 为插件新增 |
| 项目名称 | Life-Agent-RU-YEE | — |
| 开源许可 | MIT | — |

---

## 1. 整体架构与目录结构

```
Life-Agent-RU-YEE/
├── docker-compose.yml          # 一键启动全部服务
├── .env.example                # 环境变量模板
├── config.yaml                 # 插件配置（启用哪些插件、插件级参数）
├── core/                       # 核心引擎（不可移除）
│   ├── orchestrator.py         # 编排流水线
│   ├── intent_router.py        # 意图路由
│   ├── task_decomposer.py      # 任务分解（MVP 为直通模式）
│   ├── plugin_registry.py      # 插件注册表
│   ├── context_bus.py          # Agent 间通信总线
│   ├── stream.py               # SSE 流式响应基础设施
│   ├── interfaces/             # 所有插件必须实现的抽象接口
│   │   ├── agent.py            # BaseStreamAgent ABC
│   │   ├── memory.py           # BaseMemory ABC
│   │   ├── tool.py             # BaseTool 定义
│   │   └── extension.py        # BaseExtension ABC
│   └── models/                 # 核心数据模型（精简版）
│       ├── task.py
│       ├── intent.py
│       └── plugin.py
│
├── plugins/                    # 官方插件
│   ├── agents/
│   │   └── meal_agent/
│   │       ├── manifest.yaml
│   │       ├── agent.py        # 继承 BaseStreamAgent
│   │       ├── tools/          # Agent 专属 Tool
│   │       │   ├── dish_query_tool.py
│   │       │   ├── meal_recommend_tool.py
│   │       │   └── shopping_list_tool.py
│   │       └── prompts/        # Jinja2 模板
│   │           └── system.j2
│   ├── memory/
│   │   ├── short_term_memory/  # Redis 会话记忆（默认启用）
│   │   ├── long_term_memory/   # Mem0 事实记忆（可选）
│   │   └── structured_memory/  # Memobase 用户画像（可选，依赖 pgvector）
│   ├── search/
│   │   └── milvus_search/      # Milvus 向量搜索（可选插件）
│   │       ├── manifest.yaml
│   │       └── search.py
│   └── extensions/
│       └── device_gateway/     # 设备 WebSocket 网关（开源亮点）
│           ├── manifest.yaml
│           ├── gateway.py      # WebSocket 连接管理
│           ├── protocol.py     # 消息协议（MessageEnvelope）
│           ├── device_manager.py  # 设备注册与状态
│           └── README.md       # 设备接入指南
│
├── contrib/                    # 社区贡献目录
│   └── README.md
│
├── cli/                        # CLI 工具
│   └── __main__.py
│
├── docs/
│   ├── getting-started.md
│   ├── plugin-development.md
│   ├── device-gateway.md       # 设备网关接入文档
│   └── architecture.md
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── conftest.py
│
├── CONTRIBUTING.md
├── LICENSE                     # MIT
└── README.md
```

**核心原则：** core 极简（约 10 个文件），只包含编排引擎 + 接口定义 + 插件注册表 + SSE 流式基础设施。所有业务逻辑在 plugins/ 中实现。

---

## 2. 插件注册表机制

### 2.1 manifest.yaml 规范

每个插件必须包含一个 manifest 文件：

```yaml
manifest_version: 1              # manifest 格式版本，用于未来兼容
name: meal_agent
version: "0.1.0"
type: agent                      # agent | memory | search | extension
description: "AI 驱动的饮食规划 Agent"
entry_point: agent:MealAgent     # 模块:类名
dependencies:
  plugins:                       # 依赖的其他插件
    - short_term_memory
  python: ["pydantic>=2.0"]      # 额外 Python 依赖
tools:                           # Agent 类型专属：声明包含的 Tool
  - tools/dish_query_tool.py:DishQueryTool
  - tools/meal_recommend_tool.py:MealRecommendTool
  - tools/shopping_list_tool.py:ShoppingListTool
config_schema:                   # 该插件可接受的配置项
  cuisine_styles:
    type: list
    default: ["中餐", "西餐"]
```

### 2.2 PluginRegistry 核心流程

**启动时：**

1. 加载 `.env` 环境变量（LLM API Key、数据库连接等）
2. 验证 `config.yaml` schema 合法性（类型检查、引用插件是否存在），失败时输出可操作的错误信息并终止
3. 扫描 `plugins/` 和 `contrib/` 下所有 `manifest.yaml`
4. 读取 `config.yaml` 中的 enabled 列表
5. 拓扑排序（按 dependencies）— 检测到循环依赖时输出清晰错误（列出环路）并终止启动
6. 依次加载：导入模块 -> 实例化 -> 验证接口 -> 注册
7. 对 Agent 类型插件：同时加载其声明的 Tools

**运行时 API：**

```python
registry.get_agent("meal_agent")          # -> MealAgent 实例
registry.get_memory("short_term_memory")  # -> ShortTermMemory 实例
registry.get_tools("meal_agent")          # -> [DishQueryTool, MealRecommendTool, ...]
registry.list_plugins(type="agent")       # -> 所有已注册 Agent
```

### 2.3 热插拔

**适用范围：** Agent、Memory、Search 类型插件支持运行时热插拔。Extension 类型（涉及路由注册）需要重启服务。

```python
# 仅适用于 agent / memory / search 类型
registry.load_plugin("contrib/agents/fitness_agent")
registry.unload_plugin("meal_agent")
registry.reload_plugin("meal_agent")  # 卸载 + 重新加载
```

- **加载：** 读取 manifest -> 检查依赖 -> 动态 import -> 注册（含 Tools）
- **卸载：** 检查无其他插件依赖它 -> 注销 -> 清理引用
- **Extension 限制：** Extension 注册了 FastAPI 路由，运行时无法安全移除，需重启服务
- **信号机制：** 加载/卸载时发出事件，其他模块可监听响应

### 2.4 配置体系

**双层配置：**

`.env`（环境变量）— 敏感信息和基础设施连接：
```bash
# LLM Provider Keys（通过 LiteLLM 统一管理）
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
# 不配置任何 Key 则自动使用 Ollama 本地模型

# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/lifeagent
REDIS_URL=redis://redis:6379/0

# 可选服务
MEM0_API_KEY=                    # 空则禁用 long_term_memory
MEMOBASE_URL=                    # 空则禁用 structured_memory
MILVUS_HOST=                     # 空则禁用 milvus_search
```

`config.yaml`（插件配置）— 插件启用和参数：
```yaml
server:
  host: "0.0.0.0"
  port: 8000

plugins:
  agents:
    - meal_agent
  memory:
    - short_term_memory
  search: []
  extensions:
    - device_gateway

llm:
  default_model: ollama/phi3:mini    # LiteLLM 模型格式
  fallback_model: null               # 可选降级模型
  max_tokens_per_request: 4096
  temperature: 0.7

logging:
  level: INFO                        # DEBUG | INFO | WARNING | ERROR
  format: json                       # json | text

plugin_config:
  meal_agent:
    cuisine_styles: ["中餐", "日料", "东南亚"]
  short_term_memory:
    max_turns: 30
    ttl_hours: 2
  device_gateway:
    heartbeat_interval: 30           # 秒
    max_connections: 100
```

### 2.5 插件安全声明

社区贡献的插件（`contrib/`）运行在与主进程相同的 Python 环境中，无沙箱隔离。这是 MVP 的已知限制。

缓解措施：
- CI 自动扫描硬编码密钥
- 插件贡献需要 Code Review 审批
- README 中明确告知风险

未来考虑：subprocess 隔离、受限 import 白名单。

---

## 3. 核心接口定义

### 3.1 LLM 集成（LiteLLM）

**不自建抽象层**，直接使用 LiteLLM 作为 LLM 统一接口：

```python
import litellm

# LiteLLM 统一调用，自动路由到正确的 provider
response = await litellm.acompletion(
    model="ollama/phi3:mini",        # 或 "claude-sonnet-4-20250514", "gpt-4o" 等
    messages=[{"role": "user", "content": "..."}],
    stream=True
)
```

**provider 自动发现：** LiteLLM 根据环境变量中配置的 API Key 自动识别可用 provider。不配置任何 Key 时默认使用 Ollama 本地模型。

**Failover 机制：** 通过 config.yaml 的 `fallback_model` 配置，调用失败时自动切换。

### 3.2 BaseStreamAgent

沿用原项目的 SSE 流式 Agent 架构：

```python
class BaseStreamAgent(ABC):
    """流式 Agent 基类，支持 SSE 事件流和 Tool 调用"""

    def __init__(self, context_bus: ContextBus, config: dict): ...

    @abstractmethod
    def get_system_prompt(self, context: dict) -> str:
        """返回 Jinja2 渲染后的 system prompt"""
        ...

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        """返回该 Agent 可用的 Tool 列表"""
        ...

    @abstractmethod
    def get_model(self) -> str:
        """返回 LiteLLM 模型标识符"""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """声明能力标签，供 IntentRouter 动态匹配"""
        ...

    async def run(self, user_message: str, session_id: str) -> AsyncIterator[SSEEvent]:
        """
        执行 Agent，返回 SSE 事件流。
        事件类型：text_delta | tool_call | tool_output | done | error
        """
        ...
```

**与原项目 BaseStreamAgent 的对应：**
- `get_system_prompt` → 原项目的 Jinja2 prompt 模板渲染
- `get_tools` → 原项目的 function_tools 列表
- `get_model` → 原项目的 ModelConfig 选择
- `run` → 原项目的 SSE streaming + tool call handling
- 新增 `capabilities` 属性供插件化路由使用

### 3.3 BaseTool

```python
class BaseTool(ABC):
    """Agent Tool 基类，基于 Pydantic schema"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        """JSON Schema 格式的参数定义"""
        ...

    @abstractmethod
    async def execute(self, **params) -> ToolResult: ...
```

沿用原项目的 Pydantic function_tool 模式，每个 Tool 是独立文件，通过 manifest.yaml 声明归属。

### 3.4 BaseMemory

```python
class BaseMemory(ABC):
    @abstractmethod
    async def store(self, key: str, value: Any, **metadata) -> None: ...

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryItem]: ...

    @abstractmethod
    async def retrieve_recent(self, n: int = 10) -> list[MemoryItem]:
        """获取最近 N 条记录，ShortTermMemory 的主要检索方式"""
        ...

    @abstractmethod
    async def clear(self, scope: str = "session") -> None: ...
```

三个实现对齐原项目命名：
- **short_term_memory** — Redis 会话记忆（对应原项目 ShortTermMemory），`retrieve_recent` 为主要使用方式
- **long_term_memory** — Mem0 事实记忆（对应原项目 LongTermMemory），`retrieve` 使用语义相似度搜索
- **structured_memory** — Memobase 用户画像（对应原项目 MemobaseMemory），依赖 pgvector

### 3.5 ContextBus

```python
class ContextBus:
    """Agent 间通信总线。默认内存实现，作用域为单次请求。可配置 Redis 后端实现跨请求持久化。"""

    async def write(self, agent_id: str, slot: str, data: Any) -> None: ...
    async def read(self, agent_id: str, slot: str) -> Any: ...
    async def subscribe(self, slot_pattern: str, callback: Callable[[str, str, Any], None]) -> None:
        """
        监听 slot 写入事件。
        - slot_pattern: 支持通配符，如 "meal_agent/*" 或 "*"
        - callback(agent_id, slot, data): 写入时触发
        - 投递保证: at-most-once（内存实现）
        """
        ...
```

- **默认实现：** 内存字典，作用域为单次请求生命周期，请求结束后清理
- **可选 Redis 实现：** 通过 config.yaml 切换，支持跨请求持久化

### 3.6 BaseExtension

```python
class BaseExtension(ABC):
    @abstractmethod
    async def on_load(self, app: FastAPI, registry: PluginRegistry) -> None:
        """加载时挂载路由、WebSocket 等。Extension 加载后需重启才能卸载。"""
        ...

    @abstractmethod
    async def on_unload(self) -> None: ...
```

---

## 4. Device Gateway（开源亮点）

### 4.1 定位

device_gateway 是一个 Extension 插件，提供 **WebSocket 设备网关**，允许外部设备（手机、IoT、桌面客户端）与 Agent 系统实时双向通信。这是开源项目的差异化亮点——不仅是 API 调用，而是支持设备级的自动化指令下发和状态回报。

### 4.2 核心能力

```
外部设备 ←── WebSocket ──→ Device Gateway ←── ContextBus ──→ Agent 系统
                              │
                              ├── 设备注册与认证
                              ├── 心跳保活与断线重连
                              ├── 消息协议（MessageEnvelope）
                              ├── 指令下发与结果回收
                              └── 设备状态管理
```

### 4.3 消息协议

```python
class MessageEnvelope:
    id: str                    # UUID
    type: MessageType          # CHAT | HEARTBEAT | DEVICE_COMMAND | DEVICE_RESULT | DEVICE_REGISTER
    payload: dict
    timestamp: datetime
    device_id: str | None
    ack_required: bool
```

### 4.4 API 端点（Extension 注册）

```
WS  /ws/device                    # 设备 WebSocket 连接
POST /api/devices/register        # 设备注册
GET  /api/devices                 # 已连接设备列表
POST /api/devices/{id}/command    # 向设备下发指令
GET  /api/devices/{id}/status     # 设备状态查询
```

### 4.5 开发者扩展场景

- 连接手机 App → Agent 生成菜单后推送到手机
- 连接智能家居 → Agent 规划做饭时间后控制厨房设备
- 连接桌面客户端 → 实时展示 Agent 推理过程
- 社区可基于 device_gateway 协议开发任意客户端

---

## 5. HTTP API 定义

### 5.1 核心端点

```
POST /api/chat                    # 主对话端点（SSE 流式响应）
POST /api/chat/sync               # 同步对话（等待完整结果）
GET  /api/chat/history            # 获取对话历史
GET  /api/plugins                 # 列出已加载插件
POST /api/plugins/{name}/load     # 热加载插件
POST /api/plugins/{name}/unload   # 卸载插件
POST /api/plugins/{name}/reload   # 重载插件
GET  /api/health                  # 健康检查
POST /api/memory/maintenance      # 手动触发记忆维护
```

### 5.2 请求/响应格式

**POST /api/chat（SSE 流式）**

请求：
```json
{
  "message": "帮我规划一周的减脂餐",
  "session_id": "optional-session-id"
}
```

SSE 事件流：
```
event: text_delta
data: {"content": "好的，"}

event: text_delta
data: {"content": "我来为您规划..."}

event: tool_call
data: {"tool": "meal_recommend", "params": {"days": 7, "goal": "减脂"}}

event: tool_output
data: {"tool": "meal_recommend", "result": {"meals": [...]}}

event: done
data: {"session_id": "abc-123", "agent": "meal_agent"}
```

**POST /api/chat/sync（同步响应）**

响应：
```json
{
  "success": true,
  "data": {
    "session_id": "abc-123",
    "agent": "meal_agent",
    "result": {
      "meals": [...],
      "shopping_list": [...],
      "summary": "已为您生成 7 天减脂餐计划..."
    }
  }
}
```

**错误响应（统一格式）：**
```json
{
  "success": false,
  "error": "MealAgent 执行失败: LLM 服务不可用",
  "suggestion": "请检查 LLM provider 配置，确保 Ollama 正在运行"
}
```

---

## 6. IntentRouter 动态路由机制

### 6.1 Capability 声明

每个 Agent 通过 `capabilities` 属性声明能力标签：

```python
class MealAgent(BaseStreamAgent):
    @property
    def capabilities(self) -> list[str]:
        return ["meal_planning", "nutrition_calculation", "shopping_list_generation", "diet_advice"]
```

### 6.2 动态路由 Prompt 生成

IntentRouter 启动时（或 Agent 热加载后）从 Registry 收集所有 Agent 的 capabilities，自动生成路由 prompt：

```
你是一个意图路由器。根据用户输入，选择最合适的 Agent。

可用 Agent：
- meal_agent: meal_planning, nutrition_calculation, shopping_list_generation, diet_advice
- fitness_agent: workout_planning, exercise_tracking

用户输入: "{user_message}"

返回 JSON: {"agent": "agent_name", "confidence": 0.0-1.0, "task_description": "..."}
```

### 6.3 路由规则

- **单一匹配：** confidence >= 0.6 直接分发
- **多 Agent 匹配：** 选择 confidence 最高的
- **无匹配（confidence < 0.6）：** 返回友好提示，列出当前可用能力
- **新增 Agent 时：** 无需修改核心代码，Registry 变更自动触发 prompt 重新生成

---

## 7. TaskDecomposer（MVP 直通模式）

MVP 阶段，TaskDecomposer 为直通模式——单 Agent 场景下不做分解，直接将用户意图传递给目标 Agent。

```python
class TaskDecomposer:
    async def decompose(self, intent: IntentResult) -> list[SubTask]:
        # MVP: 单 Agent 直通
        if len(self.registry.list_plugins(type="agent")) <= 1:
            return [SubTask(agent=intent.agent, description=intent.task_description)]

        # 多 Agent 场景: LLM 分解为有序子任务（未来启用）
        return await self._llm_decompose(intent)
```

当社区贡献了多个 Agent 后，TaskDecomposer 自动切换到 LLM 分解模式，按依赖关系排序子任务。

---

## 8. 数据流与错误处理

### 8.1 核心请求流程

```
POST /api/chat { message: "帮我规划一周减脂餐" }
  │
  ▼
Orchestrator.run()
  ├─ IntentRouter.route()
  │    查询 Registry 已注册 Agent capabilities
  │    → LLM 判断匹配 meal_agent (confidence: 0.92)
  │
  ├─ TaskDecomposer.decompose()
  │    → MVP 直通: [SubTask(agent="meal_agent", desc="规划一周减脂餐")]
  │
  ├─ Registry.get_agent("meal_agent").run(message, session_id)
  │    ├─ Jinja2 渲染 system prompt（注入记忆上下文）
  │    ├─ LiteLLM 流式调用
  │    ├─ Tool 调用: dish_query → meal_recommend → shopping_list
  │    ├─ ContextBus.write("meal_agent", "meals", data)
  │    └─ SSE 事件流输出
  │
  ├─ Memory.store(...)  # 可选，存储对话历史
  │
  └─ 如启用 device_gateway → 推送结果到已连接设备
```

### 8.2 与原项目的简化对比

| 原项目模块 | 开源版处理 | 原因 |
|-----------|-----------|------|
| 11 个 Agent | 保留 MealAgent | 聚焦核心场景 |
| 24 个 Tool | 保留 3 个核心 Tool | 最小可体验集 |
| MySQL + MongoDB + Milvus + PG + Redis | PostgreSQL + Redis | 统一关系型存储 |
| LiteLLM + 7 provider 配置 | LiteLLM + 按需配置 | 保留能力，简化默认配置 |
| 70 个 Entity | 6 个 Model | 最小可用集 |
| 126 个 Service | ~10 个核心 Service | 聚焦核心流程 |
| 200+ API 路由 | ~15 个端点 | 核心 + 插件管理 + 设备 |
| APScheduler 定时任务 | API 手动触发 | 减少基础设施依赖 |
| WeChat 支付 | 移除 | 非核心流程 |
| Admin Web (Vue 3) | 移除 | 开发者通过 API/CLI 交互 |
| Langfuse 可观测性 | Loguru 结构化日志 | 降低外部依赖 |
| 飞书告警 | 移除 | 非通用需求 |
| JWT 认证 | 可选 Extension 插件 | 本地体验无需认证 |

### 8.3 错误处理

- **config.yaml 校验失败** — 启动时输出具体字段错误和修复建议，终止启动
- **循环插件依赖** — 启动时输出环路路径（如 A → B → C → A），终止启动
- **插件加载失败** — 跳过并输出 WARNING 日志，不阻塞启动
- **Agent 执行失败** — 单次重试，仍失败则返回清晰 SSE error 事件
- **LLM 不可用** — 如配置了 fallback_model 则自动降级；无 fallback 时返回错误信息，提示检查 provider 状态
- **Tool 执行失败** — 返回 tool_error 事件，Agent 可决定是否继续
- **WebSocket 断线** — device_gateway 支持自动重连 + 消息队列缓冲
- **Intent 无匹配** — 返回友好提示，列出当前可用能力

### 8.4 数据模型（精简版）

| 模型 | 用途 | 对应原项目 |
|------|------|-----------|
| User | 基础用户信息（无认证时用默认用户） | user entity |
| Task | 任务记录 | — (新增) |
| PluginState | 插件状态和配置持久化 | — (新增) |
| MemoryItem | 统一记忆存储（type 字段区分三层） | 合并原项目多个记忆表 |
| ConversationTurn | 对话历史 | text_session_entity |
| DeviceConnection | 设备连接信息 | — (新增) |

6 个模型替代原项目的 70+。

### 8.5 数据库初始化

Docker 容器首次启动时，应用入口自动执行 SQLAlchemy `metadata.create_all()` 创建所有表。开源版不使用 Alembic 迁移，简化首次体验流程。

已知限制：版本升级导致 schema 变更时需手动处理。未来在 schema 稳定后引入 Alembic。

---

## 9. 开发者体验

### 9.1 快速体验

```bash
git clone https://github.com/xxx/Life-Agent-RU-YEE.git
cd Life-Agent-RU-YEE
docker compose up
```

Docker Compose 包含：
- **app** — FastAPI 主服务
- **postgres** — PostgreSQL 16
- **redis** — Redis 7
- **ollama** — 本地 LLM，默认拉取 `phi3:mini`（2.7B 参数，CPU 推理约 5-10 秒/响应）

> **性能说明：** 默认模型 `phi3:mini` 针对 CPU 推理优化。如有 NVIDIA GPU，可在 `docker-compose.yml` 中启用 GPU 直通并切换到更大模型。也可修改 `.env` 指向宿主机运行的 Ollama 实例（`host.docker.internal:11434`）获得更好性能。

> **使用云端 LLM：** 在 `.env` 中配置任意 LiteLLM 支持的 API Key（如 `OPENAI_API_KEY`），并修改 `config.yaml` 中的 `default_model` 即可切换。

### 9.2 交互入口

- **Swagger UI** — `http://localhost:8000/docs`（可视化测试 API）
- **SSE 流式体验** — 浏览器直接访问 `/api/chat` 查看实时推理
- **CLI 工具：**

```bash
docker exec -it life-agent-app python -m cli chat "帮我规划一周的减脂餐"
docker exec -it life-agent-app python -m cli plugins list
docker exec -it life-agent-app python -m cli plugins load contrib/agents/my_agent
docker exec -it life-agent-app python -m cli devices list   # 查看已连接设备
```

### 9.3 插件开发脚手架

```bash
docker exec -it life-agent-app python -m cli plugins scaffold \
  --type agent \
  --name fitness_agent \
  --output contrib/agents/fitness_agent
```

生成标准插件目录：

```
contrib/agents/fitness_agent/
├── manifest.yaml       # 预填模板
├── agent.py            # BaseStreamAgent 骨架代码
├── tools/
│   └── example_tool.py # BaseTool 骨架
├── prompts/
│   └── system.j2       # Jinja2 prompt 模板
├── tests/
│   └── test_agent.py   # 测试骨架
└── README.md
```

---

## 10. 日志与可观测性

### 10.1 结构化日志

使用 Loguru 输出结构化日志（沿用原项目），通过 `config.yaml` 配置级别：

```json
{"event": "plugin_loaded", "plugin": "meal_agent", "type": "agent", "duration_ms": 42, "level": "info"}
{"event": "llm_call", "model": "ollama/phi3:mini", "tokens": 512, "latency_ms": 3200, "level": "info"}
{"event": "tool_executed", "tool": "dish_query", "agent": "meal_agent", "duration_ms": 150, "level": "info"}
{"event": "intent_routed", "agent": "meal_agent", "confidence": 0.92, "level": "info"}
{"event": "device_connected", "device_id": "phone-001", "level": "info"}
{"event": "plugin_load_failed", "plugin": "structured_memory", "error": "memobase not configured", "level": "warning"}
```

### 10.2 关键事件

- 插件生命周期（加载、卸载、加载失败）
- LLM 调用（模型、token 数、延迟）
- Tool 执行（Tool 名、Agent、耗时）
- 意图路由结果（匹配 agent、confidence）
- Agent 执行结果（成功/失败、耗时）
- 设备网关事件（连接、断线、指令下发）
- 错误与异常

---

## 11. 测试策略

### 11.1 测试结构

```
tests/
├── unit/
│   ├── core/
│   │   ├── test_plugin_registry.py    # 注册、加载、卸载、依赖排序、循环检测
│   │   ├── test_orchestrator.py
│   │   ├── test_intent_router.py
│   │   ├── test_context_bus.py
│   │   └── test_config_validation.py
│   └── plugins/
│       ├── test_meal_agent.py
│       ├── test_short_term_memory.py
│       ├── test_dish_query_tool.py
│       └── test_device_gateway.py
├── integration/
│   ├── test_plugin_lifecycle.py       # 插件热插拔完整流程
│   ├── test_meal_planning_flow.py     # 用户输入→SSE流→结果
│   └── test_device_gateway_flow.py    # 设备连接→指令→回报
├── e2e/
│   └── test_api_chat_flow.py          # pytest + httpx，完整 API 流程测试
└── conftest.py
```

### 11.2 插件贡献 CI 校验

- manifest.yaml schema 验证（含 manifest_version 检查）
- 接口合规检查（是否正确实现 ABC）
- pytest 通过
- 无硬编码密钥

### 11.3 社区贡献

提供 CONTRIBUTING.md 和 Good First Issue 模板，建立渐进式贡献路径：

1. **入门** — 为 MealAgent 添加新菜系的 Jinja2 prompt 模板
2. **进阶** — 编写新的 Tool（如营养计算 Tool）
3. **高级** — 开发完整的 Agent 插件（如 FitnessAgent）
4. **核心** — 开发新的 Extension（如 Slack 集成网关）
