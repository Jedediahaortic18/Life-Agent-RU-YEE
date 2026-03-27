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

        # 8. 热加载
        try:
            self._hot_load_plugin(str(target_dir))
        except Exception as e:
            logger.warning(f"Hot-load failed for {name}: {e}")

        # 9. 更新 config.yaml
        self._update_config_enabled(name, plugin_info.type, action="add")

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

    def _hot_load_plugin(self, plugin_dir: str, config: dict | None = None, context_bus: Any = None) -> None:
        """安装后热加载插件"""
        if self._plugin_registry:
            self._plugin_registry.load_plugin(plugin_dir, config, context_bus)

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
