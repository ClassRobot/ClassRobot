"""ClassRobot HTTP 接口挂载入口。"""

from nonebot import get_app
from fastapi import FastAPI, APIRouter

app = get_app()

if isinstance(app, FastAPI):
    router = APIRouter(prefix="/api/v1", tags=["API"])
    from src.plugins.application.active.helper import helper_menu
    from src.interfaces.http.managers import router as managers_router

    @router.get("/commands")
    async def get_commands():
        """获取所有命令"""
        return helper_menu.dict(include={"helpers"})

    app.include_router(router)
    app.include_router(managers_router)
