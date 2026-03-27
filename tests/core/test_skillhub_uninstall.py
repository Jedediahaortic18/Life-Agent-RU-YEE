"""SkillHub 卸载测试"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from core.skillhub import SkillHubManager


MANIFEST_YAML = """
name: fitness_agent
version: "1.0.0"
type: agent
entry_point: agent:FitnessAgent
"""


@pytest.fixture
def hub_with_installed(tmp_path):
    contrib = tmp_path / "contrib"
    backup = tmp_path / "contrib" / ".backup"
    for d in ["agents", "memory", "extensions"]:
        (contrib / d).mkdir(parents=True)
    backup.mkdir(parents=True)

    # 模拟已安装插件
    plugin_dir = contrib / "agents" / "fitness_agent"
    plugin_dir.mkdir()
    (plugin_dir / "manifest.yaml").write_text(MANIFEST_YAML)

    mock_registry = MagicMock()
    mock_registry.unload_plugin = MagicMock()

    hub = SkillHubManager(
        registry_url="",
        cache_ttl=3600,
        contrib_dir=str(contrib),
        backup_dir=str(backup),
        registry=mock_registry,
    )
    hub._config_path = tmp_path / "config.yaml"
    hub._config_path.write_text(yaml.dump({
        "plugins": {"agents": ["fitness_agent"], "memory": [], "search": [], "extensions": []}
    }))
    return hub, contrib


class TestUninstallPlugin:

    @pytest.mark.asyncio
    async def test_uninstall_removes_directory(self, hub_with_installed):
        hub, contrib = hub_with_installed
        result = await hub.uninstall("fitness_agent")
        assert result["status"] == "uninstalled"
        assert not (contrib / "agents" / "fitness_agent").exists()

    @pytest.mark.asyncio
    async def test_uninstall_calls_registry_unload(self, hub_with_installed):
        hub, _ = hub_with_installed
        await hub.uninstall("fitness_agent")
        hub._plugin_registry.unload_plugin.assert_called_once_with("fitness_agent")

    @pytest.mark.asyncio
    async def test_uninstall_updates_config(self, hub_with_installed):
        hub, _ = hub_with_installed
        await hub.uninstall("fitness_agent")
        config = yaml.safe_load(hub._config_path.read_text())
        assert "fitness_agent" not in config["plugins"]["agents"]

    @pytest.mark.asyncio
    async def test_uninstall_not_in_contrib(self, hub_with_installed):
        """contrib 中不存在的插件 → 报错"""
        hub, _ = hub_with_installed
        with pytest.raises(ValueError, match="not installed"):
            await hub.uninstall("nonexistent")

    @pytest.mark.asyncio
    async def test_list_installed(self, hub_with_installed):
        hub, _ = hub_with_installed
        installed = hub.list_installed()
        assert len(installed) == 1
        assert installed[0]["name"] == "fitness_agent"
        assert installed[0]["source"] == "contrib"
