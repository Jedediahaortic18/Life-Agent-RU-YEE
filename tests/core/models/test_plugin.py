"""PluginManifest v2 字段测试"""
import pytest
from core.models.plugin import PluginManifest, PluginDependencies


class TestPluginManifestV2:

    def test_v1_manifest_defaults(self):
        m = PluginManifest(
            name="test_plugin",
            type="agent",
            entry_point="agent:TestAgent",
        )
        assert m.manifest_version == 1
        assert m.allowed_agents == []
        assert m.author == ""
        assert m.repository == ""
        assert m.license == ""
        assert m.tags == []
        assert m.min_framework_version == ""
        assert m.icon == ""
        assert m.screenshots == []
        assert m.changelog == ""

    def test_v2_manifest_full_fields(self):
        m = PluginManifest(
            manifest_version=2,
            name="fitness_agent",
            version="1.0.0",
            type="agent",
            description="AI 健身教练",
            entry_point="agent:FitnessAgent",
            author="username",
            repository="https://github.com/user/lary-fitness-agent",
            license="MIT",
            tags=["健身", "运动"],
            min_framework_version="0.2.0",
            icon="icon.png",
            screenshots=["s1.png"],
            allowed_agents=["meal_agent"],
            changelog="## 1.0.0\n- 初始版本",
        )
        assert m.manifest_version == 2
        assert m.allowed_agents == ["meal_agent"]
        assert m.author == "username"
        assert m.license == "MIT"
        assert m.tags == ["健身", "运动"]

    def test_allowed_agents_wildcard(self):
        m = PluginManifest(
            name="core_agent",
            type="agent",
            entry_point="agent:CoreAgent",
            allowed_agents=["*"],
        )
        assert m.allowed_agents == ["*"]

    def test_v1_compat_extra_fields_ignored(self):
        m = PluginManifest(
            manifest_version=1,
            name="old_plugin",
            type="memory",
            entry_point="mem:OldMem",
            some_unknown_field="hello",
        )
        assert m.name == "old_plugin"
