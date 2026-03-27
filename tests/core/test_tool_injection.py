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
