"""DeliveryAddress 模型测试"""
from core.models.delivery_address import DeliveryAddress


def test_delivery_address_tablename():
    assert DeliveryAddress.__tablename__ == "delivery_address"


def test_delivery_address_columns():
    cols = {c.name for c in DeliveryAddress.__table__.columns}
    expected = {"id", "session_id", "name", "phone", "address", "is_default", "created_at", "updated_at"}
    assert cols == expected


def test_delivery_address_defaults():
    """is_default 默认值为 True"""
    col = DeliveryAddress.__table__.c.is_default
    assert col.default.arg is True
