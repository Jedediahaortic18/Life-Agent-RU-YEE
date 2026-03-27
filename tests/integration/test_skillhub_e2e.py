"""SkillHub 端到端集成测试"""
import hashlib
import io
import tarfile
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from core.skillhub import (
    SkillHubManager, RegistryIndex, RegistryPlugin,
    validate_manifest_for_publish, validate_plugin_dir, package_plugin,
)


MANIFEST_CONTENT = (
    "manifest_version: 2\nname: test_agent\nversion: '1.0.0'\ntype: agent\n"
    "description: Test\nentry_point: agent:A\nauthor: u\n"
    "repository: https://github.com/t\nlicense: MIT\ntags: [test]\n"
)


def _make_tar(manifest: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        data = manifest.encode("utf-8")
        info = tarfile.TarInfo(name="test_agent-1.0.0/manifest.yaml")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
        agent = b"class A: pass"
        info2 = tarfile.TarInfo(name="test_agent-1.0.0/agent.py")
        info2.size = len(agent)
        tf.addfile(info2, io.BytesIO(agent))
    return buf.getvalue()


def _mock_dl(data):
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
def e2e(tmp_path):
    contrib = tmp_path / "contrib"
    for d in ["agents", "memory", "extensions"]:
        (contrib / d).mkdir(parents=True)
    (contrib / ".backup").mkdir(parents=True)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "plugins": {"agents": [], "memory": [], "search": [], "extensions": []}
    }))

    tar_bytes = _make_tar(MANIFEST_CONTENT)
    sha256 = hashlib.sha256(tar_bytes).hexdigest()

    mock_reg = MagicMock()
    mock_reg.load_plugin = MagicMock()
    mock_reg.unload_plugin = MagicMock()

    hub = SkillHubManager(
        registry_url="https://example.com/index.json",
        cache_ttl=3600,
        contrib_dir=str(contrib), backup_dir=str(contrib / ".backup"),
        registry=mock_reg,
    )
    hub._config_path = config_path
    hub._index_cache = RegistryIndex(
        version=1, plugins=[
            RegistryPlugin(
                name="test_agent", version="1.0.0", type="agent",
                download_url="https://example.com/test.tar.gz",
                sha256=sha256, verified=True, tags=["test"],
            ),
        ],
    )
    hub._cache_time = time.time()
    return hub, contrib, config_path, tar_bytes


class TestSkillHubE2E:

    @pytest.mark.asyncio
    async def test_search_install_uninstall(self, e2e):
        """完整流程：搜索 → 安装 → 重复安装 → 卸载"""
        hub, contrib, config_path, tar_bytes = e2e

        # 搜索
        results = await hub.search(q="test")
        assert len(results) == 1

        # 安装
        with patch("httpx.AsyncClient", _mock_dl(tar_bytes)):
            result = await hub.install("test_agent")
        assert result["status"] == "installed"
        assert (contrib / "agents" / "test_agent" / "manifest.yaml").exists()

        config = yaml.safe_load(config_path.read_text())
        assert "test_agent" in config["plugins"]["agents"]

        # 重复安装
        result2 = await hub.install("test_agent")
        assert result2["status"] == "already_latest"

        # 列表
        installed = hub.list_installed()
        assert any(p["name"] == "test_agent" for p in installed)

        # 卸载
        result3 = await hub.uninstall("test_agent")
        assert result3["status"] == "uninstalled"
        assert not (contrib / "agents" / "test_agent").exists()

        config = yaml.safe_load(config_path.read_text())
        assert "test_agent" not in config["plugins"]["agents"]

    @pytest.mark.asyncio
    async def test_publish_validation_e2e(self, e2e):
        """发布校验完整流程"""
        # 校验 manifest
        raw = yaml.safe_load(MANIFEST_CONTENT)
        errors = validate_manifest_for_publish(raw)
        assert errors == []
