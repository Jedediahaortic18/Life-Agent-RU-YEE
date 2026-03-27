"""API 路由聚合"""
from fastapi import APIRouter

from api.chat import router as chat_router
from api.plugins import router as plugins_router
from api.health import router as health_router
from api.skillhub import router as skillhub_router

router = APIRouter()
router.include_router(chat_router, prefix="/chat", tags=["Chat"])
router.include_router(plugins_router, prefix="/plugins", tags=["Plugins"])
router.include_router(health_router, tags=["Health"])
router.include_router(skillhub_router, prefix="/skillhub", tags=["SkillHub"])
