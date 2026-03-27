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
