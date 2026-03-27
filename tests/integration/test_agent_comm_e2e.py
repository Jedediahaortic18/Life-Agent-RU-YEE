"""Agent 间通信端到端集成测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from core.agent_comm import AgentCommManager, AgentCallTool, AgentListTool
from core.plugin_registry import PluginRegistry
from core.models.plugin import PluginManifest, PluginState
from core.interfaces.agent import AgentResult, SSEEvent


async def _mock_fitness_run(message, session_id=None):
    """模拟 fitness_agent.run() 流式输出"""
    yield SSEEvent(event="text_delta", data={"content": "今日消耗 500 卡路里"})
    yield SSEEvent(event="done", data={"session_id": session_id or "", "agent": "fitness_agent"})


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

        mock_fitness = MagicMock()
        mock_fitness.run = _mock_fitness_run
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
        assert "agent_progress" in event_types
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
