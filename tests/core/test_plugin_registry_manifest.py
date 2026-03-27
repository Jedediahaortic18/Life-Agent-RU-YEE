"""PluginRegistry.get_manifest 测试"""
import pytest
from core.plugin_registry import PluginRegistry
from core.models.plugin import PluginManifest


class TestGetManifest:

    def test_get_existing_manifest(self):
        registry = PluginRegistry()
        manifest = PluginManifest(name="test", type="agent", entry_point="a:A")
        registry._manifests["test"] = manifest
        assert registry.get_manifest("test") is manifest

    def test_get_nonexistent_manifest(self):
        registry = PluginRegistry()
        assert registry.get_manifest("nonexistent") is None
