"""AddressGetTool - 查询默认收货地址"""
from __future__ import annotations

from core.interfaces.tool import BaseTool, ToolResult


class AddressGetTool(BaseTool):
    """查询当前会话的默认收货地址"""

    name = "address_get"
    description = "查询用户的默认配送区域地址。返回 address 或空（表示尚未设置）。地址仅用于定位盒马配送区域，非实际收货地址。"
    parameters_schema = {"type": "object", "properties": {}}

    async def execute(self, **params) -> ToolResult:
        session_id = params.get("session_id", "")
        if not session_id:
            return ToolResult(success=False, error="缺少 session_id")

        try:
            from sqlalchemy import select

            from core.database import get_session_factory
            from core.models.delivery_address import DeliveryAddress

            async with get_session_factory()() as session:
                stmt = (
                    select(DeliveryAddress)
                    .where(
                        DeliveryAddress.session_id == session_id,
                        DeliveryAddress.is_default.is_(True),
                    )
                    .order_by(DeliveryAddress.updated_at.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                addr = result.scalar_one_or_none()

            if addr is None:
                return ToolResult(
                    success=True,
                    data={"found": False},
                )

            return ToolResult(
                success=True,
                data={
                    "found": True,
                    "address": addr.address,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"查询地址失败: {e}")
