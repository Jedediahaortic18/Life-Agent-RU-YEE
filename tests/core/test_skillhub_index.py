# tests/core/test_skillhub_index.py
"""SkillHub 索引管理测试"""
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.skillhub import SkillHubManager, RegistryIndex, RegistryPlugin


SAMPLE_INDEX = {
    "version": 1,
    "updated_at": "2026-03-24T12:00:00Z",
    "plugins": [
        {
            "name": "fitness_agent",
            "version": "1.0.0",
            "type": "agent",
            "description": "AI 健身教练",
            "author": "testuser",
            "tags": ["健身", "运动"],
            "min_framework_version": "0.2.0",
            "download_url": "https://example.com/fitness.tar.gz",
            "manifest_url": "https://example.com/manifest.yaml",
            "sha256": "abc123",
            "verified": True,
            "created_at": "2026-03-24",
            "updated_at": "2026-03-24",
        },
    ],
}


def _mock_httpx_client(mock_response):
    """创建正确 mock httpx.AsyncClient 上下文管理器的辅助函数"""
    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_client_cls


class TestRegistryIndex:

    def test_parse_index(self):
        idx = RegistryIndex(**SAMPLE_INDEX)
        assert idx.version == 1
        assert len(idx.plugins) == 1
        assert idx.plugins[0].name == "fitness_agent"
        assert idx.plugins[0].sha256 == "abc123"
        assert idx.plugins[0].verified is True


class TestSkillHubIndexFetch:

    @pytest.mark.asyncio
    async def test_fetch_remote_index(self):
        """首次拉取远程索引"""
        hub = SkillHubManager(
            registry_url="https://example.com/index.json",
            cache_ttl=3600,
            contrib_dir="/tmp/test_contrib",
            backup_dir="/tmp/test_contrib/.backup",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=SAMPLE_INDEX)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient", _mock_httpx_client(mock_response)):
            index = await hub.fetch_index()
            assert index.version == 1
            assert len(index.plugins) == 1

    @pytest.mark.asyncio
    async def test_index_cache_hit(self):
        """缓存未过期时不重新拉取"""
        hub = SkillHubManager(
            registry_url="https://example.com/index.json",
            cache_ttl=3600,
            contrib_dir="/tmp/test_contrib",
            backup_dir="/tmp/test_contrib/.backup",
        )

        hub._index_cache = RegistryIndex(**SAMPLE_INDEX)
        hub._cache_time = time.time()  # 刚缓存

        # 不 mock httpx → 如果发起网络请求会报错
        index = await hub.fetch_index()
        assert index.plugins[0].name == "fitness_agent"

    @pytest.mark.asyncio
    async def test_index_cache_expired(self):
        """缓存过期后重新拉取"""
        hub = SkillHubManager(
            registry_url="https://example.com/index.json",
            cache_ttl=3600,
            contrib_dir="/tmp/test_contrib",
            backup_dir="/tmp/test_contrib/.backup",
        )

        hub._index_cache = RegistryIndex(**SAMPLE_INDEX)
        hub._cache_time = time.time() - 7200  # 2 小时前

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=SAMPLE_INDEX)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient", _mock_httpx_client(mock_response)):
            index = await hub.fetch_index()
            assert index is not None

    @pytest.mark.asyncio
    async def test_fetch_index_network_error(self):
        """网络错误应抛出异常"""
        hub = SkillHubManager(
            registry_url="https://example.com/index.json",
            cache_ttl=3600,
            contrib_dir="/tmp/test_contrib",
            backup_dir="/tmp/test_contrib/.backup",
        )

        import httpx
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
        mock_client_cls = MagicMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", mock_client_cls):
            with pytest.raises(httpx.ConnectError):
                await hub.fetch_index()


class TestSkillHubSearch:

    def _hub_with_cache(self):
        hub = SkillHubManager(
            registry_url="", cache_ttl=3600,
            contrib_dir="/tmp", backup_dir="/tmp/.backup",
        )
        hub._index_cache = RegistryIndex(**SAMPLE_INDEX)
        hub._cache_time = time.time()
        return hub

    @pytest.mark.asyncio
    async def test_search_by_keyword(self):
        results = await self._hub_with_cache().search(q="健身")
        assert len(results) == 1
        assert results[0].name == "fitness_agent"

    @pytest.mark.asyncio
    async def test_search_by_tag(self):
        results = await self._hub_with_cache().search(tags=["运动"])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_by_type(self):
        results = await self._hub_with_cache().search(plugin_type="memory")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_no_match(self):
        results = await self._hub_with_cache().search(q="不存在")
        assert len(results) == 0
