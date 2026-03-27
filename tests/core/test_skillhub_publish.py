"""SkillHub 发布校验和打包测试"""
import tarfile
import pytest
from pathlib import Path

from core.skillhub import validate_manifest_for_publish, validate_plugin_dir, package_plugin


class TestManifestPublishValidation:

    def test_valid_v2_manifest(self):
        raw = {
            "manifest_version": 2, "name": "test", "version": "1.0.0",
            "type": "agent", "entry_point": "a:A",
            "author": "user", "repository": "https://github.com/test", "license": "MIT",
        }
        assert validate_manifest_for_publish(raw) == []

    def test_missing_author(self):
        raw = {
            "manifest_version": 2, "name": "test", "version": "1.0.0",
            "type": "agent", "entry_point": "a:A",
            "repository": "https://github.com/test", "license": "MIT",
        }
        errors = validate_manifest_for_publish(raw)
        assert any("author" in e for e in errors)

    def test_missing_repository(self):
        raw = {
            "manifest_version": 2, "name": "test", "version": "1.0.0",
            "type": "agent", "entry_point": "a:A",
            "author": "user", "license": "MIT",
        }
        errors = validate_manifest_for_publish(raw)
        assert any("repository" in e for e in errors)

    def test_missing_license(self):
        raw = {
            "manifest_version": 2, "name": "test", "version": "1.0.0",
            "type": "agent", "entry_point": "a:A",
            "author": "user", "repository": "https://github.com/test",
        }
        errors = validate_manifest_for_publish(raw)
        assert any("license" in e for e in errors)

    def test_v1_manifest_rejected(self):
        raw = {"manifest_version": 1, "name": "test", "type": "agent", "entry_point": "a:A"}
        errors = validate_manifest_for_publish(raw)
        assert any("v2" in e.lower() or "version" in e for e in errors)

    def test_invalid_version_format(self):
        raw = {
            "manifest_version": 2, "name": "test", "version": "bad",
            "type": "agent", "entry_point": "a:A",
            "author": "user", "repository": "https://github.com/test", "license": "MIT",
        }
        errors = validate_manifest_for_publish(raw)
        assert any("version" in e.lower() for e in errors)


@pytest.fixture
def valid_plugin(tmp_path):
    d = tmp_path / "my_agent"
    d.mkdir()
    (d / "manifest.yaml").write_text(
        "manifest_version: 2\nname: my_agent\nversion: '1.0.0'\ntype: agent\n"
        "entry_point: agent:A\nauthor: u\nrepository: https://github.com/t\nlicense: MIT\n"
    )
    (d / "agent.py").write_text("class A: pass")
    return d


@pytest.fixture
def plugin_with_secrets(tmp_path):
    d = tmp_path / "bad"
    d.mkdir()
    (d / "manifest.yaml").write_text("name: bad\nversion: '1.0.0'\ntype: agent\nentry_point: a:A\n")
    (d / ".env").write_text("SECRET=abc")
    (d / "agent.py").write_text("class A: pass")
    return d


class TestValidatePluginDir:

    def test_valid_dir(self, valid_plugin):
        assert validate_plugin_dir(valid_plugin) == []

    def test_sensitive_files_detected(self, plugin_with_secrets):
        warnings = validate_plugin_dir(plugin_with_secrets)
        assert any(".env" in w for w in warnings)

    def test_no_manifest(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError, match="manifest.yaml"):
            validate_plugin_dir(empty)


class TestPackagePlugin:

    def test_creates_tar(self, valid_plugin, tmp_path):
        output = tmp_path / "out.tar.gz"
        sha = package_plugin(valid_plugin, output)
        assert output.exists()
        assert len(sha) == 64

    def test_excludes_sensitive_files(self, plugin_with_secrets, tmp_path):
        output = tmp_path / "out.tar.gz"
        package_plugin(plugin_with_secrets, output)
        with tarfile.open(output, "r:gz") as tf:
            assert not any(".env" in n for n in tf.getnames())
