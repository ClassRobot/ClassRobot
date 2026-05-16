from __future__ import annotations

from fastapi import APIRouter

from .api import manager_api_routers

router = APIRouter(prefix="/api/v1/manager")

for manager_api_router in manager_api_routers:
    router.include_router(manager_api_router, tags=["Manager"])
