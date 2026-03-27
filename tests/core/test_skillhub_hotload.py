"""SkillHub 安装后热加载和配置联动测试"""
import hashlib
import io
import tarfile
import time
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from core.skillhub import SkillHubManager, RegistryIndex, RegistryPlugin


def _make_tar(manifest: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data = manifest.encode("utf-8")
        info = tarfile.TarInfo(name="test-1.0.0/manifest.yaml")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


MANIFEST = "name: test_agent\nversion: '1.0.0'\ntype: agent\nentry_point: a:A"
TAR = _make_tar(MANIFEST)
SHA = hashlib.sha256(TAR).hexdigest()


def _mock_download(data):
    mock_resp = AsyncMock()
    mock_resp.content = data
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cls


@pytest.fixture
def setup(tmp_path):
    contrib = tmp_path / "contrib"
    for d in ["agents", "memory", "extensions"]:
        (contrib / d).mkdir(parents=True)
    (contrib / ".backup").mkdir(parents=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "plugins": {"agents": [], "memory": [], "search": [], "extensions": []}
    }))

    mock_registry = MagicMock()
    mock_registry.load_plugin = MagicMock()

    hub = SkillHubManager(
        registry_url="", cache_ttl=3600,
        contrib_dir=str(contrib), backup_dir=str(contrib / ".backup"),
        registry=mock_registry,
    )
    hub._config_path = config_path
    hub._index_cache = RegistryIndex(
        version=1, plugins=[
            RegistryPlugin(
                name="test_agent", version="1.0.0", type="agent",
                download_url="https://example.com/test.tar.gz",
                sha256=SHA, verified=True,
            ),
        ],
    )
    hub._cache_time = time.time()
    return hub, mock_registry, config_path


class TestInstallHotLoad:

    @pytest.mark.asyncio
    async def test_install_triggers_hot_load(self, setup):
        hub, mock_registry, _ = setup
        with patch("httpx.AsyncClient", _mock_download(TAR)):
            await hub.install("test_agent")
        mock_registry.load_plugin.assert_called_once()

    @pytest.mark.asyncio
    async def test_install_updates_config(self, setup):
        hub, _, config_path = setup
        with patch("httpx.AsyncClient", _mock_download(TAR)):
            await hub.install("test_agent")
        config = yaml.safe_load(config_path.read_text())
        assert "test_agent" in config["plugins"]["agents"]

    @pytest.mark.asyncio
    async def test_hot_load_failure_does_not_block_install(self, setup):
        """热加载失败不影响安装结果"""
        hub, mock_registry, _ = setup
        mock_registry.load_plugin.side_effect = Exception("load failed")
        with patch("httpx.AsyncClient", _mock_download(TAR)):
            result = await hub.install("test_agent")
        assert result["status"] == "installed"
