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
    """拉取远程索引，不可用时返回空列表"""
    try:
        index = await hub.fetch_index()
        return {"success": True, "data": index.model_dump()}
    except Exception:
        return {
            "success": True,
            "data": {"version": 0, "updated_at": "", "plugins": []},
        }


@router.get("/installed")
async def get_installed(hub=Depends(get_skillhub_manager)):
    """已安装插件列表（内置 + 社区）"""
    reg = _get_registry()

    # 内置插件
    all_plugins = reg.list_plugins()
    builtin = []
    for p in all_plugins:
        manifest = reg.get_manifest(p.name)
        tools = reg.get_tools(p.name)
        tool_names = [t.name for t in tools] if tools else []
        builtin.append({
            "name": p.name, "version": p.version, "type": p.type,
            "status": p.status, "capabilities": p.capabilities,
            "description": manifest.description if manifest else "",
            "tools": tool_names,
            "source": "builtin",
        })

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
    try:
        results = await hub.search(q=q, tags=tag_list, plugin_type=type)
        return {"success": True, "data": [r.model_dump() for r in results]}
    except Exception:
        return {"success": True, "data": []}


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
