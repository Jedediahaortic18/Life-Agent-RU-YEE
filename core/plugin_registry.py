"""PluginRegistry - 插件注册表"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from core.interfaces.agent import BaseStreamAgent
from core.interfaces.memory import BaseMemory
from core.interfaces.tool import BaseTool
from core.interfaces.extension import BaseExtension
from core.models.plugin import PluginManifest, PluginDependencies, PluginState


# 插件类型与基类的映射
_TYPE_BASE_MAP = {
    "agent": BaseStreamAgent,
    "memory": BaseMemory,
    "search": None,  # search 插件无统一基类
    "extension": BaseExtension,
}


class PluginRegistry:
    """插件注册表，管理所有插件的生命周期"""

    def __init__(self) -> None:
        self._manifests: dict[str, PluginManifest] = {}
        self._instances: dict[str, Any] = {}
        self._tools: dict[str, list[BaseTool]] = {}  # agent_name -> tools
        self._states: dict[str, PluginState] = {}
        self._comm_manager: Any = None

    # ── 启动时加载 ──────────────────────────────────────────

    def discover(self, *scan_dirs: str | Path) -> list[PluginManifest]:
        """扫描目录发现所有 manifest.yaml"""
        manifests = []
        for scan_dir in scan_dirs:
            scan_path = Path(scan_dir)
            if not scan_path.exists():
                continue
            for manifest_file in scan_path.rglob("manifest.yaml"):
                try:
                    raw = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
                    deps = raw.get("dependencies") or {}
                    raw["dependencies"] = PluginDependencies(**deps) if deps else PluginDependencies()
                    manifest = PluginManifest(**raw)
                    manifest._source_dir = str(manifest_file.parent)
                    manifests.append(manifest)
                except Exception as e:
                    logger.warning(f"Failed to parse {manifest_file}: {e}")
        return manifests

    def load_enabled(
        self,
        manifests: list[PluginManifest],
        enabled: dict[str, list[str]],
        plugin_config: dict[str, dict] | None = None,
        context_bus: Any = None,
    ) -> None:
        """
        加载启用的插件。

        enabled: {"agents": ["meal_agent"], "memory": ["short_term_memory"], ...}
        plugin_config: 每个插件的配置覆盖
        """
        plugin_config = plugin_config or {}

        # 收集所有启用的插件名
        enabled_names: set[str] = set()
        for names in enabled.values():
            enabled_names.update(names)

        # 建立 name -> manifest 映射
        manifest_map: dict[str, PluginManifest] = {}
        for m in manifests:
            manifest_map[m.name] = m

        # 拓扑排序
        sorted_names = self._topological_sort(enabled_names, manifest_map)

        # 依次加载
        for name in sorted_names:
            if name not in manifest_map:
                logger.warning(f"Plugin '{name}' not found in discovered manifests, skipped")
                continue
            manifest = manifest_map[name]
            config = plugin_config.get(name, {})
            try:
                self._load_single(manifest, config, context_bus)
            except Exception as e:
                logger.warning(f"Plugin '{name}' failed to load: {e}")
                self._states[name] = PluginState(
                    name=name,
                    type=manifest.type,
                    version=manifest.version,
                    status="failed",
                    error=str(e),
                )

    @staticmethod
    def _scoped_import(source_dir: str, module_name: str) -> Any:
        """在指定插件目录作用域内导入模块，避免跨插件 sys.path 污染"""
        # 确保项目根在 path 中（支持 from core.xxx import）
        project_root = str(Path(source_dir).parents[2])
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        # 临时将插件目录置于 sys.path 最前
        sys.path.insert(0, source_dir)
        try:
            # 清除可能被其他插件缓存的同名模块（如 tools, tools.xxx, agent, memory）
            # 只清理插件本地模块，不清理全局包（core, fastapi 等）
            top_pkg = module_name.split(".")[0]
            global_pkgs = {"core", "fastapi", "pydantic", "sqlalchemy", "jinja2", "litellm", "loguru", "yaml"}
            if top_pkg not in global_pkgs:
                stale = [k for k in sys.modules if k == top_pkg or k.startswith(top_pkg + ".")]
                for k in stale:
                    del sys.modules[k]
            return importlib.import_module(module_name)
        finally:
            sys.path.remove(source_dir)

    def _load_single(
        self,
        manifest: PluginManifest,
        config: dict,
        context_bus: Any = None,
    ) -> None:
        """加载单个插件"""
        source_dir = getattr(manifest, "_source_dir", None)
        if not source_dir:
            raise ValueError(f"Plugin '{manifest.name}' has no source directory")

        # 解析 entry_point (module:ClassName)
        module_name, class_name = manifest.entry_point.split(":")
        module = self._scoped_import(source_dir, module_name)
        cls = getattr(module, class_name)

        # 实例化
        if manifest.type == "agent":
            instance = cls(context_bus=context_bus, config=config)
        elif manifest.type == "memory":
            instance = cls(config=config)
        elif manifest.type == "extension":
            instance = cls()
        else:
            instance = cls(config=config) if "config" in cls.__init__.__code__.co_varnames else cls()

        self._instances[manifest.name] = instance
        self._manifests[manifest.name] = manifest

        # 加载插件自身声明的 Tools（任何类型插件都可提供）
        if manifest.tools:
            tools = []
            for tool_ref in manifest.tools:
                tool_module_name, tool_class_name = tool_ref.split(":")
                tool_module = self._scoped_import(source_dir, tool_module_name)
                tool_cls = getattr(tool_module, tool_class_name)
                tool_instance = tool_cls()
                # 注入 registry 引用（供需要访问其他插件的工具使用）
                if hasattr(tool_instance, "set_registry"):
                    tool_instance.set_registry(self)
                tools.append(tool_instance)
            self._tools[manifest.name] = tools

        # Agent 类型：合并依赖插件的 tools、注入系统工具
        if manifest.type == "agent":
            agent_tools = list(self._tools.get(manifest.name, []))
            # 收集依赖插件提供的 tools
            if manifest.dependencies:
                for dep_name in manifest.dependencies.plugins:
                    dep_tools = self._tools.get(dep_name, [])
                    agent_tools.extend(dep_tools)
            # 注入系统工具（agent_call, agent_list）
            agent_tools = self._inject_system_tools(manifest.name, agent_tools)
            self._tools[manifest.name] = agent_tools
            if hasattr(instance, "set_tools"):
                instance.set_tools(agent_tools)

        # 记录状态
        capabilities = []
        if manifest.type == "agent" and hasattr(instance, "capabilities"):
            capabilities = instance.capabilities

        self._states[manifest.name] = PluginState(
            name=manifest.name,
            type=manifest.type,
            version=manifest.version,
            status="loaded",
            capabilities=capabilities,
        )

        logger.info(f"Plugin loaded: {manifest.name} ({manifest.type})")

    # ── 运行时查询 ──────────────────────────────────────────

    def get_agent(self, name: str) -> BaseStreamAgent | None:
        inst = self._instances.get(name)
        return inst if isinstance(inst, BaseStreamAgent) else None

    def get_memory(self, name: str) -> BaseMemory | None:
        inst = self._instances.get(name)
        return inst if isinstance(inst, BaseMemory) else None

    def get_extension(self, name: str) -> BaseExtension | None:
        inst = self._instances.get(name)
        return inst if isinstance(inst, BaseExtension) else None

    def get_tools(self, agent_name: str) -> list[BaseTool]:
        return self._tools.get(agent_name, [])

    def get_instance(self, name: str) -> Any:
        return self._instances.get(name)

    def get_manifest(self, name: str) -> PluginManifest | None:
        """获取插件 manifest"""
        return self._manifests.get(name)

    def set_comm_manager(self, comm_manager: Any) -> None:
        """设置 Agent 通信管理器（在 main.py 初始化后调用）"""
        self._comm_manager = comm_manager

    def _inject_system_tools(self, agent_name: str, existing_tools: list) -> list:
        """为 Agent 注入系统级工具（agent_call、agent_list）"""
        if not self._comm_manager:
            return existing_tools

        from core.agent_comm import AgentListTool, AgentCallTool

        system_tools = [
            AgentListTool(self._comm_manager),
            AgentCallTool(self._comm_manager, source_agent=agent_name),
        ]
        return list(existing_tools) + system_tools

    def list_plugins(self, plugin_type: str | None = None) -> list[PluginState]:
        states = list(self._states.values())
        if plugin_type:
            states = [s for s in states if s.type == plugin_type]
        return states

    # ── 热插拔 ──────────────────────────────────────────────

    def load_plugin(self, plugin_dir: str, config: dict | None = None, context_bus: Any = None) -> None:
        """运行时加载新插件（仅 agent/memory/search）"""
        manifest_path = Path(plugin_dir) / "manifest.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest.yaml not found in {plugin_dir}")

        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        deps = raw.get("dependencies") or {}
        raw["dependencies"] = PluginDependencies(**deps) if deps else PluginDependencies()
        manifest = PluginManifest(**raw)
        manifest._source_dir = str(plugin_dir)

        if manifest.type == "extension":
            raise ValueError("Extension plugins cannot be hot-loaded. Restart the server.")

        # 检查依赖
        for dep in (manifest.dependencies.plugins if manifest.dependencies else []):
            if dep not in self._instances:
                raise ValueError(f"Dependency '{dep}' not loaded")

        self._load_single(manifest, config or {}, context_bus)

    def unload_plugin(self, name: str) -> None:
        """运行时卸载插件"""
        if name not in self._instances:
            raise ValueError(f"Plugin '{name}' not loaded")

        manifest = self._manifests.get(name)
        if manifest and manifest.type == "extension":
            raise ValueError("Extension plugins cannot be hot-unloaded. Restart the server.")

        # 检查反向依赖
        for other_name, other_manifest in self._manifests.items():
            if other_name == name:
                continue
            deps = other_manifest.dependencies.plugins if other_manifest.dependencies else []
            if name in deps:
                raise ValueError(f"Cannot unload '{name}': '{other_name}' depends on it")

        del self._instances[name]
        del self._manifests[name]
        self._tools.pop(name, None)
        self._states[name] = PluginState(
            name=name, type=manifest.type if manifest else "unknown",
            version=manifest.version if manifest else "0.0.0",
            status="unloaded",
        )
        logger.info(f"Plugin unloaded: {name}")

    def reload_plugin(self, name: str, config: dict | None = None, context_bus: Any = None) -> None:
        """重载插件"""
        manifest = self._manifests.get(name)
        if not manifest:
            raise ValueError(f"Plugin '{name}' not found")
        source_dir = getattr(manifest, "_source_dir", None)
        self.unload_plugin(name)
        if source_dir:
            self.load_plugin(source_dir, config, context_bus)

    # ── 拓扑排序 ──────────────────────────────────────────

    @staticmethod
    def _topological_sort(
        names: set[str],
        manifest_map: dict[str, PluginManifest],
    ) -> list[str]:
        """拓扑排序，检测循环依赖"""
        # 构建邻接表
        graph: dict[str, list[str]] = {n: [] for n in names}
        for name in names:
            manifest = manifest_map.get(name)
            if not manifest or not manifest.dependencies:
                continue
            for dep in manifest.dependencies.plugins:
                if dep in names:
                    graph[name].append(dep)

        # Kahn 算法
        in_degree: dict[str, int] = {n: 0 for n in names}
        for name, deps in graph.items():
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0)

        for name, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    pass  # in_degree 已初始化
            # 实际计算入度：被依赖的节点入度 +1
        # 重新计算
        in_degree = {n: 0 for n in names}
        reverse_graph: dict[str, list[str]] = {n: [] for n in names}
        for name, deps in graph.items():
            for dep in deps:
                reverse_graph.setdefault(dep, []).append(name)

        # name 依赖 dep，所以 dep 要先加载 → dep 的出边指向 name
        # 入度 = 被多少个节点依赖（即多少节点要在它之后）× 错了
        # 正确：name 依赖 dep → name 入度 +1（name 要等 dep 先加载）
        in_degree = {n: len(graph[n]) for n in names}

        queue = [n for n in names if in_degree[n] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for dependent in reverse_graph.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(names):
            loaded = set(result)
            cycle_nodes = names - loaded
            raise ValueError(f"Circular dependency detected: {' → '.join(cycle_nodes)}")

        return result
