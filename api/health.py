"""健康检查端点"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "Life-Agent-RU-YEE", "version": "0.1.0"}
