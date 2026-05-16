from __future__ import annotations

from .agents import router as agents_router
from .auth import router as auth_router
from .chat_history import router as chat_history_router
from .databases import router as databases_router
from .files import router as files_router
from .groups import router as groups_router
from .logs import router as logs_router
from .models import router as models_router
from .nonebot import router as nonebot_router
from .operations import router as operations_router
from .overview import router as overview_router
from .prompts import router as prompts_router
from .settings import router as settings_router
from .skills import router as skills_router
from .users import router as users_router

manager_api_routers = (
    auth_router,
    overview_router,
    settings_router,
    users_router,
    groups_router,
    skills_router,
    prompts_router,
    models_router,
    agents_router,
    nonebot_router,
    files_router,
    chat_history_router,
    databases_router,
    logs_router,
    operations_router,
)
