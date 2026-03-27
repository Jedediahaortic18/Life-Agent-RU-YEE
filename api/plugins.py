"""Plugin Management API"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("")
async def list_plugins(plugin_type: str | None = None):
    """列出已加载插件"""
    from main import registry

    plugins = registry.list_plugins(plugin_type=plugin_type)
    return {
        "success": True,
        "data": [p.model_dump() for p in plugins],
    }


@router.post("/{name}/load")
async def load_plugin(name: str, plugin_dir: str = ""):
    """热加载插件"""
    from main import registry

    if not plugin_dir:
        plugin_dir = f"contrib/agents/{name}"

    try:
        registry.load_plugin(plugin_dir)
        return {"success": True, "message": f"Plugin '{name}' loaded"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{name}/unload")
async def unload_plugin(name: str):
    """卸载插件"""
    from main import registry

    try:
        registry.unload_plugin(name)
        return {"success": True, "message": f"Plugin '{name}' unloaded"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{name}/reload")
async def reload_plugin(name: str):
    """重载插件"""
    from main import registry

    try:
        registry.reload_plugin(name)
        return {"success": True, "message": f"Plugin '{name}' reloaded"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
