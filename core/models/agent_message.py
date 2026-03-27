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
    result = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="success")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
