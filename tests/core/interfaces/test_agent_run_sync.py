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
