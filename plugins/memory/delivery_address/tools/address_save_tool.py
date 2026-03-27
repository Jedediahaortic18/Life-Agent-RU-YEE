"""AddressSaveTool - 保存收货地址"""
from __future__ import annotations

from core.interfaces.tool import BaseTool, ToolResult


class AddressSaveTool(BaseTool):
    """保存收货地址"""

    name = "address_save"
    description = "保存用户配送区域地址（如小区/街道名称，无需详细门牌号）。用于定位盒马可配送区域和商品库存。"
    parameters_schema = {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "配送区域地址，如小区名或街道名（例：金台北街小区、望京SOHO），无需门牌号",
            },
        },
        "required": ["address"],
    }

    async def execute(self, **params) -> ToolResult:
        session_id = params.get("session_id", "")
        address = params.get("address", "")

        if not session_id:
            return ToolResult(success=False, error="缺少 session_id")
        if not address:
            return ToolResult(success=False, error="收货地址不能为空")

        try:
            from sqlalchemy import update

            from core.database import get_session_factory
            from core.models.delivery_address import DeliveryAddress

            async with get_session_factory()() as session:
                # 将旧的默认地址取消
                await session.execute(
                    update(DeliveryAddress)
                    .where(
                        DeliveryAddress.session_id == session_id,
                        DeliveryAddress.is_default.is_(True),
                    )
                    .values(is_default=False)
                )

                new_addr = DeliveryAddress(
                    session_id=session_id,
                    name="",
                    phone="",
                    address=address,
                    is_default=True,
                )
                session.add(new_addr)
                await session.commit()

            return ToolResult(
                success=True,
                data={
                    "message": "配送区域已保存",
                    "address": address,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"保存地址失败: {e}")
