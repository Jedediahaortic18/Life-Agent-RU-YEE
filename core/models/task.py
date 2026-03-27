"""Task 和 SubTask 模型"""
from __future__ import annotations

from pydantic import BaseModel


class SubTask(BaseModel):
    """分解后的子任务"""
    agent: str
    description: str
    depends_on: list[str] = []


class Task(BaseModel):
    """任务记录"""
    task_id: str
    session_id: str
    user_message: str
    sub_tasks: list[SubTask] = []
    status: str = "pending"  # pending | running | completed | failed
