"""Life-Agent-RU-YEE - FastAPI 应用入口"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 sys.path
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from core.config import load_config, load_env, AppConfig, EnvConfig
from core.context_bus import ContextBus
from core.intent_router import IntentRouter
from core.orchestrator import Orchestrator
from core.plugin_registry import PluginRegistry
from core.task_decomposer import TaskDecomposer


# ── 全局状态 ─────────────────────────────────────────────
registry = PluginRegistry()
orchestrator: Orchestrator | None = None
skillhub_manager = None  # SkillHubManager
app_config: AppConfig | None = None
env_config: EnvConfig | None = None


def setup_logging(config: AppConfig) -> None:
    """配置 Loguru 日志"""
    logger.remove()
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "{message}"
    )
    if config.logging.format == "json":
        logger.add(sys.stderr, level=config.logging.level, serialize=True)
    else:
        logger.add(sys.stderr, level=config.logging.level, format=log_format)


def init_plugins(config: AppConfig) -> None:
    """发现并加载所有启用的插件"""
    global registry

    manifests = registry.discover("plugins", "contrib")
    logger.info(f"Discovered {len(manifests)} plugin(s)")

    enabled = {
        "agents": config.plugins.agents,
        "memory": config.plugins.memory,
        "search": config.plugins.search,
        "extensions": config.plugins.extensions,
    }

    context_bus = ContextBus()
    registry.load_enabled(
        manifests=manifests,
        enabled=enabled,
        plugin_config=config.plugin_config,
        context_bus=context_bus,
    )

    loaded = registry.list_plugins()
    for p in loaded:
        logger.info(f"  [{p.status}] {p.name} ({p.type}) v{p.version}")


def init_orchestrator(config: AppConfig) -> None:
    """初始化编排引擎"""
    global orchestrator

    router_model = config.llm.intent_router_model or config.llm.default_model
    intent_router = IntentRouter(registry, model=router_model)
    task_decomposer = TaskDecomposer(registry)
    memory = registry.get_memory("short_term_memory")
    orchestrator = Orchestrator(registry, intent_router, task_decomposer, memory=memory)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期"""
    global app_config, env_config

    # 加载配置
    app_config = load_config()
    env_config = load_env()

    # 设置日志
    setup_logging(app_config)
    logger.info("Starting Life-Agent-RU-YEE...")

    # 设置 LiteLLM 环境变量
    import os
    if env_config.volcengine_api_key:
        os.environ["VOLCENGINE_API_KEY"] = env_config.volcengine_api_key
    if env_config.openai_api_key:
        os.environ["OPENAI_API_KEY"] = env_config.openai_api_key
    if env_config.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = env_config.anthropic_api_key

    # 初始化数据库
    from core.database import init_db
    await init_db()
    logger.info("Database initialized")

    # 初始化 Agent 间通信（必须在 init_plugins 之前，以便注入系统工具）
    from core.agent_comm import AgentCommManager
    comm_manager = AgentCommManager(registry=registry)
    registry.set_comm_manager(comm_manager)

    # 加载插件
    init_plugins(app_config)

    # 加载 Extensions（注册路由）
    for ext_state in registry.list_plugins(plugin_type="extension"):
        if ext_state.status == "loaded":
            ext = registry.get_extension(ext_state.name)
            if ext:
                await ext.on_load(app, registry)
                logger.info(f"Extension '{ext_state.name}' routes registered")

    # 初始化编排引擎
    init_orchestrator(app_config)

    # 连接通信管理器到编排引擎
    orchestrator.set_comm_manager(comm_manager)

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

    logger.info("Life-Agent-RU-YEE started successfully")
    yield

    # 清理
    logger.info("Shutting down...")


# ── FastAPI App ──────────────────────────────────────────
app = FastAPI(
    title="Life-Agent-RU-YEE",
    description="AI 驱动的生活管理 Agent 框架，可插拔架构",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── API 路由 ─────────────────────────────────────────────
from api import router as api_router  # noqa: E402

app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
