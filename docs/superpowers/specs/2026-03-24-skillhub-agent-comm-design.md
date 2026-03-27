# SkillHub + Agent 间通信 设计文档

## 目标

为 LARY 框架增加两个核心能力：
1. **技能市场（SkillHub）**：社区驱动的插件发现、安装、发布平台
2. **Agent 间通信**：多 Agent 混合协作（Orchestrator 路由 + Agent 直接调用）

## 约束

- 兼容现有插件体系（manifest v1 → v2 平滑升级）
- 本地自托管优先，不依赖外部付费服务
- GitHub 作为索引和下载基础设施
- 第一版功能完整：通信 + 市场 + 发布流程

---

## 一、Agent 间通信

### 1.1 架构

混合模式：Orchestrator 负责用户消息路由和多 Agent 任务编排，Agent 之间也可直接通信。

```
用户消息 → Orchestrator
             ├── 单 Agent 任务 → 直接路由到目标 Agent
             └── 多 Agent 任务 → 拆分子任务 → 分发 → 汇总结果
                                    ↕
                              Agent ←→ Agent（直接调用）
```

### 1.2 内置通信工具

每个 Agent 自动获得两个系统级工具（由框架注入，无需插件声明）：

**`agent_call(target_agent, message, context?)`**
- 异步等待调用目标 Agent（`asyncio.wait_for` 实现超时）
- `target_agent`：目标 Agent 名称（如 `fitness_agent`）
- `message`：自然语言请求
- `context`：可选上下文数据（JSON）
- 返回：目标 Agent 的文本回复 + 工具调用结果
- 超时：30 秒，通过 `asyncio.wait_for(agent.run_sync(...), timeout=30)` 实现
- **被调用 Agent 不接收调用方的对话历史**，仅接收 message 和共享的 session_id（可访问同一用户画像）

**`agent_list()`**
- 返回当前已加载的所有 Agent 列表
- 每个 Agent 包含：name、description、capabilities、status

### 1.3 通信流程

```
Agent A 调用 agent_call("agent_b", "查询用户运动量")
  → 框架校验权限：检查 A 的 manifest.allowed_agents 是否包含 agent_b
  → 框架查找 agent_b 实例
  → 创建临时子会话，继承 session_id（共享用户画像），不传递对话历史
  → asyncio.wait_for(agent_b.run_sync(message, session_id), timeout=30)
  → 将结果返回给 Agent A
  → 写入通信日志
```

### 1.4 通信日志

新增 `agent_message` 表：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增 |
| session_id | String(64) | 用户会话 ID |
| source_agent | String(64) | 发起方 Agent |
| target_agent | String(64) | 目标方 Agent |
| message | Text | 请求消息 |
| result | Text | 响应结果（JSON） |
| duration_ms | Integer | 耗时（毫秒） |
| status | String(16) | success / error / timeout |
| created_at | DateTime | 创建时间 |

### 1.5 Orchestrator 多 Agent 编排（第二阶段）

> 注意：多 Agent 编排是最复杂的部分，第一版先实现 agent_call 直接通信能力，
> 多 Agent 编排推迟到有实际多 Agent 使用场景后再实现。

扩展现有 IntentRouter：

- IntentResult 增加 `agents: list[str]` 字段，同时保留 `agent: str` 作为主 Agent 的计算属性（向后兼容）
- 单 Agent：直接路由（现有逻辑不变）
- 多 Agent：Orchestrator **串行调用**各 Agent，前一个的结果作为后一个的上下文
- 汇总逻辑：将多个 Agent 结果拼接为上下文，交给主 Agent 生成最终回复
- **并行执行标记为未来增强**，当前版本仅串行

### 1.6 防护机制

- **权限控制**：manifest 新增 `allowed_agents: list[str]` 字段，声明可调用的目标 Agent。框架在 agent_call 时强制校验，未声明的调用被拒绝。`"*"` 表示允许调用所有 Agent（仅限内置插件）
- **循环检测**：记录调用链（A→B→C），如果 C 再调 A 则拒绝，返回错误
- **深度限制**：最大调用深度 3 层
- **超时**：单次 agent_call 30 秒，通过 `asyncio.wait_for` 实现
- **并发**：同一 session 内 agent_call 串行执行，避免状态竞争

### 1.7 SSE 事件扩展

Agent 间调用时向前端发送新事件，便于用户了解协作过程：

- `agent_delegate`：`{source: "meal_agent", target: "fitness_agent", message: "..."}`
- `agent_delegate_done`：`{source: "meal_agent", target: "fitness_agent", summary: "..."}`

---

## 二、技能市场（SkillHub）

### 2.1 整体架构

```
GitHub Registry Repo          LARY 实例
┌──────────────────┐     ┌─────────────────────┐
│ index.json       │────→│ SkillHub API        │
│ plugins/         │     │  - 拉取索引（缓存）  │
│   meal_agent/    │     │  - 下载安装          │
│   fitness_agent/ │     │  - 卸载              │
│   ...            │     │  - 发布（生成 PR）   │
└──────────────────┘     └─────────────────────┘
                              ↕
                         前端市场页面
```

### 2.2 Manifest v2

在现有 v1 基础上增加市场相关字段，v1 字段完全保留：

```yaml
manifest_version: 2
name: fitness_agent
version: "1.0.0"
type: agent
description: "AI 健身教练，支持运动计划、卡路里消耗计算"
entry_point: agent:FitnessAgent

# === v2 新增字段 ===
author: "username"
repository: "https://github.com/user/lary-fitness-agent"
license: "MIT"
tags: ["健身", "运动", "健康"]
min_framework_version: "0.2.0"
icon: "icon.png"
screenshots: ["screenshot1.png"]
allowed_agents: ["meal_agent"]  # 允许调用的目标 Agent，"*" 表示全部
changelog: |
  ## 1.0.0
  - 初始版本

# === 现有字段保持不变 ===
dependencies:
  plugins:
    - user_profile
  python:
    - jinja2
tools:
  - tools.workout_tool:WorkoutTool
config_schema: {}
```

**v1 兼容**：manifest_version=1 的插件 `allowed_agents` 默认为空（不可调用其他 Agent），其余 v2 字段可选。加载时不区分版本，缺失字段使用默认值。

**发布校验**：`publish` 时使用严格验证器，要求 v2 必填字段（author, repository, license）必须存在。

### 2.3 索引格式（index.json）

```json
{
  "version": 1,
  "updated_at": "2026-03-24T12:00:00Z",
  "plugins": [
    {
      "name": "fitness_agent",
      "version": "1.0.0",
      "type": "agent",
      "description": "AI 健身教练",
      "author": "username",
      "tags": ["健身", "运动"],
      "min_framework_version": "0.2.0",
      "download_url": "https://github.com/user/lary-fitness-agent/archive/refs/tags/v1.0.0.tar.gz",
      "manifest_url": "https://raw.githubusercontent.com/lary-hub/registry/main/plugins/fitness_agent/manifest.yaml",
      "sha256": "a1b2c3d4...",
      "verified": true,
      "created_at": "2026-03-24",
      "updated_at": "2026-03-24"
    }
  ]
}
```

### 2.4 发布流程

```
开发者本地开发插件
  → lary publish（CLI 或 API）
    → 验证 manifest v2 格式
    → 打包插件目录
    → 生成 PR 到 registry 仓库
      → CI 自动验证：
        - manifest 格式校验
        - 依赖存在性检查
        - 基础安全扫描（敏感文件、硬编码密钥）
        - 插件可加载性测试
      → 维护者人工 Review
      → 合并 → 自动更新 index.json
```

### 2.5 本地安装流程

```
用户在市场页面点击"安装"
  → POST /api/skillhub/install {name, version?}
    → 从 index.json 获取 download_url 和 sha256
    → 下载 tar.gz 到临时目录
    → **校验 SHA256 哈希**（不匹配则拒绝安装）
    → 检查是否已安装同名插件：
      - 未安装 → 正常安装
      - 已安装且版本相同 → 跳过，返回"已是最新"
      - 已安装且版本不同 → 备份旧版到 contrib/.backup/{name}-{old_version}/，再覆盖安装
    → 解压到 contrib/{type}/{name}/
    → 验证 manifest.yaml
    → 调用 registry.load_plugin() 热加载
    → 更新 config.yaml 的 enabled 列表
    → 返回安装结果
```

卸载流程：
```
DELETE /api/skillhub/uninstall/{name}
  → 检查反向依赖
  → 调用 registry.unload_plugin()
  → 从 config.yaml 移除
  → 删除 contrib/{type}/{name}/ 目录
```

### 2.6 后端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/skillhub/registry | 拉取远程索引（本地缓存 1 小时） |
| GET | /api/skillhub/installed | 已安装插件列表 |
| POST | /api/skillhub/install | 安装插件 |
| DELETE | /api/skillhub/uninstall/{name} | 卸载插件 |
| POST | /api/skillhub/publish | 发布插件（生成 PR） |
| GET | /api/skillhub/search?q=&tags=&type= | 搜索插件 |

### 2.7 前端市场页面

替换现有"插件"标签页，分两个 Tab：

**已安装 Tab：**
- 显示当前所有已加载插件
- 每个插件卡片：图标、名称、版本、状态（loaded/failed）、描述
- 操作：卸载、重载、查看详情

**市场 Tab：**
- 顶部搜索栏 + 标签筛选（type: agent/memory/extension, tags）
- 插件卡片网格：图标、名称、作者、描述、标签、版本、验证状态徽章
- 操作：安装、查看详情（跳转 GitHub 仓库）
- 已安装的插件显示"已安装"标记

### 2.8 安装目录结构

```
LARY/
  plugins/          # 内置插件（随项目发布）
    agents/
    memory/
    extensions/
  contrib/           # 社区安装的插件（.gitignore）
    agents/
    memory/
    extensions/
```

`contrib/` 目录加入 `.gitignore`，不随项目代码提交。框架启动时已经扫描 `plugins/` 和 `contrib/`（`main.py` 中 `registry.discover("plugins", "contrib")`），无需修改启动逻辑。

---

## 三、文件变更清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `core/agent_comm.py` | Agent 间通信管理器（agent_call、agent_list 工具实现） |
| `core/models/agent_message.py` | AgentMessage 数据模型 |
| `api/skillhub.py` | SkillHub API 路由 |
| `core/skillhub.py` | SkillHub 核心逻辑（索引、安装、卸载、发布） |
| `web/src/views/SkillHubView.vue` | 市场页面（替换 PluginsView） |
| `web/src/components/skillhub/PluginCard.vue` | 插件卡片组件 |
| `web/src/components/skillhub/SearchBar.vue` | 搜索筛选组件 |
| `web/src/api/skillhub.ts` | 前端 API 调用 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `core/database.py` | 新增 AgentMessage 表 |
| `core/plugin_registry.py` | 支持扫描 contrib 目录、manifest v2 兼容 |
| `core/models/plugin.py` | PluginManifest 增加 v2 字段 |
| `core/interfaces/agent.py` | run() 中自动注入 agent_call/agent_list 工具 |
| `core/orchestrator.py` | 多 Agent 编排逻辑 |
| `core/intent_router.py` | 支持返回多个 Agent |
| `main.py` | 注册 SkillHub 路由 |
| `config.yaml` | 新增 skillhub 配置项 |
| `web/src/router/index.ts` | 路由更新 |
| `web/src/components/BottomNav.vue` | "插件"改为"市场" |

---

## 四、实施顺序

1. **基础设施**：Manifest v2 模型（含 allowed_agents）、AgentMessage 表、PluginManifest 兼容升级
2. **Agent 间通信**：agent_call/agent_list 工具、权限校验、通信日志、循环检测、SSE 事件
3. **SkillHub 后端**：索引拉取（带缓存）、SHA256 校验安装、版本升级/备份、卸载 API
4. **SkillHub 发布流程**：打包、manifest v2 严格校验、PR 生成、CI 验证
5. **前端市场页面**：已安装 + 市场 Tab、搜索筛选、安装卸载交互
6. **Orchestrator 多 Agent 编排**（第二阶段）：多 Agent 意图识别和串行任务分发，待有实际多 Agent 场景后实施

### 信任模型说明

SkillHub 安装的插件本质上是执行任意 Python 代码。安全保障链：
1. **发布审核**：PR + 维护者人工 Review
2. **下载校验**：SHA256 哈希确保下载内容与审核内容一致
3. **运行时权限**：`allowed_agents` 限制 Agent 间调用范围
4. **用户知情**：安装界面显示"已验证"/"未验证"标记
