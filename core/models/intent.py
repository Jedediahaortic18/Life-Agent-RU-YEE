"""IntentResult 模型"""
from __future__ import annotations

from pydantic import BaseModel


class IntentResult(BaseModel):
    """意图路由结果"""
    agent: str
    confidence: float
    task_description: str
