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
