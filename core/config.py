"""配置加载 - .env + config.yaml 双层配置"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class I18nConfig(BaseModel):
    default_locale: str = "zh"
    supported_locales: list[str] = ["en", "zh"]


class LLMConfig(BaseModel):
    default_model: str = "volcengine/doubao-seed-2-0-pro-260215"
    intent_router_model: str | None = None  # 意图路由模型，默认使用 default_model
    fallback_model: str | None = None
    max_tokens_per_request: int = 4096
    temperature: float = 0.7


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "json"


class PluginsEnabled(BaseModel):
    agents: list[str] = ["meal_agent"]
    memory: list[str] = ["short_term_memory"]
    search: list[str] = []
    extensions: list[str] = ["device_gateway"]


class SkillHubConfig(BaseModel):
    registry_url: str = "https://raw.githubusercontent.com/lary-hub/registry/main/index.json"
    cache_ttl_seconds: int = 3600
    contrib_dir: str = "contrib"
    backup_dir: str = "contrib/.backup"
    max_download_size_mb: int = 100


class AppConfig(BaseModel):
    """从 config.yaml 加载的应用配置"""
    server: ServerConfig = ServerConfig()
    i18n: I18nConfig = I18nConfig()
    llm: LLMConfig = LLMConfig()
    logging: LoggingConfig = LoggingConfig()
    plugins: PluginsEnabled = PluginsEnabled()
    plugin_config: dict[str, dict[str, Any]] = {}
    skillhub: SkillHubConfig = SkillHubConfig()


class EnvConfig(BaseSettings):
    """从 .env 加载的环境变量"""
    # 数据库
    database_url: str = "postgresql+asyncpg://lifeagent:lifeagent@postgres:5432/lifeagent"
    redis_url: str = "redis://redis:6379/0"

    # LLM (LiteLLM 自动读取环境变量)
    volcengine_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # 可选服务
    mem0_api_key: str = ""
    memobase_url: str = ""
    milvus_host: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """加载 config.yaml，文件不存在时使用默认值"""
    path = Path(config_path)
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return AppConfig(**raw)
    return AppConfig()


def load_env() -> EnvConfig:
    """加载 .env 环境变量"""
    return EnvConfig()
