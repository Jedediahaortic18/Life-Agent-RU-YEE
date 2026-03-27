"""TaskDecomposer - 任务分解器（MVP 直通模式）"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.models.intent import IntentResult
from core.models.task import SubTask

if TYPE_CHECKING:
    from core.plugin_registry import PluginRegistry


class TaskDecomposer:
    """MVP 阶段：单 Agent 直通，多 Agent 时 LLM 分解"""

    def __init__(self, registry: "PluginRegistry") -> None:
        self._registry = registry

    async def decompose(self, intent: IntentResult) -> list[SubTask]:
        # MVP: 单 Agent 直通
        agents = self._registry.list_plugins(plugin_type="agent")
        if len(agents) <= 1:
            return [SubTask(agent=intent.agent, description=intent.task_description)]

        # 多 Agent 场景也暂时直通（未来 LLM 分解）
        return [SubTask(agent=intent.agent, description=intent.task_description)]
