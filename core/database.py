"""数据库引擎 + 表定义"""
from __future__ import annotations

import os

from sqlalchemy import Column, String, Text, DateTime, Integer, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ChatMessage(Base):
    """对话消息表"""
    __tablename__ = "chat_message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user | assistant
    content = Column(Text, nullable=False, default="")
    tool_data = Column(Text, nullable=True)  # JSON: 工具调用信息 [{tool, params, result}]
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserProfile(Base):
    """用户画像表"""
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, unique=True, index=True)
    profile_data = Column(Text, nullable=False, default="{}")  # JSON: 画像槽位
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://lifeagent:lifeagent@postgres:5432/lifeagent",
        )
        _engine = create_async_engine(url, echo=False, pool_size=5, max_overflow=10)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    """创建表（如果不存在）"""
    # 导入所有模型以注册到 Base
    import core.models.agent_message  # noqa: F401
    import core.models.delivery_address  # noqa: F401

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
