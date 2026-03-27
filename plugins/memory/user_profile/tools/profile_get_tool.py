"""ProfileGetTool - 获取用户画像"""
from __future__ import annotations

import json
from typing import Any

from core.interfaces.tool import BaseTool, ToolResult

# 画像槽位定义及中文标签
SLOT_LABELS = {
    "family_size": "家庭人数",
    "family_members": "家庭成员",
    "taste": "口味偏好",
    "cuisine": "偏好菜系",
    "restrictions": "饮食限制",
    "health_goal": "健康目标",
    "cooking_skill": "厨艺水平",
    "budget": "预算倾向",
    "scene": "餐食场景",
}


class ProfileGetTool(BaseTool):
    """获取用户饮食画像，了解已收集的偏好信息"""

    @property
    def name(self) -> str:
        return "profile_get"

    @property
    def description(self) -> str:
        return (
            "获取当前用户的饮食画像。在规划菜谱前必须先调用此工具，"
            "查看已有的用户偏好信息，避免重复询问。"
            "返回已填写的槽位和未填写的槽位列表。"
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, **params: Any) -> ToolResult:
        session_id = params.get("session_id", "")
        if not session_id:
            return ToolResult(success=False, error="缺少 session_id")

        try:
            from core.database import get_session_factory, UserProfile
            from sqlalchemy import select

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(UserProfile).where(UserProfile.session_id == session_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()

            if row and row.profile_data:
                profile = json.loads(row.profile_data)
            else:
                profile = {}

            filled = {}
            missing = []
            for key, label in SLOT_LABELS.items():
                val = profile.get(key)
                if val:
                    filled[label] = val
                else:
                    missing.append(label)

            filled_count = len(filled)
            total = len(SLOT_LABELS)

            return ToolResult(
                success=True,
                data={
                    "profile": profile,
                    "filled": filled,
                    "missing": missing,
                    "filled_count": filled_count,
                    "total": total,
                    "ready": filled_count >= 4,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
