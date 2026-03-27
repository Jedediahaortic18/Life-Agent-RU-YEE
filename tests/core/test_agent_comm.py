"""AgentCommManager 测试"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from core.agent_comm import AgentCommManager, AgentListTool, AgentCallTool
from core.interfaces.agent import AgentResult, SSEEvent
from core.models.plugin import PluginManifest, PluginState


async def _mock_agent_run(message, session_id=None):
    """模拟 agent.run() 的 async iterator 返回"""
    yield SSEEvent(event="text_delta", data={"content": "运动量正常"})
    yield SSEEvent(event="done", data={"session_id": session_id or "", "agent": "fitness_agent"})


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    registry.list_plugins.return_value = [
        PluginState(name="meal_agent", type="agent", version="0.1.0",
                    status="loaded", capabilities=["meal_recommend"]),
        PluginState(name="fitness_agent", type="agent", version="1.0.0",
                    status="loaded", capabilities=["workout"]),
    ]
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


# ── agent_call 测试 ──────────────────────────────

@pytest.fixture
def mock_registry_with_manifests():
    registry = MagicMock()
    registry.list_plugins.return_value = [
        PluginState(name="meal_agent", type="agent", version="0.1.0", status="loaded"),
        PluginState(name="fitness_agent", type="agent", version="1.0.0", status="loaded"),
    ]

    mock_fitness = MagicMock()
    mock_fitness.run = _mock_agent_run
    registry.get_agent.side_effect = lambda name: mock_fitness if name == "fitness_agent" else None

    meal_manifest = PluginManifest(
        name="meal_agent", type="agent", entry_point="a:A",
        allowed_agents=["fitness_agent"],
    )
    fitness_manifest = PluginManifest(
        name="fitness_agent", type="agent", entry_point="a:A",
        allowed_agents=[],
    )
    # 循环/深度测试用的虚拟 manifest（allowed_agents=["*"] 允许所有）
    wildcard_manifest = PluginManifest(
        name="_wildcard", type="agent", entry_point="a:A",
        allowed_agents=["*"],
    )
    registry.get_manifest.side_effect = lambda name: {
        "meal_agent": meal_manifest,
        "fitness_agent": fitness_manifest,
        "a": wildcard_manifest,
        "b": wildcard_manifest,
        "c": wildcard_manifest,
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
    async def test_call_target_not_found(self, comm_with_manifests):
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
        comm_with_manifests._call_chains["s1"] = ["a", "b"]
        tool = AgentCallTool(comm_with_manifests, source_agent="b")
        result = await tool.execute(
            target_agent="a",
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
        mock_agent = comm_with_manifests._registry.get_agent("fitness_agent")

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(60)
            yield SSEEvent(event="done", data={})

        mock_agent.run = slow_run
        comm_with_manifests.CALL_TIMEOUT = 0.1

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
        tool = AgentCallTool(comm_with_manifests, source_agent="meal_agent")
        await tool.execute(
            target_agent="fitness_agent",
            message="test",
            session_id="s1",
        )
        assert comm_with_manifests._call_chains.get("s1", []) == []

    @pytest.mark.asyncio
    async def test_chain_cleaned_after_timeout(self, comm_with_manifests):
        mock_agent = comm_with_manifests._registry.get_agent("fitness_agent")

        async def slow_run(*args, **kwargs):
            await asyncio.sleep(60)
            yield SSEEvent(event="done", data={})

        mock_agent.run = slow_run
        comm_with_manifests.CALL_TIMEOUT = 0.1

        tool = AgentCallTool(comm_with_manifests, source_agent="meal_agent")
        await tool.execute(
            target_agent="fitness_agent",
            message="test",
            session_id="s1",
        )
        assert comm_with_manifests._call_chains.get("s1", []) == []
