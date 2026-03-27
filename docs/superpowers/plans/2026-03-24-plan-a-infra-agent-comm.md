# Plan A: 基础设施 + Agent 间通信 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 LARY 框架增加 Manifest v2 模型、Agent 间通信能力（agent_call / agent_list）和通信日志，为后续 SkillHub 打下基础。

**Architecture:** 在现有插件体系上平滑升级：PluginManifest 增加 v2 字段（向后兼容），新增 AgentMessage 表记录通信日志，新建 `core/agent_comm.py` 实现 agent_call/agent_list 工具并自动注入到每个 Agent，通过 `allowed_agents` 权限控制 + 调用链循环检测保障安全。

**Tech Stack:** Python 3.11+, Pydantic v2, SQLAlchemy async, asyncio, FastAPI SSE

**Spec:** `docs/superpowers/specs/2026-03-24-skillhub-agent-comm-design.md`

---

### Task 0: 修复 run_sync 事件名不匹配

**背景:** `BaseStreamAgent.run_sync()` 监听 `"tool_output"` 事件，但 `run()` 实际发出的是 `"tool_output_done"`。这导致 `run_sync` 收集不到工具结果，而 `agent_call` 依赖 `run_sync` 工作。

**Files:**
- Modify: `core/interfaces/agent.py:229`
- Test: `tests/core/interfaces/test_agent_run_sync.py` (Create)

- [ ] **Step 1: 编写 run_sync 事件收集测试**

```python
# tests/core/interfaces/test_agent_run_sync.py
"""BaseStreamAgent.run_sync 事件收集测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.interfaces.agent import BaseStreamAgent, SSEEvent, AgentResult


class FakeAgent(BaseStreamAgent):
    def get_system_prompt(self, context):
        return "test"
    def get_tools(self):
        return []
    def get_model(self):
        return "test-model"
    @property
    def capabilities(self):
        return ["test"]


class TestRunSyncEventCollection:

    @pytest.mark.asyncio
    async def test_run_sync_collects_tool_output_done(self):
        """run_sync 应该收集 tool_output_done 事件中的工具结果"""
        agent = FakeAgent(context_bus=None)

        # Mock run() to yield specific events
        async def fake_run(*args, **kwargs):
            yield SSEEvent(event="text_delta", data={"content": "hello"})
            yield SSEEvent(event="tool_output_done", data={"tool": "test", "result": {"success": True}})
            yield SSEEvent(event="done", data={"session_id": "s1", "agent": "FakeAgent"})

        agent.run = fake_run

        result = await agent.run_sync("test message", "s1")
        assert result.result["summary"] == "hello"
        assert len(result.result["tool_results"]) == 1
        assert result.result["tool_results"][0]["tool"] == "test"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/interfaces/test_agent_run_sync.py -v`
Expected: FAIL — `tool_results` 为空（因为监听了错误的事件名）

- [ ] **Step 3: 修复 run_sync 事件名**

在 `core/interfaces/agent.py` 第 229 行，将：
```python
elif event.event == "tool_output":
```
改为：
```python
elif event.event == "tool_output_done":
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/interfaces/test_agent_run_sync.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/interfaces/agent.py tests/core/interfaces/test_agent_run_sync.py
git commit -m "fix: run_sync 监听正确的 tool_output_done 事件名"
```

---

### Task 1: PluginManifest v2 模型升级

**Files:**
- Modify: `core/models/plugin.py:7-17`
- Test: `tests/core/models/test_plugin.py` (Create)

- [ ] **Step 1: 创建测试文件，编写 manifest v2 字段测试**

```python
# tests/core/models/test_plugin.py
"""PluginManifest v2 字段测试"""
import pytest
from core.models.plugin import PluginManifest, PluginDependencies


class TestPluginManifestV2:
    """manifest v2 新增字段"""

    def test_v1_manifest_defaults(self):
        """v1 manifest 缺失 v2 字段时使用默认值"""
        m = PluginManifest(
            name="test_plugin",
            type="agent",
            entry_point="agent:TestAgent",
        )
        assert m.manifest_version == 1
        assert m.allowed_agents == []
        assert m.author == ""
        assert m.repository == ""
        assert m.license == ""
        assert m.tags == []
        assert m.min_framework_version == ""
        assert m.icon == ""
        assert m.screenshots == []
        assert m.changelog == ""

    def test_v2_manifest_full_fields(self):
        """v2 manifest 全字段"""
        m = PluginManifest(
            manifest_version=2,
            name="fitness_agent",
            version="1.0.0",
            type="agent",
            description="AI 健身教练",
            entry_point="agent:FitnessAgent",
            author="username",
            repository="https://github.com/user/lary-fitness-agent",
            license="MIT",
            tags=["健身", "运动"],
            min_framework_version="0.2.0",
            icon="icon.png",
            screenshots=["s1.png"],
            allowed_agents=["meal_agent"],
            changelog="## 1.0.0\n- 初始版本",
        )
        assert m.manifest_version == 2
        assert m.allowed_agents == ["meal_agent"]
        assert m.author == "username"
        assert m.license == "MIT"
        assert m.tags == ["健身", "运动"]

    def test_allowed_agents_wildcard(self):
        """allowed_agents 支持通配符 '*'"""
        m = PluginManifest(
            name="core_agent",
            type="agent",
            entry_point="agent:CoreAgent",
            allowed_agents=["*"],
        )
        assert m.allowed_agents == ["*"]

    def test_v1_compat_extra_fields_ignored(self):
        """v1 manifest 即使有 extra='allow' 也不会报错"""
        m = PluginManifest(
            manifest_version=1,
            name="old_plugin",
            type="memory",
            entry_point="mem:OldMem",
            some_unknown_field="hello",
        )
        assert m.name == "old_plugin"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY && python -m pytest tests/core/models/test_plugin.py -v`
Expected: FAIL — `allowed_agents` 等字段不存在

- [ ] **Step 3: 修改 PluginManifest 增加 v2 字段**

```python
# core/models/plugin.py
"""Plugin 相关模型"""
from __future__ import annotations

from pydantic import BaseModel


class PluginManifest(BaseModel):
    """插件 manifest.yaml 对应模型（v1 + v2 兼容）"""
    manifest_version: int = 1
    name: str
    version: str = "0.1.0"
    type: str  # agent | memory | search | extension
    description: str = ""
    entry_point: str  # 模块:类名
    dependencies: PluginDependencies = None
    tools: list[str] = []
    config_schema: dict = {}

    # === v2 新增字段（全部可选，v1 使用默认值）===
    author: str = ""
    repository: str = ""
    license: str = ""
    tags: list[str] = []
    min_framework_version: str = ""
    icon: str = ""
    screenshots: list[str] = []
    allowed_agents: list[str] = []  # 允许调用的目标 Agent，"*" = 全部
    changelog: str = ""

    class Config:
        extra = "allow"


class PluginDependencies(BaseModel):
    """插件依赖声明"""
    plugins: list[str] = []
    python: list[str] = []


class PluginState(BaseModel):
    """插件运行时状态"""
    name: str
    type: str
    version: str
    status: str = "loaded"  # loaded | failed | unloaded
    capabilities: list[str] = []
    error: str | None = None
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/models/test_plugin.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: 提交**

```bash
git add core/models/plugin.py tests/core/models/test_plugin.py
git commit -m "feat: PluginManifest 增加 v2 字段，向后兼容 v1"
```

---

### Task 2: PluginRegistry 增加 get_manifest 公共方法

**Files:**
- Modify: `core/plugin_registry.py`
- Test: `tests/core/test_plugin_registry_manifest.py` (Create)

- [ ] **Step 1: 编写 get_manifest 测试**

```python
# tests/core/test_plugin_registry_manifest.py
"""PluginRegistry.get_manifest 测试"""
import pytest
from core.plugin_registry import PluginRegistry
from core.models.plugin import PluginManifest


class TestGetManifest:

    def test_get_existing_manifest(self):
        registry = PluginRegistry()
        manifest = PluginManifest(name="test", type="agent", entry_point="a:A")
        registry._manifests["test"] = manifest
        assert registry.get_manifest("test") is manifest

    def test_get_nonexistent_manifest(self):
        registry = PluginRegistry()
        assert registry.get_manifest("nonexistent") is None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_plugin_registry_manifest.py -v`
Expected: FAIL — `get_manifest` 不存在

- [ ] **Step 3: 在 PluginRegistry 中添加 get_manifest**

在 `core/plugin_registry.py` 的"运行时查询"区域（约第 196 行之后）新增：

```python
def get_manifest(self, name: str) -> PluginManifest | None:
    """获取插件 manifest"""
    return self._manifests.get(name)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_plugin_registry_manifest.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/plugin_registry.py tests/core/test_plugin_registry_manifest.py
git commit -m "feat: PluginRegistry 新增 get_manifest 公共方法"
```

---

### Task 3: AgentMessage 数据模型 + 数据库表

**Files:**
- Create: `core/models/agent_message.py`
- Modify: `core/database.py` (增加 import)
- Test: `tests/core/models/test_agent_message.py` (Create)

- [ ] **Step 1: 编写 AgentMessage 模型测试**

```python
# tests/core/models/test_agent_message.py
"""AgentMessage 模型测试"""
import pytest
from core.models.agent_message import AgentMessageRecord


class TestAgentMessageRecord:

    def test_table_name(self):
        assert AgentMessageRecord.__tablename__ == "agent_message"

    def test_columns_exist(self):
        cols = {c.name for c in AgentMessageRecord.__table__.columns}
        expected = {
            "id", "session_id", "source_agent", "target_agent",
            "message", "result", "duration_ms", "status", "created_at",
        }
        assert expected == cols
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/models/test_agent_message.py -v`
Expected: FAIL — `core.models.agent_message` 不存在

- [ ] **Step 3: 创建 AgentMessage 模型**

```python
# core/models/agent_message.py
"""AgentMessage - Agent 间通信日志表"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, DateTime, Integer, func

from core.database import Base


class AgentMessageRecord(Base):
    """Agent 间通信日志"""
    __tablename__ = "agent_message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    source_agent = Column(String(64), nullable=False)
    target_agent = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    result = Column(Text, nullable=True)  # JSON
    duration_ms = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="success")  # success | error | timeout
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

- [ ] **Step 4: 在 database.py 中导入以确保表注册**

在 `core/database.py` 的 `init_db` 函数之前添加：

```python
# 确保所有 ORM 模型在 create_all 前被导入
import core.models.agent_message  # noqa: F401
```

- [ ] **Step 5: 运行测试验证通过**

Run: `python -m pytest tests/core/models/test_agent_message.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: 提交**

```bash
git add core/models/agent_message.py core/database.py tests/core/models/test_agent_message.py
git commit -m "feat: 新增 AgentMessage 表，记录 Agent 间通信日志"
```

---

### Task 4: AgentCommManager 核心 — agent_list 工具

**Files:**
- Create: `core/agent_comm.py`
- Test: `tests/core/test_agent_comm.py` (Create)

**注意:** `BaseTool` 的 `name`、`description`、`parameters_schema` 是 `@property @abstractmethod`，实现时用类属性覆盖即可（Python 允许），但属性名必须是 `parameters_schema` 而非 `parameters`。

- [ ] **Step 1: 编写 agent_list 工具测试**

```python
# tests/core/test_agent_comm.py
"""AgentCommManager 测试"""
import pytest
from unittest.mock import MagicMock

from core.agent_comm import AgentCommManager, AgentListTool
from core.models.plugin import PluginManifest, PluginState


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.list_plugins.return_value = [
        PluginState(name="meal_agent", type="agent", version="0.1.0",
                    status="loaded", capabilities=["meal_recommend"]),
        PluginState(name="fitness_agent", type="agent", version="1.0.0",
                    status="loaded", capabilities=["workout"]),
    ]
    # get_manifest 返回包含 description 的 manifest
    registry.get_manifest.side_effect = lambda name: {
        "meal_agent": PluginManifest(
            name="meal_agent", type="agent", entry_point="a:A",
            description="AI 营养师",
        ),
        "fitness_agent": PluginManifest(
            name="fitness_agent", type="agent", entry_point="a:A",
            description="AI 健身教练",
        ),
    }.get(name)
    return registry


@pytest.fixture
def comm_manager(mock_registry):
    return AgentCommManager(registry=mock_registry)


class TestAgentListTool:

    @pytest.mark.asyncio
    async def test_agent_list_returns_all_agents(self, comm_manager):
        tool = AgentListTool(comm_manager)
        result = await tool.execute()
        assert result.success is True
        agents = result.data["agents"]
        assert len(agents) == 2
        assert agents[0]["name"] == "meal_agent"
        assert agents[0]["description"] == "AI 营养师"
        assert agents[1]["name"] == "fitness_agent"
        assert agents[1]["description"] == "AI 健身教练"

    def test_tool_schema(self, comm_manager):
        tool = AgentListTool(comm_manager)
        assert tool.name == "agent_list"
        schema = tool.to_function_tool()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "agent_list"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_agent_comm.py::TestAgentListTool -v`
Expected: FAIL — `core.agent_comm` 不存在

- [ ] **Step 3: 实现 AgentCommManager 和 AgentListTool**

```python
# core/agent_comm.py
"""AgentCommManager - Agent 间通信管理器"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, TYPE_CHECKING

from loguru import logger

from core.interfaces.tool import BaseTool, ToolResult

if TYPE_CHECKING:
    from core.plugin_registry import PluginRegistry


class AgentCommManager:
    """管理 Agent 间通信：权限校验、调用执行、日志记录"""

    MAX_CALL_DEPTH = 3
    CALL_TIMEOUT = 30  # 秒

    def __init__(self, registry: "PluginRegistry") -> None:
        self._registry = registry
        # 调用链追踪：session_id -> list[agent_name]
        self._call_chains: dict[str, list[str]] = {}
        # SSE 事件回调
        self._sse_callback: Any = None

    def get_agent_list(self) -> list[dict[str, Any]]:
        """返回所有已加载 Agent 信息"""
        agents = self._registry.list_plugins(plugin_type="agent")
        result = []
        for a in agents:
            manifest = self._registry.get_manifest(a.name)
            result.append({
                "name": a.name,
                "description": manifest.description if manifest else "",
                "capabilities": a.capabilities,
                "status": a.status,
            })
        return result

    def check_permission(self, source: str, target: str) -> str | None:
        """校验 source 是否有权调用 target，返回错误消息或 None"""
        manifest = self._registry.get_manifest(source)
        if not manifest:
            return f"源 Agent '{source}' 的 manifest 未找到"
        allowed = getattr(manifest, "allowed_agents", [])
        if "*" in allowed:
            return None
        if target not in allowed:
            return f"Agent '{source}' 无权限调用 '{target}'（allowed_agents 中未声明）"
        return None

    def check_call_chain(self, session_id: str, source: str, target: str) -> str | None:
        """检测循环调用和深度限制，返回错误消息或 None"""
        chain = self._call_chains.get(session_id, [])

        # 循环检测
        if target in chain:
            return f"检测到循环调用: {'→'.join(chain)}→{target}"

        # 深度限制
        if len(chain) >= self.MAX_CALL_DEPTH:
            return f"调用深度超过限制（最大 {self.MAX_CALL_DEPTH} 层）"

        return None

    def set_sse_callback(self, callback: Any) -> None:
        """设置 SSE 事件回调，用于通知前端 Agent 委派事件"""
        self._sse_callback = callback

    def _emit_event(self, event_type: str, data: dict) -> None:
        """触发 SSE 事件"""
        if self._sse_callback:
            self._sse_callback(event_type, data)

    async def log_message(
        self,
        session_id: str,
        source: str,
        target: str,
        message: str,
        result: str | None,
        duration_ms: int,
        status: str,
    ) -> None:
        """记录通信日志到数据库"""
        try:
            from core.database import get_session_factory
            from core.models.agent_message import AgentMessageRecord

            factory = get_session_factory()
            async with factory() as session:
                record = AgentMessageRecord(
                    session_id=session_id,
                    source_agent=source,
                    target_agent=target,
                    message=message,
                    result=result,
                    duration_ms=duration_ms,
                    status=status,
                )
                session.add(record)
                await session.commit()
        except Exception as e:
            logger.warning(f"Failed to log agent message: {e}", exc_info=True)


class AgentListTool(BaseTool):
    """系统工具：列出当前已加载的所有 Agent"""

    name = "agent_list"
    description = "列出当前已加载的所有 Agent 及其能力"
    parameters_schema = {"type": "object", "properties": {}}

    def __init__(self, comm_manager: AgentCommManager) -> None:
        self._comm = comm_manager

    async def execute(self, **kwargs: Any) -> ToolResult:
        agents = self._comm.get_agent_list()
        return ToolResult(success=True, data={"agents": agents})
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_agent_comm.py::TestAgentListTool -v`
Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add core/agent_comm.py tests/core/test_agent_comm.py
git commit -m "feat: 新增 AgentCommManager 和 agent_list 工具"
```

---

### Task 5: agent_call 工具 — 权限校验 + 循环检测 + 超时

**Files:**
- Modify: `core/agent_comm.py`
- Modify: `tests/core/test_agent_comm.py`

- [ ] **Step 1: 编写 agent_call 权限、循环检测和超时测试**

在 `tests/core/test_agent_comm.py` 中追加：

```python
import asyncio
from core.agent_comm import AgentCallTool
from core.interfaces.agent import AgentResult


@pytest.fixture
def mock_registry_with_manifests():
    registry = MagicMock()

    registry.list_plugins.return_value = [
        PluginState(name="meal_agent", type="agent", version="0.1.0", status="loaded"),
        PluginState(name="fitness_agent", type="agent", version="1.0.0", status="loaded"),
    ]

    mock_fitness = MagicMock()
    mock_fitness.run_sync.return_value = AgentResult(
        session_id="s1", agent="fitness_agent",
        result={"summary": "运动量正常", "tool_results": []},
    )
    registry.get_agent.side_effect = lambda name: mock_fitness if name == "fitness_agent" else None

    meal_manifest = PluginManifest(
        name="meal_agent", type="agent", entry_point="a:A",
        allowed_agents=["fitness_agent"],
    )
    fitness_manifest = PluginManifest(
        name="fitness_agent", type="agent", entry_point="a:A",
        allowed_agents=[],
    )
    registry.get_manifest.side_effect = lambda name: {
        "meal_agent": meal_manifest,
        "fitness_agent": fitness_manifest,
    }.get(name)

    return registry


@pytest.fixture
def comm_with_manifests(mock_registry_with_manifests):
    return AgentCommManager(registry=mock_registry_with_manifests)


class TestAgentCallPermission:

    @pytest.mark.asyncio
    async def test_call_allowed(self, comm_with_manifests):
        tool = AgentCallTool(comm_with_manifests, source_agent="meal_agent")
        result = await tool.execute(
            target_agent="fitness_agent",
            message="查询用户运动量",
            session_id="s1",
        )
        assert result.success is True
        assert "运动量正常" in result.data["summary"]

    @pytest.mark.asyncio
    async def test_call_denied_no_permission(self, comm_with_manifests):
        tool = AgentCallTool(comm_with_manifests, source_agent="fitness_agent")
        result = await tool.execute(
            target_agent="meal_agent",
            message="查询菜谱",
            session_id="s1",
        )
        assert result.success is False
        assert "权限" in result.error

    @pytest.mark.asyncio
    async def test_call_wildcard_permission(self, comm_with_manifests):
        """通配符权限应通过校验（但目标 agent 可能不存在）"""
        # 修改 fitness 的权限为通配符
        manifest = comm_with_manifests._registry.get_manifest("fitness_agent")
        manifest.allowed_agents = ["*"]
        tool = AgentCallTool(comm_with_manifests, source_agent="fitness_agent")
        result = await tool.execute(
            target_agent="meal_agent",
            message="查询菜谱",
            session_id="s1",
        )
        # 通配符权限通过，但 meal_agent 在 get_agent 中返回 None
        assert result.success is False
        assert "未找到" in result.error

    @pytest.mark.asyncio
    async def test_call_target_not_found(self, comm_with_manifests):
        """目标 Agent 不存在"""
        manifest = comm_with_manifests._registry.get_manifest("meal_agent")
        manifest.allowed_agents = ["nonexistent"]
        tool = AgentCallTool(comm_with_manifests, source_agent="meal_agent")
        result = await tool.execute(
            target_agent="nonexistent",
            message="test",
            session_id="s1",
        )
        assert result.success is False
        assert "未找到" in result.error


class TestAgentCallCircularDetection:

    @pytest.mark.asyncio
    async def test_circular_call_rejected(self, comm_with_manifests):
        comm_with_manifests._call_chains["s1"] = ["meal_agent", "fitness_agent"]
        tool = AgentCallTool(comm_with_manifests, source_agent="fitness_agent")
        result = await tool.execute(
            target_agent="meal_agent",
            message="test",
            session_id="s1",
        )
        assert result.success is False
        assert "循环" in result.error

    @pytest.mark.asyncio
    async def test_depth_limit_exceeded(self, comm_with_manifests):
        comm_with_manifests._call_chains["s1"] = ["a", "b", "c"]
        tool = AgentCallTool(comm_with_manifests, source_agent="c")
        result = await tool.execute(
            target_agent="fitness_agent",
            message="test",
            session_id="s1",
        )
        assert result.success is False
        assert "深度" in result.error


class TestAgentCallTimeout:

    @pytest.mark.asyncio
    async def test_call_timeout(self, comm_with_manifests):
        """超时调用应返回 timeout 错误"""
        mock_agent = comm_with_manifests._registry.get_agent("fitness_agent")

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(60)

        mock_agent.run_sync = slow_run
        comm_with_manifests.CALL_TIMEOUT = 0.1  # 100ms 快速超时

        tool = AgentCallTool(comm_with_manifests, source_agent="meal_agent")
        result = await tool.execute(
            target_agent="fitness_agent",
            message="test",
            session_id="s1",
        )
        assert result.success is False
        assert "超时" in result.error


class TestAgentCallChainCleanup:

    @pytest.mark.asyncio
    async def test_chain_cleaned_after_success(self, comm_with_manifests):
        """成功调用后调用链应被清理"""
        tool = AgentCallTool(comm_with_manifests, source_agent="meal_agent")
        await tool.execute(
            target_agent="fitness_agent",
            message="test",
            session_id="s1",
        )
        # 调用链应为空或已清理
        assert comm_with_manifests._call_chains.get("s1", []) == []

    @pytest.mark.asyncio
    async def test_chain_cleaned_after_timeout(self, comm_with_manifests):
        """超时后调用链也应被清理"""
        mock_agent = comm_with_manifests._registry.get_agent("fitness_agent")

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(60)

        mock_agent.run_sync = slow_run
        comm_with_manifests.CALL_TIMEOUT = 0.1

        tool = AgentCallTool(comm_with_manifests, source_agent="meal_agent")
        await tool.execute(
            target_agent="fitness_agent",
            message="test",
            session_id="s1",
        )
        assert comm_with_manifests._call_chains.get("s1", []) == []
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_agent_comm.py -v -k "Permission or Circular or Timeout or Cleanup"`
Expected: FAIL — `AgentCallTool` 不存在

- [ ] **Step 3: 实现 AgentCallTool**

在 `core/agent_comm.py` 末尾追加：

```python
class AgentCallTool(BaseTool):
    """系统工具：调用目标 Agent"""

    name = "agent_call"
    description = "调用另一个 Agent 执行任务。需要指定目标 Agent 名称和请求消息。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "target_agent": {
                "type": "string",
                "description": "目标 Agent 名称",
            },
            "message": {
                "type": "string",
                "description": "发送给目标 Agent 的自然语言请求",
            },
            "context": {
                "type": "object",
                "description": "可选的上下文数据",
            },
        },
        "required": ["target_agent", "message"],
    }

    def __init__(self, comm_manager: AgentCommManager, source_agent: str) -> None:
        self._comm = comm_manager
        self._source = source_agent

    async def execute(self, **kwargs: Any) -> ToolResult:
        target_name = kwargs.get("target_agent", "")
        message = kwargs.get("message", "")
        session_id = kwargs.get("session_id", "")

        # 1. 权限校验
        error = self._comm.check_permission(self._source, target_name)
        if error:
            return ToolResult(success=False, data=None, error=error)

        # 2. 循环检测 + 深度限制
        error = self._comm.check_call_chain(session_id, self._source, target_name)
        if error:
            return ToolResult(success=False, data=None, error=error)

        # 3. 查找目标 Agent
        target = self._comm._registry.get_agent(target_name)
        if not target:
            return ToolResult(success=False, data=None, error=f"Agent '{target_name}' 未找到")

        # 4. SSE 通知
        self._comm._emit_event("agent_delegate", {
            "source": self._source,
            "target": target_name,
            "message": message,
        })

        # 5. 执行调用
        chain = self._comm._call_chains.setdefault(session_id, [])
        chain.append(target_name)
        start_ms = int(time.time() * 1000)
        try:
            agent_result = await asyncio.wait_for(
                target.run_sync(message, session_id),
                timeout=self._comm.CALL_TIMEOUT,
            )
            duration_ms = int(time.time() * 1000) - start_ms

            await self._comm.log_message(
                session_id=session_id,
                source=self._source,
                target=target_name,
                message=message,
                result=json.dumps(agent_result.result, ensure_ascii=False),
                duration_ms=duration_ms,
                status="success",
            )

            self._comm._emit_event("agent_delegate_done", {
                "source": self._source,
                "target": target_name,
                "summary": agent_result.result.get("summary", ""),
            })

            return ToolResult(
                success=True,
                data={
                    "summary": agent_result.result.get("summary", ""),
                    "tool_results": agent_result.result.get("tool_results", []),
                },
            )
        except asyncio.TimeoutError:
            duration_ms = int(time.time() * 1000) - start_ms
            await self._comm.log_message(
                session_id=session_id,
                source=self._source,
                target=target_name,
                message=message,
                result=None,
                duration_ms=duration_ms,
                status="timeout",
            )
            return ToolResult(
                success=False, data=None,
                error=f"调用 {target_name} 超时（{self._comm.CALL_TIMEOUT}s）",
            )
        except Exception as e:
            duration_ms = int(time.time() * 1000) - start_ms
            await self._comm.log_message(
                session_id=session_id,
                source=self._source,
                target=target_name,
                message=message,
                result=str(e),
                duration_ms=duration_ms,
                status="error",
            )
            return ToolResult(
                success=False, data=None,
                error=f"调用 {target_name} 失败: {e}",
            )
        finally:
            if chain and chain[-1] == target_name:
                chain.pop()
            # 清理空链避免内存泄漏
            if not chain:
                self._comm._call_chains.pop(session_id, None)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_agent_comm.py -v`
Expected: PASS (所有测试)

- [ ] **Step 5: 提交**

```bash
git add core/agent_comm.py tests/core/test_agent_comm.py
git commit -m "feat: 实现 agent_call 工具，含权限校验、循环检测、超时和 SSE 事件"
```

---

### Task 6: Agent 系统工具自动注入

**Files:**
- Modify: `core/plugin_registry.py`
- Test: `tests/core/test_tool_injection.py` (Create)

- [ ] **Step 1: 编写工具注入测试**

```python
# tests/core/test_tool_injection.py
"""Agent 系统工具注入测试"""
import pytest
from unittest.mock import MagicMock

from core.plugin_registry import PluginRegistry
from core.agent_comm import AgentCommManager


class TestSystemToolInjection:

    def test_agent_receives_system_tools(self):
        """Agent 加载后应自动获得 agent_list 和 agent_call 工具"""
        registry = PluginRegistry()
        comm = AgentCommManager(registry=registry)
        registry.set_comm_manager(comm)

        tools = registry._inject_system_tools("test_agent", [])
        tool_names = [t.name for t in tools]
        assert "agent_list" in tool_names
        assert "agent_call" in tool_names

    def test_system_tools_appended_to_existing(self):
        """系统工具追加到现有工具列表末尾"""
        registry = PluginRegistry()
        comm = AgentCommManager(registry=registry)
        registry.set_comm_manager(comm)

        existing_tool = MagicMock()
        existing_tool.name = "dish_query"

        tools = registry._inject_system_tools("test_agent", [existing_tool])
        assert len(tools) == 3  # dish_query + agent_list + agent_call
        assert tools[0].name == "dish_query"

    def test_no_injection_without_comm_manager(self):
        """未设置 CommManager 时不注入系统工具"""
        registry = PluginRegistry()
        tools = registry._inject_system_tools("test_agent", [])
        assert len(tools) == 0
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_tool_injection.py -v`
Expected: FAIL — `set_comm_manager` 和 `_inject_system_tools` 不存在

- [ ] **Step 3: 修改 PluginRegistry 支持系统工具注入**

1. 在 `core/plugin_registry.py` 的 `__init__` 中新增：
```python
self._comm_manager: Any = None
```

2. 新增两个方法（在"运行时查询"区域）：
```python
def set_comm_manager(self, comm_manager: Any) -> None:
    """设置 Agent 通信管理器（在 main.py 初始化后调用）"""
    self._comm_manager = comm_manager

def _inject_system_tools(self, agent_name: str, existing_tools: list) -> list:
    """为 Agent 注入系统级工具（agent_call、agent_list）"""
    if not self._comm_manager:
        return existing_tools

    from core.agent_comm import AgentListTool, AgentCallTool

    system_tools = [
        AgentListTool(self._comm_manager),
        AgentCallTool(self._comm_manager, source_agent=agent_name),
    ]
    return list(existing_tools) + system_tools
```

3. 修改 `_load_single` 中 Agent 工具注入（约第 168 行），在 `self._tools[manifest.name] = agent_tools` 之前插入一行：

```python
# 原代码：
# self._tools[manifest.name] = agent_tools

# 改为：
agent_tools = self._inject_system_tools(manifest.name, agent_tools)
self._tools[manifest.name] = agent_tools
```

完整的 Agent 工具注入块：
```python
if manifest.type == "agent":
    agent_tools = list(self._tools.get(manifest.name, []))
    if manifest.dependencies:
        for dep_name in manifest.dependencies.plugins:
            dep_tools = self._tools.get(dep_name, [])
            agent_tools.extend(dep_tools)
    # 注入系统工具（agent_call, agent_list）
    agent_tools = self._inject_system_tools(manifest.name, agent_tools)
    self._tools[manifest.name] = agent_tools
    if hasattr(instance, "set_tools"):
        instance.set_tools(agent_tools)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_tool_injection.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add core/plugin_registry.py tests/core/test_tool_injection.py
git commit -m "feat: PluginRegistry 支持 Agent 系统工具自动注入"
```

---

### Task 7: Orchestrator 集成 SSE 转发

**Files:**
- Modify: `core/orchestrator.py`
- Test: `tests/core/test_orchestrator_comm.py` (Create)

- [ ] **Step 1: 编写 Orchestrator delegate 事件转发测试**

```python
# tests/core/test_orchestrator_comm.py
"""Orchestrator Agent 通信事件转发测试"""
import pytest
from unittest.mock import MagicMock

from core.orchestrator import Orchestrator


class TestOrchestratorCommIntegration:

    def test_set_comm_manager(self):
        """Orchestrator 支持设置 comm_manager"""
        registry = MagicMock()
        router = MagicMock()
        decomposer = MagicMock()

        orch = Orchestrator(
            registry=registry,
            intent_router=router,
            task_decomposer=decomposer,
        )
        assert hasattr(orch, "set_comm_manager")

        mock_comm = MagicMock()
        orch.set_comm_manager(mock_comm)
        assert orch._comm_manager is mock_comm
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_orchestrator_comm.py -v`
Expected: FAIL — `set_comm_manager` 不存在

- [ ] **Step 3: 修改 Orchestrator 支持委派事件转发**

在 `core/orchestrator.py` 的 `__init__` 中添加：
```python
self._comm_manager: Any = None
```

新增方法：
```python
def set_comm_manager(self, comm_manager: Any) -> None:
    """设置通信管理器以转发 delegate 事件"""
    self._comm_manager = comm_manager
```

在 `run_stream` 方法中，Agent 执行循环之前（约 `for sub_task in sub_tasks:` 前）设置 SSE 回调：

```python
# 设置 Agent 通信 SSE 回调
sse_events_buffer: list[SSEEvent] = []
if self._comm_manager:
    def on_comm_event(event_type: str, data: dict):
        sse_events_buffer.append(SSEEvent(event=event_type, data=data))
    self._comm_manager.set_sse_callback(on_comm_event)
```

在 `async for event in agent.run(...)` 循环内，每次 `yield event` 之前先 flush 缓冲：

```python
# flush 委派事件
while sse_events_buffer:
    yield sse_events_buffer.pop(0)
yield event
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_orchestrator_comm.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/orchestrator.py tests/core/test_orchestrator_comm.py
git commit -m "feat: Orchestrator 转发 Agent delegate SSE 事件"
```

---

### Task 8: main.py 初始化集成

**Files:**
- Modify: `main.py:86-127` (lifespan 函数)

- [ ] **Step 1: 阅读 main.py 确认当前初始化顺序**

当前顺序（`lifespan` 函数内）：
1. 加载配置
2. 设置日志
3. 设置 LiteLLM 环境变量
4. 初始化数据库（`init_db`）
5. `init_plugins(app_config)` → 调用 `registry.load_enabled()`
6. 加载 Extensions
7. `init_orchestrator(app_config)` → 创建 Orchestrator

**关键:** `set_comm_manager` 必须在 `init_plugins` **之前**调用，这样 `load_enabled` 加载 Agent 时才能注入系统工具。

- [ ] **Step 2: 修改 main.py 添加 AgentCommManager 初始化**

在 `main.py` 的 `lifespan` 函数中，在 `init_plugins(app_config)` 之前添加：

```python
# 初始化 Agent 间通信（必须在 init_plugins 之前，以便注入系统工具）
from core.agent_comm import AgentCommManager
comm_manager = AgentCommManager(registry=registry)
registry.set_comm_manager(comm_manager)
```

在 `init_orchestrator(app_config)` 之后添加：

```python
# 连接通信管理器到编排引擎
orchestrator.set_comm_manager(comm_manager)
```

修改后的 lifespan 关键顺序：
```python
# 初始化数据库
await init_db()

# 初始化 Agent 间通信（必须在 init_plugins 之前）
from core.agent_comm import AgentCommManager
comm_manager = AgentCommManager(registry=registry)
registry.set_comm_manager(comm_manager)

# 加载插件
init_plugins(app_config)

# 加载 Extensions
...

# 初始化编排引擎
init_orchestrator(app_config)
orchestrator.set_comm_manager(comm_manager)
```

- [ ] **Step 3: 验证导入正常**

Run: `cd /Users/sMacmini4/Project/dongying/github/LARY && python -c "from core.agent_comm import AgentCommManager; print('import ok')"`
Expected: 输出 `import ok`

- [ ] **Step 4: 提交**

```bash
git add main.py
git commit -m "feat: main.py 初始化 AgentCommManager，在 init_plugins 之前注入"
```

---

### Task 9: 端到端集成验证

**Files:**
- Create: `tests/integration/test_agent_comm_e2e.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/integration/test_agent_comm_e2e.py
"""Agent 间通信端到端集成测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from core.agent_comm import AgentCommManager, AgentCallTool, AgentListTool
from core.plugin_registry import PluginRegistry
from core.models.plugin import PluginManifest, PluginState
from core.interfaces.agent import AgentResult


class TestAgentCommE2E:
    """端到端：权限校验 → 调用 → SSE 事件 → 调用链清理"""

    @pytest.mark.asyncio
    async def test_full_call_flow(self):
        """完整调用流程：meal_agent 调用 fitness_agent"""
        registry = MagicMock(spec=PluginRegistry)

        meal_manifest = PluginManifest(
            name="meal_agent", type="agent",
            entry_point="a:A", allowed_agents=["fitness_agent"],
        )
        fitness_manifest = PluginManifest(
            name="fitness_agent", type="agent",
            entry_point="a:A", allowed_agents=[],
        )
        registry.get_manifest.side_effect = lambda n: {
            "meal_agent": meal_manifest,
            "fitness_agent": fitness_manifest,
        }.get(n)

        mock_fitness = AsyncMock()
        mock_fitness.run_sync.return_value = AgentResult(
            session_id="test-session",
            agent="fitness_agent",
            result={"summary": "今日消耗 500 卡路里", "tool_results": []},
        )
        registry.get_agent.side_effect = lambda n: mock_fitness if n == "fitness_agent" else None

        comm = AgentCommManager(registry=registry)

        # SSE 事件收集
        events = []
        comm.set_sse_callback(lambda t, d: events.append((t, d)))

        # 执行
        tool = AgentCallTool(comm, source_agent="meal_agent")
        result = await tool.execute(
            target_agent="fitness_agent",
            message="查询今日运动消耗",
            session_id="test-session",
        )

        # 验证结果
        assert result.success is True
        assert "500 卡路里" in result.data["summary"]

        # 验证 SSE 事件
        event_types = [e[0] for e in events]
        assert "agent_delegate" in event_types
        assert "agent_delegate_done" in event_types

        # 验证 delegate 事件数据
        delegate_evt = next(e for e in events if e[0] == "agent_delegate")
        assert delegate_evt[1]["source"] == "meal_agent"
        assert delegate_evt[1]["target"] == "fitness_agent"

        # 验证调用链被清理
        assert comm._call_chains.get("test-session") is None

    @pytest.mark.asyncio
    async def test_permission_blocks_unauthorized(self):
        """未授权调用被拒绝"""
        registry = MagicMock(spec=PluginRegistry)
        registry.get_manifest.return_value = PluginManifest(
            name="agent_a", type="agent",
            entry_point="a:A", allowed_agents=[],
        )

        comm = AgentCommManager(registry=registry)
        tool = AgentCallTool(comm, source_agent="agent_a")
        result = await tool.execute(
            target_agent="agent_b",
            message="hello",
            session_id="s1",
        )
        assert result.success is False
        assert "权限" in result.error
```

- [ ] **Step 2: 运行集成测试**

Run: `python -m pytest tests/integration/test_agent_comm_e2e.py -v`
Expected: PASS

- [ ] **Step 3: 运行全部测试确保无回归**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add tests/integration/test_agent_comm_e2e.py
git commit -m "test: Agent 间通信端到端集成测试"
```

---

## 可能出现的问题

1. **循环导入**：`agent_comm.py` 和 `plugin_registry.py` 互相引用。通过 `TYPE_CHECKING` + 延迟 import 解决。
2. **pytest-asyncio**：测试需要 `pytest-asyncio` 包。确认 `requirements.txt` 或 `pyproject.toml` 中已声明。
3. **数据库连接**：`log_message` 需要数据库。集成测试中 mock 数据库或利用现有 try/except 静默失败。
4. **Pydantic v2 的 class Config**：确认 `extra = "allow"` 在 Pydantic v2 中的正确写法，可能需要 `model_config = ConfigDict(extra="allow")`。
5. **mock_fitness.run_sync 返回值类型**：`MagicMock().run_sync.return_value` 设为 `AgentResult` 对象，但 `await` 需要 coroutine。使用 `AsyncMock` 或确保 mock 正确处理 await。

## 建议的测试用例

| 场景 | 预期结果 |
|------|----------|
| v1 manifest 加载，无 allowed_agents | 默认空列表，不能调用其他 Agent |
| allowed_agents=["*"] | 可调用任意 Agent |
| A→B→A 循环调用 | 拒绝，返回循环错误 |
| 调用深度超过 3 层 | 拒绝，返回深度错误 |
| 目标 Agent 不存在 | 返回 not found 错误 |
| 目标 Agent 超时（>30s）| 返回 timeout 错误 |
| 正常调用 | 返回结果 + SSE 事件 + 通信日志 |
| 调用完成后调用链清理 | session 的 chain 为空或已删除 |
| agent_list 返回 description | 从 manifest 读取，非空 |
