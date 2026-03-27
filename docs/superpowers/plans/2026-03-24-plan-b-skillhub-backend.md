# Plan B: SkillHub 后端 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 SkillHub 技能市场后端：远程索引拉取（带缓存）、SHA256 校验安装、版本升级/备份、卸载、搜索、发布（manifest v2 严格校验 + 打包）。

**Architecture:** 新建 `core/skillhub.py` 封装核心逻辑（索引管理、下载安装、卸载、发布），`api/skillhub.py` 提供 REST API。安装目录为 `contrib/{type}/{name}/`，与内置 `plugins/` 隔离。远程索引通过 GitHub raw URL 拉取，本地缓存 1 小时。

**Tech Stack:** Python 3.11+, httpx (async HTTP), hashlib (SHA256), shutil/tarfile, PyYAML, FastAPI

**Spec:** `docs/superpowers/specs/2026-03-24-skillhub-agent-comm-design.md` 第二节

**前置依赖:** Plan A Task 1（PluginManifest v2 模型）必须先完成。

---

### Task 1: 基础设施 — config.yaml + .gitignore + SkillHubConfig

**Files:**
- Modify: `config.yaml`
- Modify: `core/config.py`
- Modify: `.gitignore`

- [ ] **Step 1: 在 config.yaml 中添加 skillhub 配置**

在 `config.yaml` 末尾追加：

```yaml
skillhub:
  registry_url: "https://raw.githubusercontent.com/lary-hub/registry/main/index.json"
  cache_ttl_seconds: 3600  # 索引缓存 1 小时
  contrib_dir: "contrib"
  backup_dir: "contrib/.backup"
  max_download_size_mb: 100  # 单个插件最大下载大小
```

- [ ] **Step 2: 在 AppConfig 中添加 SkillHubConfig 模型**

在 `core/config.py` 中新增：

```python
class SkillHubConfig(BaseModel):
    registry_url: str = "https://raw.githubusercontent.com/lary-hub/registry/main/index.json"
    cache_ttl_seconds: int = 3600
    contrib_dir: str = "contrib"
    backup_dir: str = "contrib/.backup"
    max_download_size_mb: int = 100
```

在 `AppConfig` 中新增字段：

```python
class AppConfig(BaseModel):
    ...
    skillhub: SkillHubConfig = SkillHubConfig()
```

- [ ] **Step 3: 在 .gitignore 中添加 contrib/**

在 `.gitignore` 末尾追加：

```
# 社区安装的插件
contrib/
```

注意：不创建 `.gitkeep`，`contrib/` 子目录由 `SkillHubManager.__init__` 在运行时自动创建。

- [ ] **Step 4: 提交**

```bash
git add config.yaml core/config.py .gitignore
git commit -m "feat: 添加 skillhub 配置项和 contrib gitignore"
```

---

### Task 2: 索引管理器 — 远程拉取 + 本地缓存 + 搜索

**Files:**
- Create: `core/skillhub.py`
- Test: `tests/core/test_skillhub_index.py` (Create)

- [ ] **Step 1: 编写索引拉取、缓存和搜索测试**

```python
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

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_INDEX
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

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_INDEX
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

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(side_effect=httpx.ConnectError("connection failed"))
        mock_client_cls = MagicMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        import httpx
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_skillhub_index.py -v`
Expected: FAIL — `core.skillhub` 不存在

- [ ] **Step 3: 实现 SkillHubManager 索引管理和搜索**

```python
# core/skillhub.py
"""SkillHub - 技能市场核心逻辑"""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

import httpx
import yaml
from loguru import logger
from pydantic import BaseModel

if TYPE_CHECKING:
    from core.plugin_registry import PluginRegistry


class RegistryPlugin(BaseModel):
    """远程索引中的插件条目"""
    name: str
    version: str
    type: str
    description: str = ""
    author: str = ""
    tags: list[str] = []
    min_framework_version: str = ""
    download_url: str
    manifest_url: str = ""
    sha256: str
    verified: bool = False
    created_at: str = ""
    updated_at: str = ""


class RegistryIndex(BaseModel):
    """远程索引"""
    version: int = 1
    updated_at: str = ""
    plugins: list[RegistryPlugin] = []


# 类型到目录名的映射
_TYPE_DIR_MAP = {
    "agent": "agents",
    "memory": "memory",
    "extension": "extensions",
    "search": "search",
}

# type 到 config.yaml key 的映射
_TYPE_CONFIG_KEY_MAP = {
    "agent": "agents",
    "memory": "memory",
    "extension": "extensions",
    "search": "search",
}


class SkillHubManager:
    """技能市场管理器"""

    def __init__(
        self,
        registry_url: str,
        cache_ttl: int,
        contrib_dir: str,
        backup_dir: str,
        registry: "PluginRegistry | None" = None,
        max_download_size_mb: int = 100,
    ) -> None:
        self._registry_url = registry_url
        self._cache_ttl = cache_ttl
        self._contrib_dir = Path(contrib_dir)
        self._backup_dir = Path(backup_dir)
        self._plugin_registry = registry
        self._max_download_bytes = max_download_size_mb * 1024 * 1024
        self._config_path: Path = Path("config.yaml")

        # 索引缓存
        self._index_cache: RegistryIndex | None = None
        self._cache_time: float = 0

        # 运行时创建 contrib 目录
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """确保 contrib 子目录存在"""
        for type_dir in _TYPE_DIR_MAP.values():
            (self._contrib_dir / type_dir).mkdir(parents=True, exist_ok=True)
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    # ── 索引管理 ────────────────────────────────────────

    async def fetch_index(self, force: bool = False) -> RegistryIndex:
        """拉取远程索引，带本地缓存"""
        now = time.time()
        if (
            not force
            and self._index_cache is not None
            and (now - self._cache_time) < self._cache_ttl
        ):
            return self._index_cache

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(self._registry_url)
            resp.raise_for_status()
            data = resp.json()

        self._index_cache = RegistryIndex(**data)
        self._cache_time = time.time()
        logger.info(f"Fetched registry index: {len(self._index_cache.plugins)} plugins")
        return self._index_cache

    def _find_plugin_in_index(self, name: str, version: str | None = None) -> RegistryPlugin | None:
        """在缓存索引中查找插件"""
        if not self._index_cache:
            return None
        for p in self._index_cache.plugins:
            if p.name == name:
                if version and p.version != version:
                    continue
                return p
        return None

    # ── 搜索 ───────────────────────────────────────────

    async def search(
        self,
        q: str = "",
        tags: list[str] | None = None,
        plugin_type: str = "",
    ) -> list[RegistryPlugin]:
        """搜索远程索引中的插件"""
        if not self._index_cache:
            try:
                await self.fetch_index()
            except Exception as e:
                logger.warning(f"Failed to fetch index for search: {e}")
                return []

        results = list(self._index_cache.plugins)

        if q:
            q_lower = q.lower()
            results = [
                p for p in results
                if q_lower in p.name.lower()
                or q_lower in p.description.lower()
                or any(q_lower in tag.lower() for tag in p.tags)
            ]

        if tags:
            tag_set = {t.lower() for t in tags}
            results = [
                p for p in results
                if tag_set & {t.lower() for t in p.tags}
            ]

        if plugin_type:
            results = [p for p in results if p.type == plugin_type]

        return results
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_skillhub_index.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/skillhub.py tests/core/test_skillhub_index.py
git commit -m "feat: SkillHubManager 索引拉取、缓存和搜索"
```

---

### Task 3: 安装逻辑 — 下载、SHA256 校验、版本处理

**Files:**
- Modify: `core/skillhub.py`
- Test: `tests/core/test_skillhub_install.py` (Create)

- [ ] **Step 1: 编写安装流程测试**

```python
# tests/core/test_skillhub_install.py
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_skillhub_install.py -v`
Expected: FAIL — `install` 方法不存在

- [ ] **Step 3: 实现安装逻辑**

在 `core/skillhub.py` 的 `SkillHubManager` 类中追加：

```python
    # ── 安装 ───────────────────────────────────────────

    async def install(
        self,
        name: str,
        version: str | None = None,
    ) -> dict[str, str]:
        """安装远程插件"""
        # 1. 从索引查找
        plugin_info = self._find_plugin_in_index(name, version)
        if not plugin_info:
            raise ValueError(f"Plugin '{name}' not found in registry index")

        type_dir = _TYPE_DIR_MAP.get(plugin_info.type, plugin_info.type)
        target_dir = self._contrib_dir / type_dir / name

        # 2. 检查已安装版本
        is_upgrade = False
        if target_dir.exists():
            existing_version = self._get_installed_version(target_dir)
            if existing_version == plugin_info.version:
                return {"status": "already_latest", "version": plugin_info.version}
            # 备份旧版
            is_upgrade = True
            self._backup_plugin(name, existing_version, target_dir)

        # 3. 下载
        tar_bytes = await self._download(plugin_info.download_url)

        # 4. 大小限制
        if len(tar_bytes) > self._max_download_bytes:
            raise ValueError(
                f"下载大小 {len(tar_bytes)} 字节超过限制 {self._max_download_bytes} 字节"
            )

        # 5. SHA256 校验
        actual_hash = hashlib.sha256(tar_bytes).hexdigest()
        if actual_hash != plugin_info.sha256:
            raise ValueError(
                f"SHA256 校验失败：期望 {plugin_info.sha256}，实际 {actual_hash}"
            )

        # 6. 解压到目标目录
        try:
            self._extract_tar(tar_bytes, target_dir)
        except Exception:
            # 清理部分解压的内容
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            raise

        # 7. 验证 manifest.yaml 存在
        manifest_path = target_dir / "manifest.yaml"
        if not manifest_path.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
            raise ValueError("解压后未找到 manifest.yaml")

        status = "upgraded" if is_upgrade else "installed"
        logger.info(f"Plugin {status}: {name} v{plugin_info.version}")
        return {"status": status, "version": plugin_info.version}

    def _get_installed_version(self, plugin_dir: Path) -> str:
        """读取已安装插件的版本"""
        manifest_path = plugin_dir / "manifest.yaml"
        if not manifest_path.exists():
            return ""
        try:
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            return raw.get("version", "")
        except Exception:
            return ""

    def _backup_plugin(self, name: str, version: str, source_dir: Path) -> None:
        """备份旧版插件"""
        backup_target = self._backup_dir / f"{name}-{version}"
        if backup_target.exists():
            shutil.rmtree(backup_target)
        shutil.copytree(source_dir, backup_target)
        shutil.rmtree(source_dir)
        logger.info(f"Backed up {name} v{version} to {backup_target}")

    async def _download(self, url: str) -> bytes:
        """下载文件"""
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    @staticmethod
    def _extract_tar(tar_bytes: bytes, target_dir: Path) -> None:
        """解压 tar.gz 到目标目录，自动剥离顶层目录"""
        target_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tf:
            members = tf.getmembers()
            if not members:
                raise ValueError("tar.gz 文件为空")

            # 检测顶层目录前缀
            prefix = ""
            first = members[0].name
            if "/" in first:
                prefix = first.split("/")[0] + "/"

            for member in members:
                # 计算剥离后的路径（不修改原始 member）
                relative_name = member.name
                if prefix and relative_name.startswith(prefix):
                    relative_name = relative_name[len(prefix):]
                if not relative_name or relative_name == ".":
                    continue

                # 安全检查：防止路径遍历
                dest = (target_dir / relative_name).resolve()
                if not str(dest).startswith(str(target_dir.resolve())):
                    raise ValueError(f"不安全的路径: {member.name}")

                # 手动提取（不使用 tf.extract 避免权限和可变性问题）
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    source = tf.extractfile(member)
                    if source:
                        dest.write_bytes(source.read())
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_skillhub_install.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: 提交**

```bash
git add core/skillhub.py tests/core/test_skillhub_install.py
git commit -m "feat: SkillHub 安装逻辑，含 SHA256 校验、大小限制和路径安全检查"
```

---

### Task 4: 卸载逻辑

**Files:**
- Modify: `core/skillhub.py`
- Test: `tests/core/test_skillhub_uninstall.py` (Create)

- [ ] **Step 1: 编写卸载测试**

```python
# tests/core/test_skillhub_uninstall.py
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_skillhub_uninstall.py -v`
Expected: FAIL — `uninstall` 方法不存在

- [ ] **Step 3: 实现卸载和列表方法**

在 `core/skillhub.py` 的 `SkillHubManager` 中追加：

```python
    # ── 卸载 ───────────────────────────────────────────

    async def uninstall(self, name: str) -> dict[str, str]:
        """卸载社区安装的插件"""
        plugin_dir = self._find_installed_dir(name)
        if not plugin_dir:
            raise ValueError(f"Plugin '{name}' not installed in contrib")

        # 读取 manifest 信息（卸载前需要 type）
        raw = yaml.safe_load((plugin_dir / "manifest.yaml").read_text(encoding="utf-8"))
        plugin_type = raw.get("type", "")

        # 调用 registry 卸载（检查反向依赖）
        if self._plugin_registry:
            self._plugin_registry.unload_plugin(name)

        # 更新 config.yaml
        self._update_config_enabled(name, plugin_type, action="remove")

        # 删除目录
        shutil.rmtree(plugin_dir)
        logger.info(f"Plugin uninstalled: {name}")
        return {"status": "uninstalled", "name": name}

    def _find_installed_dir(self, name: str) -> Path | None:
        """在 contrib 中查找已安装插件的目录"""
        for type_dir in _TYPE_DIR_MAP.values():
            candidate = self._contrib_dir / type_dir / name
            if candidate.exists() and (candidate / "manifest.yaml").exists():
                return candidate
        return None

    def list_installed(self) -> list[dict[str, str]]:
        """列出 contrib 中已安装的插件"""
        result = []
        for type_dir in _TYPE_DIR_MAP.values():
            type_path = self._contrib_dir / type_dir
            if not type_path.exists():
                continue
            for plugin_dir in type_path.iterdir():
                if not plugin_dir.is_dir():
                    continue
                manifest_path = plugin_dir / "manifest.yaml"
                if manifest_path.exists():
                    try:
                        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                        result.append({
                            "name": raw.get("name", plugin_dir.name),
                            "version": raw.get("version", ""),
                            "type": raw.get("type", ""),
                            "description": raw.get("description", ""),
                            "source": "contrib",
                        })
                    except Exception:
                        pass
        return result

    # ── 配置更新 ─────────────────────────────────────────

    def _update_config_enabled(self, name: str, plugin_type: str, action: str = "add") -> None:
        """更新 config.yaml 的 enabled 列表"""
        if not self._config_path.exists():
            return

        config = yaml.safe_load(self._config_path.read_text(encoding="utf-8")) or {}
        plugins = config.setdefault("plugins", {})

        key = _TYPE_CONFIG_KEY_MAP.get(plugin_type, plugin_type)
        plugin_list = plugins.setdefault(key, [])

        if action == "add":
            if name not in plugin_list:
                plugin_list.append(name)
        elif action == "remove":
            if name in plugin_list:
                plugin_list.remove(name)

        self._config_path.write_text(
            yaml.dump(config, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_skillhub_uninstall.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: 提交**

```bash
git add core/skillhub.py tests/core/test_skillhub_uninstall.py
git commit -m "feat: SkillHub 卸载逻辑、已安装列表和 config.yaml 更新"
```

---

### Task 5: 安装后热加载 + config.yaml 联动

**Files:**
- Modify: `core/skillhub.py` (在 install 方法末尾添加热加载和 config 更新)
- Test: `tests/core/test_skillhub_hotload.py` (Create)

- [ ] **Step 1: 编写热加载测试**

```python
# tests/core/test_skillhub_hotload.py
"""SkillHub 安装后热加载和配置联动测试"""
import hashlib
import io
import tarfile
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    from unittest.mock import AsyncMock
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_skillhub_hotload.py -v`
Expected: FAIL — install 方法不包含热加载逻辑

- [ ] **Step 3: 在 install 方法末尾添加热加载和 config 更新**

在 `install` 方法的 `return` 之前添加：

```python
        # 8. 热加载
        try:
            self._hot_load_plugin(str(target_dir))
        except Exception as e:
            logger.warning(f"Hot-load failed for {name}: {e}")

        # 9. 更新 config.yaml
        self._update_config_enabled(name, plugin_info.type, action="add")
```

新增 `_hot_load_plugin` 方法：

```python
    def _hot_load_plugin(self, plugin_dir: str, config: dict | None = None, context_bus: Any = None) -> None:
        """安装后热加载插件"""
        if self._plugin_registry:
            self._plugin_registry.load_plugin(plugin_dir, config, context_bus)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_skillhub_hotload.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add core/skillhub.py tests/core/test_skillhub_hotload.py
git commit -m "feat: 安装后热加载插件并更新 config.yaml"
```

---

### Task 6: 发布校验器 + 打包

**Files:**
- Modify: `core/skillhub.py`
- Test: `tests/core/test_skillhub_publish.py` (Create)

- [ ] **Step 1: 编写发布校验和打包测试**

```python
# tests/core/test_skillhub_publish.py
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/core/test_skillhub_publish.py -v`
Expected: FAIL

- [ ] **Step 3: 实现校验和打包函数**

在 `core/skillhub.py` 中新增顶层函数：

```python
# 敏感文件模式
_SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "credentials.json",
                    "secrets.yaml", "id_rsa", "id_ed25519", ".npmrc"}
_SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx"}


def validate_manifest_for_publish(raw: dict) -> list[str]:
    """严格校验 manifest 用于发布，返回错误列表"""
    errors = []

    if raw.get("manifest_version", 1) < 2:
        errors.append("发布要求 manifest_version >= 2")

    for field in ("name", "version", "type", "entry_point"):
        if not raw.get(field):
            errors.append(f"缺少必填字段: {field}")

    for field in ("author", "repository", "license"):
        if not raw.get(field):
            errors.append(f"发布要求 v2 必填字段: {field}")

    version = raw.get("version", "")
    if version and not re.match(r"^\d+\.\d+\.\d+", version):
        errors.append(f"version 格式不正确，应为语义化版本（如 1.0.0）: {version}")

    valid_types = {"agent", "memory", "extension", "search"}
    if raw.get("type") and raw["type"] not in valid_types:
        errors.append(f"type 必须是 {valid_types} 之一，当前: {raw['type']}")

    return errors


def validate_plugin_dir(plugin_dir: Path) -> list[str]:
    """校验插件目录，返回警告列表"""
    plugin_dir = Path(plugin_dir)
    if not (plugin_dir / "manifest.yaml").exists():
        raise ValueError(f"manifest.yaml not found in {plugin_dir}")

    warnings = []
    for f in plugin_dir.rglob("*"):
        if f.is_dir():
            continue
        if f.name in _SENSITIVE_NAMES:
            warnings.append(f"检测到敏感文件: {f.relative_to(plugin_dir)}")
        if f.suffix in _SENSITIVE_EXTENSIONS:
            warnings.append(f"检测到敏感文件: {f.relative_to(plugin_dir)}")
    return warnings


def package_plugin(plugin_dir: Path, output_path: Path) -> str:
    """打包插件为 tar.gz，返回 SHA256。排除敏感文件和 __pycache__"""
    plugin_dir = Path(plugin_dir)
    output_path = Path(output_path)

    with tarfile.open(output_path, "w:gz") as tf:
        for f in plugin_dir.rglob("*"):
            if f.is_dir():
                continue
            if f.name in _SENSITIVE_NAMES or f.suffix in _SENSITIVE_EXTENSIONS:
                continue
            if "__pycache__" in str(f):
                continue
            arcname = f"{plugin_dir.name}/{f.relative_to(plugin_dir)}"
            tf.add(f, arcname=arcname)

    return hashlib.sha256(output_path.read_bytes()).hexdigest()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/core/test_skillhub_publish.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add core/skillhub.py tests/core/test_skillhub_publish.py
git commit -m "feat: manifest v2 发布校验器和安全打包"
```

---

### Task 7: SkillHub REST API

**Files:**
- Create: `api/skillhub.py`
- Modify: `api/__init__.py`
- Modify: `main.py`
- Test: `tests/api/test_skillhub_api.py` (Create)

- [ ] **Step 1: 编写 API 路由测试**

```python
# tests/api/test_skillhub_api.py
"""SkillHub API 路由测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def client():
    """使用 FastAPI 的 dependency_overrides 注入 mock"""
    from main import app
    from fastapi.testclient import TestClient

    mock_hub = MagicMock()
    mock_hub.fetch_index = AsyncMock(return_value=MagicMock(
        model_dump=lambda: {"version": 1, "updated_at": "", "plugins": []}
    ))
    mock_hub.search = AsyncMock(return_value=[])
    mock_hub.list_installed = MagicMock(return_value=[])
    mock_hub.install = AsyncMock(return_value={"status": "installed", "version": "1.0.0"})
    mock_hub.uninstall = AsyncMock(return_value={"status": "uninstalled", "name": "test"})

    # 使用 FastAPI 的 DI override
    from api.skillhub import get_skillhub_manager
    app.dependency_overrides[get_skillhub_manager] = lambda: mock_hub

    # mock registry for installed endpoint
    with patch("api.skillhub._get_registry") as mock_reg:
        mock_reg.return_value.list_plugins.return_value = []
        yield TestClient(app), mock_hub

    app.dependency_overrides.clear()


class TestSkillHubAPI:

    def test_get_registry(self, client):
        c, _ = client
        resp = c.get("/api/skillhub/registry")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_get_installed(self, client):
        c, _ = client
        resp = c.get("/api/skillhub/installed")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_search(self, client):
        c, _ = client
        resp = c.get("/api/skillhub/search?q=健身")
        assert resp.status_code == 200

    def test_install(self, client):
        c, _ = client
        resp = c.post("/api/skillhub/install", json={"name": "fitness_agent"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "installed"

    def test_uninstall(self, client):
        c, _ = client
        resp = c.delete("/api/skillhub/uninstall/fitness_agent")
        assert resp.status_code == 200

    def test_install_error(self, client):
        c, mock_hub = client
        mock_hub.install = AsyncMock(side_effect=ValueError("not found"))
        resp = c.post("/api/skillhub/install", json={"name": "bad"})
        assert resp.status_code == 400
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/api/test_skillhub_api.py -v`
Expected: FAIL — `api.skillhub` 不存在

- [ ] **Step 3: 实现 SkillHub API 路由**

```python
# api/skillhub.py
"""SkillHub API - 技能市场接口"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter()


class InstallRequest(BaseModel):
    name: str
    version: str | None = None


def get_skillhub_manager():
    """获取 SkillHubManager 实例（可被测试 override）"""
    from main import skillhub_manager
    if not skillhub_manager:
        raise HTTPException(status_code=503, detail="SkillHub not initialized")
    return skillhub_manager


def _get_registry():
    """获取 PluginRegistry"""
    from main import registry
    return registry


@router.get("/registry")
async def get_registry(hub=Depends(get_skillhub_manager)):
    """拉取远程索引"""
    try:
        index = await hub.fetch_index()
        return {"success": True, "data": index.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch registry: {e}")


@router.get("/installed")
async def get_installed(hub=Depends(get_skillhub_manager)):
    """已安装插件列表（内置 + 社区）"""
    reg = _get_registry()

    # 内置插件
    all_plugins = reg.list_plugins()
    builtin = [
        {
            "name": p.name, "version": p.version, "type": p.type,
            "status": p.status, "capabilities": p.capabilities,
            "source": "builtin",
        }
        for p in all_plugins
    ]

    # 社区安装插件
    contrib = hub.list_installed()
    return {"success": True, "data": builtin + contrib}


@router.get("/search")
async def search_plugins(
    q: str = "",
    tags: str = "",
    type: str = "",
    hub=Depends(get_skillhub_manager),
):
    """搜索远程索引"""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    results = await hub.search(q=q, tags=tag_list, plugin_type=type)
    return {"success": True, "data": [r.model_dump() for r in results]}


@router.post("/install")
async def install_plugin(req: InstallRequest, hub=Depends(get_skillhub_manager)):
    """安装插件"""
    try:
        result = await hub.install(req.name, req.version)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"安装失败: {e}")


@router.delete("/uninstall/{name}")
async def uninstall_plugin(name: str, hub=Depends(get_skillhub_manager)):
    """卸载插件"""
    try:
        result = await hub.uninstall(name)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"卸载失败: {e}")


@router.post("/publish")
async def publish_plugin():
    """发布插件（PR 生成，第二阶段实现）"""
    raise HTTPException(status_code=501, detail="发布功能即将推出")
```

- [ ] **Step 4: 在 api/__init__.py 中注册路由**

在 `api/__init__.py` 中添加 import 和路由注册：

```python
from api.skillhub import router as skillhub_router
```

```python
router.include_router(skillhub_router, prefix="/skillhub", tags=["SkillHub"])
```

- [ ] **Step 5: 在 main.py 中初始化 SkillHubManager**

1. 在全局状态区域新增：
```python
skillhub_manager = None  # SkillHubManager
```

2. 在 `lifespan` 函数中，`init_orchestrator(app_config)` 之后添加：
```python
# 初始化 SkillHub
global skillhub_manager
from core.skillhub import SkillHubManager
skillhub_manager = SkillHubManager(
    registry_url=app_config.skillhub.registry_url,
    cache_ttl=app_config.skillhub.cache_ttl_seconds,
    contrib_dir=app_config.skillhub.contrib_dir,
    backup_dir=app_config.skillhub.backup_dir,
    registry=registry,
    max_download_size_mb=app_config.skillhub.max_download_size_mb,
)
logger.info("SkillHub initialized")
```

- [ ] **Step 6: 运行测试验证通过**

Run: `python -m pytest tests/api/test_skillhub_api.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: 提交**

```bash
git add api/skillhub.py api/__init__.py main.py tests/api/test_skillhub_api.py
git commit -m "feat: SkillHub REST API（索引、搜索、安装、卸载）+ main.py 集成"
```

---

### Task 8: 端到端集成验证

**Files:**
- Create: `tests/integration/test_skillhub_e2e.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/integration/test_skillhub_e2e.py
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
```

- [ ] **Step 2: 运行全部测试**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 全部 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/integration/test_skillhub_e2e.py
git commit -m "test: SkillHub 端到端集成测试（搜索→安装→卸载完整流程）"
```

---

## 可能出现的问题

1. **httpx 版本**：确认 `requirements.txt` 包含 `httpx>=0.27.0`（项目已有）。
2. **config.yaml 并发写入**：多个安装请求同时修改 `config.yaml`。当前串行无问题，后续并发需加文件锁。
3. **GitHub tar.gz 顶层目录名**：格式为 `{repo}-{tag}/`，`_extract_tar` 前缀剥离需匹配实际格式。
4. **hot_load 失败**：安装成功但热加载失败时，插件文件存在但未加载。当前仅 log warning，用户需重启。
5. **Pydantic 版本**：`model_dump()` 需要 Pydantic v2（项目已用 v2）。
6. **min_framework_version**：当前安装不检查版本兼容性，后续可添加。

## 建议的测试用例

| 场景 | 预期结果 |
|------|----------|
| 远程索引拉取成功 | 返回 RegistryIndex，缓存生效 |
| 索引缓存未过期 | 不发起网络请求 |
| 索引缓存已过期 | 重新拉取 |
| 搜索匹配 name/description/tags | 返回结果 |
| SHA256 校验失败 | 拒绝安装 |
| 下载超过大小限制 | 拒绝安装 |
| tar.gz 含路径遍历 | 拒绝解压 |
| 安装新插件 | 解压 + 热加载 + config 更新 |
| 安装已有相同版本 | 返回 already_latest |
| 版本升级 | 备份旧版 + 安装新版 |
| 卸载社区插件 | 删除 + unload + config 移除 |
| 卸载不存在的插件 | 报错 |
| 发布校验 v1 manifest | 返回错误 |
| 打包排除 .env | tar 中无 .env |
| API install 400 | ValueError 返回 400 |
