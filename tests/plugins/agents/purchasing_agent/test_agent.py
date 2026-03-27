"""PurchasingAgent 单元测试"""
import pytest

from plugins.agents.purchasing_agent.agent import PurchasingAgent


@pytest.fixture
def agent():
    return PurchasingAgent(config={"model": "test-model"})


class TestPurchasingAgent:
    def test_agent_name(self, agent):
        assert agent.agent_name == "purchasing_agent"

    def test_capabilities(self, agent):
        caps = agent.capabilities
        assert "grocery_purchasing" in caps
        assert "hema_shopping" in caps
        assert "cart_management" in caps

    def test_get_model_from_config(self, agent):
        assert agent.get_model() == "test-model"

    def test_get_model_default(self):
        agent = PurchasingAgent()
        assert "doubao" in agent.get_model()

    def test_get_tools_empty_by_default(self, agent):
        assert agent.get_tools() == []

    def test_set_tools(self, agent):
        mock_tools = ["tool1", "tool2"]
        agent.set_tools(mock_tools)
        assert agent.get_tools() == mock_tools

    def test_get_system_prompt(self, agent):
        prompt = agent.get_system_prompt({})
        assert "盒马" in prompt
        assert "购物车" in prompt
        assert "不要结算" in prompt or "不结算" in prompt

    def test_get_system_prompt_with_shopping_list(self, agent):
        prompt = agent.get_system_prompt({"shopping_list": "白菜 x1, 鸡蛋 x1"})
        assert "白菜" in prompt
