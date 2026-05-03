from fastapi import APIRouter

from src.plugins.helper import helper_menu


public_router = APIRouter(tags=["Public API"])


@public_router.get("/commands")
async def get_commands():
    """获取当前系统注册的命令帮助信息。"""

    return helper_menu.dict(include={"helpers"})
