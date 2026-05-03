from nonebot import get_app
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles

from utils.config import managers_dist_dir

from src.routers.public_api import public_router
from src.routers.admin_api import admin_router


app = get_app()

if isinstance(app, FastAPI):
    api_router = APIRouter(prefix="/api/v1", tags=["API"])
    api_router.include_router(public_router)
    api_router.include_router(admin_router)
    app.include_router(api_router)

    if managers_dist_dir.exists():
        app.mount("/admin", StaticFiles(directory=str(managers_dist_dir), html=True), name="managers-admin")
