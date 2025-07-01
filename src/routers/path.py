from nonebot import get_app
from fastapi import FastAPI, APIRouter

app = get_app()

if isinstance(app, FastAPI):
    router = APIRouter(prefix="/api/v1", tags=["API"])
    from src.plugins.helper import helper_menu

    @router.get("/commands")
    async def get_commands():
        """获取所有命令"""
        return helper_menu.dict(include={"helpers"})

    app.include_router(router)
