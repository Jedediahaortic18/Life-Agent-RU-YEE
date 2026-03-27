"""SkillHub 安装流程测试"""
import hashlib
import io
import tarfile
import pytest
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.skillhub import SkillHubManager, RegistryIndex, RegistryPlugin


def _make_tar_bytes(manifest_content: str) -> bytes:
    """创建包含 manifest.yaml 的 tar.gz 字节"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name="fitness_agent-1.0.0/manifest.yaml")
        content = manifest_content.encode("utf-8")
        info.size = len(content)
        tf.addfile(info, io.BytesIO(content))

        agent_content = b"class FitnessAgent: pass"
        info2 = tarfile.TarInfo(name="fitness_agent-1.0.0/agent.py")
        info2.size = len(agent_content)
        tf.addfile(info2, io.BytesIO(agent_content))
    return buf.getvalue()


SAMPLE_MANIFEST = """
manifest_version: 2
name: fitness_agent
version: "1.0.0"
type: agent
description: "AI 健身教练"
entry_point: agent:FitnessAgent
author: testuser
repository: "https://github.com/test"
license: MIT
"""

TAR_BYTES = _make_tar_bytes(SAMPLE_MANIFEST)
TAR_SHA256 = hashlib.sha256(TAR_BYTES).hexdigest()


def _mock_httpx_download(tar_bytes: bytes):
    """Mock httpx 下载响应"""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.content = tar_bytes
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cls


@pytest.fixture
def hub(tmp_path):
    contrib = tmp_path / "contrib"
    backup = tmp_path / "contrib" / ".backup"
    for d in ["agents", "memory", "extensions"]:
        (contrib / d).mkdir(parents=True)
    backup.mkdir(parents=True)

    mock_registry = MagicMock()
    mock_registry.load_plugin = MagicMock()

    h = SkillHubManager(
        registry_url="https://example.com/index.json",
        cache_ttl=3600,
        contrib_dir=str(contrib),
        backup_dir=str(backup),
        registry=mock_registry,
    )
    h._config_path = tmp_path / "config.yaml"
    h._config_path.write_text("plugins:\n  agents: []\n  memory: []\n  search: []\n  extensions: []\n")
    h._index_cache = RegistryIndex(
        version=1,
        plugins=[
            RegistryPlugin(
                name="fitness_agent", version="1.0.0", type="agent",
                description="AI 健身教练",
                download_url="https://example.com/fitness.tar.gz",
                sha256=TAR_SHA256, verified=True,
            ),
        ],
    )
    h._cache_time = time.time()
    return h, contrib


class TestInstallPlugin:

    @pytest.mark.asyncio
    async def test_install_new_plugin(self, hub):
        """安装新插件 → 解压到 contrib/{type}/{name}/"""
        h, contrib = hub

        with patch("httpx.AsyncClient", _mock_httpx_download(TAR_BYTES)):
            result = await h.install("fitness_agent")

        assert result["status"] == "installed"
        plugin_dir = contrib / "agents" / "fitness_agent"
        assert plugin_dir.exists()
        assert (plugin_dir / "manifest.yaml").exists()
        assert (plugin_dir / "agent.py").exists()

    @pytest.mark.asyncio
    async def test_install_sha256_mismatch(self, hub):
        """SHA256 不匹配 → 拒绝安装"""
        h, _ = hub

        with patch("httpx.AsyncClient", _mock_httpx_download(b"corrupted data")):
            with pytest.raises(ValueError, match="SHA256"):
                await h.install("fitness_agent")

    @pytest.mark.asyncio
    async def test_install_already_latest(self, hub):
        """已安装相同版本 → 跳过"""
        h, contrib = hub
        plugin_dir = contrib / "agents" / "fitness_agent"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "manifest.yaml").write_text(SAMPLE_MANIFEST)

        result = await h.install("fitness_agent")
        assert result["status"] == "already_latest"

    @pytest.mark.asyncio
    async def test_install_upgrade_with_backup(self, hub):
        """已安装不同版本 → 备份旧版 + 覆盖安装"""
        h, contrib = hub
        plugin_dir = contrib / "agents" / "fitness_agent"
        plugin_dir.mkdir(parents=True)
        old_manifest = SAMPLE_MANIFEST.replace('version: "1.0.0"', 'version: "0.9.0"')
        (plugin_dir / "manifest.yaml").write_text(old_manifest)

        with patch("httpx.AsyncClient", _mock_httpx_download(TAR_BYTES)):
            result = await h.install("fitness_agent")

        assert result["status"] == "upgraded"
        backup_path = h._backup_dir / "fitness_agent-0.9.0"
        assert backup_path.exists()

    @pytest.mark.asyncio
    async def test_install_plugin_not_in_index(self, hub):
        """插件不在索引中 → 报错"""
        h, _ = hub
        with pytest.raises(ValueError, match="not found"):
            await h.install("nonexistent_plugin")

    @pytest.mark.asyncio
    async def test_install_oversized_download(self, hub):
        """超过大小限制 → 拒绝"""
        h, _ = hub
        h._max_download_bytes = 10  # 10 字节限制

        with patch("httpx.AsyncClient", _mock_httpx_download(TAR_BYTES)):
            with pytest.raises(ValueError, match="大小"):
                await h.install("fitness_agent")

    @pytest.mark.asyncio
    async def test_install_path_traversal_rejected(self, hub):
        """tar.gz 含路径遍历 → 拒绝"""
        h, _ = hub
        # 创建含恶意路径的 tar
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            info = tarfile.TarInfo(name="evil-1.0.0/../../etc/passwd")
            info.size = 5
            tf.addfile(info, io.BytesIO(b"hello"))
            info2 = tarfile.TarInfo(name="evil-1.0.0/manifest.yaml")
            manifest = b"name: fitness_agent\nversion: '1.0.0'\ntype: agent\nentry_point: a:A"
            info2.size = len(manifest)
            tf.addfile(info2, io.BytesIO(manifest))
        evil_bytes = buf.getvalue()
        evil_sha = hashlib.sha256(evil_bytes).hexdigest()

        h._index_cache.plugins[0].sha256 = evil_sha

        with patch("httpx.AsyncClient", _mock_httpx_download(evil_bytes)):
            with pytest.raises(ValueError, match="不安全"):
                await h.install("fitness_agent")
