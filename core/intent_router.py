"""IntentRouter - 意图路由器"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import litellm
from loguru import logger

from core.models.intent import IntentResult

if TYPE_CHECKING:
    from core.plugin_registry import PluginRegistry


class IntentRouter:
    """根据已注册 Agent 的 capabilities 动态路由用户意图"""

    def __init__(self, registry: "PluginRegistry", model: str = "volcengine/doubao-seed-2-0-pro-260215") -> None:
        self._registry = registry
        self._model = model
        self._prompt_cache: str | None = None

    def _build_routing_prompt(self, user_message: str, agents: list | None = None) -> str:
        """动态生成路由 prompt"""
        if agents is None:
            agents = self._registry.list_plugins(plugin_type="agent")
        if not agents:
            return ""

        agent_lines = []
        for agent in agents:
            caps = ", ".join(agent.capabilities) if agent.capabilities else "general"
            agent_lines.append(f"- {agent.name}: {caps}")

        agents_section = "\n".join(agent_lines)

        return f"""你是一个意图路由器。根据用户输入，选择最合适的 Agent。

可用 Agent：
{agents_section}

用户输入: "{user_message}"

请严格返回以下 JSON 格式（不要返回其他内容）：
{{"agent": "agent_name", "confidence": 0.0-1.0, "task_description": "任务描述"}}"""

    async def route(self, user_message: str) -> IntentResult:
        """路由用户消息到合适的 Agent"""
        all_agents = self._registry.list_plugins(plugin_type="agent")
        # 过滤掉 routable=false 的 agent（仅作为子 agent 被调用）
        agents = [
            a for a in all_agents
            if self._registry.get_manifest(a.name) is None
            or getattr(self._registry.get_manifest(a.name), "routable", True) is not False
        ]

        # 只有一个 Agent 时直接返回
        if len(agents) == 1:
            return IntentResult(
                agent=agents[0].name,
                confidence=1.0,
                task_description=user_message,
            )

        # 没有 Agent
        if not agents:
            return IntentResult(
                agent="",
                confidence=0.0,
                task_description="没有可用的 Agent",
            )

        # 多个 Agent 时用 LLM 路由
        prompt = self._build_routing_prompt(user_message, agents)
        try:
            response = await litellm.acompletion(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            content = response.choices[0].message.content.strip()

            # 提取 JSON
            if "{" in content:
                json_str = content[content.index("{"):content.rindex("}") + 1]
                parsed = json.loads(json_str)
                return IntentResult(**parsed)

        except Exception as e:
            logger.error(f"IntentRouter failed: {e}")

        # fallback: 选第一个 Agent
        return IntentResult(
            agent=agents[0].name,
            confidence=0.5,
            task_description=user_message,
        )
