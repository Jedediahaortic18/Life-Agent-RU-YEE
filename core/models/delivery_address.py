"""DeliveryAddress - 收货地址表"""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from core.database import Base


class DeliveryAddress(Base):
    """用户收货地址"""
    __tablename__ = "delivery_address"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    name = Column(String(64), nullable=False, default="")
    phone = Column(String(20), nullable=False)
    address = Column(Text, nullable=False)
    is_default = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
