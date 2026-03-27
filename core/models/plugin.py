"""Plugin 相关模型"""
from __future__ import annotations

from pydantic import BaseModel


class PluginManifest(BaseModel):
    """插件 manifest.yaml 对应模型（v1 + v2 兼容）"""
    manifest_version: int = 1
    name: str
    version: str = "0.1.0"
    type: str  # agent | memory | search | extension
    description: str = ""
    entry_point: str  # 模块:类名
    dependencies: PluginDependencies = None
    tools: list[str] = []
    config_schema: dict = {}

    # === v2 新增字段（全部可选，v1 使用默认值）===
    author: str = ""
    repository: str = ""
    license: str = ""
    tags: list[str] = []
    min_framework_version: str = ""
    icon: str = ""
    screenshots: list[str] = []
    allowed_agents: list[str] = []
    changelog: str = ""

    class Config:
        extra = "allow"


class PluginDependencies(BaseModel):
    """插件依赖声明"""
    plugins: list[str] = []
    python: list[str] = []


class PluginState(BaseModel):
    """插件运行时状态"""
    name: str
    type: str
    version: str
    status: str = "loaded"  # loaded | failed | unloaded
    capabilities: list[str] = []
    error: str | None = None
