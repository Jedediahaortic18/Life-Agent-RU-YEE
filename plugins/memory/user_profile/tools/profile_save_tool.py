"""ProfileSaveTool - 保存/更新用户画像"""
from __future__ import annotations

import json
from typing import Any

from core.interfaces.tool import BaseTool, ToolResult


class ProfileSaveTool(BaseTool):
    """保存或更新用户饮食画像的某个槽位"""

    @property
    def name(self) -> str:
        return "profile_save"

    @property
    def description(self) -> str:
        return (
            "保存或更新用户画像信息。每当用户回答了偏好问题后，"
            "立即调用此工具将信息持久化。支持的槽位：family_size, family_members, "
            "taste, cuisine, restrictions, health_goal, cooking_skill, budget, scene。"
            "可以一次更新多个槽位。"
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "family_size": {
                    "type": "string",
                    "description": "家庭用餐人数，如：1-2人、3口之家、4-5人",
                },
                "family_members": {
                    "type": "string",
                    "description": "家庭成员构成，如：两大一小、有老人、有孕妇",
                },
                "taste": {
                    "type": "string",
                    "description": "口味偏好，如：清淡、微辣、重辣、不挑",
                },
                "cuisine": {
                    "type": "string",
                    "description": "偏好菜系，如：川湘菜、粤菜、家常菜、都喜欢",
                },
                "restrictions": {
                    "type": "string",
                    "description": "饮食限制，如：海鲜过敏、素食、不吃牛肉、清真、无",
                },
                "health_goal": {
                    "type": "string",
                    "description": "健康目标，如：减脂、增肌、均衡、控糖、无特殊",
                },
                "cooking_skill": {
                    "type": "string",
                    "description": "厨艺水平，如：新手、会做家常菜、厨艺不错",
                },
                "budget": {
                    "type": "string",
                    "description": "预算倾向，如：经济实惠、适中、不限",
                },
                "scene": {
                    "type": "string",
                    "description": "餐食场景，如：日常家常、便当、待客、周末改善",
                },
            },
            "required": [],
        }

    async def execute(self, **params: Any) -> ToolResult:
        session_id = params.pop("session_id", "")
        if not session_id:
            return ToolResult(success=False, error="缺少 session_id")

        # 提取要更新的槽位（排除空值）
        valid_slots = {
            "family_size", "family_members", "taste", "cuisine",
            "restrictions", "health_goal", "cooking_skill", "budget", "scene",
        }
        updates = {k: v for k, v in params.items() if k in valid_slots and v}

        if not updates:
            return ToolResult(success=False, error="没有提供要更新的画像信息")

        try:
            from core.database import get_session_factory, UserProfile
            from sqlalchemy import select

            factory = get_session_factory()
            async with factory() as session:
                stmt = select(UserProfile).where(UserProfile.session_id == session_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()

                if row:
                    profile = json.loads(row.profile_data) if row.profile_data else {}
                    profile.update(updates)
                    row.profile_data = json.dumps(profile, ensure_ascii=False)
                else:
                    profile = updates
                    row = UserProfile(
                        session_id=session_id,
                        profile_data=json.dumps(profile, ensure_ascii=False),
                    )
                    session.add(row)

                await session.commit()

            return ToolResult(
                success=True,
                data={
                    "updated_slots": list(updates.keys()),
                    "profile": profile,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
