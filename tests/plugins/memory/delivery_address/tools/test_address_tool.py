"""AddressGetTool / AddressSaveTool 单元测试"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plugins.memory.delivery_address.tools.address_get_tool import AddressGetTool
from plugins.memory.delivery_address.tools.address_save_tool import AddressSaveTool


# ── AddressGetTool ──────────────────────────────────


class TestAddressGetTool:

    def test_metadata(self):
        tool = AddressGetTool()
        assert tool.name == "address_get"
        assert "收货地址" in tool.description

    async def test_missing_session_id(self):
        tool = AddressGetTool()
        result = await tool.execute()
        assert result.success is False
        assert "session_id" in result.error

    async def test_address_found(self):
        tool = AddressGetTool()

        mock_addr = MagicMock()
        mock_addr.name = "张三"
        mock_addr.phone = "13800138000"
        mock_addr.address = "北京市朝阳区xx路1号"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_addr

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = False
        mock_factory.return_value = mock_ctx

        with patch("core.database.get_session_factory", return_value=mock_factory):
            result = await tool.execute(session_id="test-session")

        assert result.success is True
        assert result.data["found"] is True
        assert result.data["phone"] == "13800138000"
        assert result.data["address"] == "北京市朝阳区xx路1号"

    async def test_address_not_found(self):
        tool = AddressGetTool()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = False
        mock_factory.return_value = mock_ctx

        with patch("core.database.get_session_factory", return_value=mock_factory):
            result = await tool.execute(session_id="test-session")

        assert result.success is True
        assert result.data["found"] is False

    async def test_db_error(self):
        tool = AddressGetTool()

        with patch(
            "core.database.get_session_factory",
            side_effect=RuntimeError("db down"),
        ):
            result = await tool.execute(session_id="test-session")

        assert result.success is False
        assert "查询地址失败" in result.error


# ── AddressSaveTool ─────────────────────────────────


class TestAddressSaveTool:

    def test_metadata(self):
        tool = AddressSaveTool()
        assert tool.name == "address_save"
        assert "name" in tool.parameters_schema["required"]
        assert "phone" in tool.parameters_schema["required"]
        assert "address" in tool.parameters_schema["required"]

    async def test_missing_session_id(self):
        tool = AddressSaveTool()
        result = await tool.execute(name="张三", phone="13800138000", address="北京")
        assert result.success is False
        assert "session_id" in result.error

    async def test_missing_required_fields(self):
        tool = AddressSaveTool()
        result = await tool.execute(session_id="s1", name="", phone="", address="")
        assert result.success is False
        assert "不能为空" in result.error

    async def test_missing_name(self):
        tool = AddressSaveTool()
        result = await tool.execute(session_id="s1", name="", phone="13800138000", address="北京")
        assert result.success is False
        assert "不能为空" in result.error

    async def test_save_success(self):
        tool = AddressSaveTool()

        mock_session = AsyncMock()
        mock_session.execute.return_value = None
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_ctx.__aexit__.return_value = False
        mock_factory.return_value = mock_ctx

        with patch("core.database.get_session_factory", return_value=mock_factory):
            result = await tool.execute(
                session_id="s1",
                name="李四",
                phone="13900139000",
                address="上海市浦东新区xx路2号",
            )

        assert result.success is True
        assert result.data["phone"] == "13900139000"
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    async def test_save_db_error(self):
        tool = AddressSaveTool()

        with patch(
            "core.database.get_session_factory",
            side_effect=RuntimeError("db down"),
        ):
            result = await tool.execute(
                session_id="s1",
                name="张三",
                phone="13800138000",
                address="北京",
            )

        assert result.success is False
        assert "保存地址失败" in result.error
