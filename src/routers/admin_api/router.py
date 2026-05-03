from fastapi import APIRouter, Depends, Response, status

from utils.models import User

from .deps import require_admin_user
from .schemas import (
    AdminAgentOverviewResponse,
    AdminAuthStatusResponse,
    AdminBotListResponse,
    AdminCommandListResponse,
    AdminDatabaseOverviewResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminModelListResponse,
    AdminOverviewResponse,
    AdminPluginListResponse,
    AdminSkillListResponse,
    AdminSystemStatusResponse,
    AdminUserCreateRequest,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserUpdateRequest,
)
from .security import authenticate_admin_user, create_admin_access_token
from .service import (
    build_agent_overview,
    build_auth_status,
    build_bot_list,
    build_command_list,
    build_database_overview,
    build_model_list,
    build_overview,
    build_plugin_list,
    build_skill_list,
    build_system_status,
    build_user_list,
    create_user,
    delete_user,
    ensure_session_secret_ready,
    get_user_or_404,
    serialize_user,
    update_user,
)


admin_router = APIRouter(prefix="/admin", tags=["Admin API"])


@admin_router.get("/auth/status", response_model=AdminAuthStatusResponse)
async def get_admin_auth_status() -> AdminAuthStatusResponse:
    """获取后台登录模式与基础状态。"""

    admin_count = await User.filter(is_admin=True).count()
    return build_auth_status(admin_count)


@admin_router.post("/auth/login", response_model=AdminLoginResponse)
async def admin_login(payload: AdminLoginRequest) -> AdminLoginResponse:
    """管理员账户登录并签发后台访问令牌。"""

    ensure_session_secret_ready()
    user = await authenticate_admin_user(payload.username.strip(), payload.password)
    access_token, expires_at = create_admin_access_token(user)
    return AdminLoginResponse(access_token=access_token, expires_at=expires_at, user=serialize_user(user))


@admin_router.get("/auth/me", response_model=AdminUserItem)
async def get_admin_me(current_admin: User = Depends(require_admin_user)) -> AdminUserItem:
    """获取当前已登录管理员信息。"""

    return serialize_user(current_admin)


@admin_router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(_: User = Depends(require_admin_user)) -> AdminOverviewResponse:
    """获取后台仪表盘总览。"""

    return await build_overview()


@admin_router.get("/users", response_model=AdminUserListResponse)
async def get_admin_users(_: User = Depends(require_admin_user)) -> AdminUserListResponse:
    """获取后台用户列表。"""

    return await build_user_list()


@admin_router.post("/users", response_model=AdminUserItem, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    payload: AdminUserCreateRequest,
    _: User = Depends(require_admin_user),
) -> AdminUserItem:
    """创建后台用户。"""

    return await create_user(payload)


@admin_router.patch("/users/{user_id}", response_model=AdminUserItem)
async def update_admin_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    current_admin: User = Depends(require_admin_user),
) -> AdminUserItem:
    """更新后台用户。"""

    target_user = await get_user_or_404(user_id)
    return await update_user(target_user, payload, current_admin)


@admin_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_user(
    user_id: int,
    current_admin: User = Depends(require_admin_user),
) -> Response:
    """删除后台用户。"""

    target_user = await get_user_or_404(user_id)
    await delete_user(target_user, current_admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("/commands", response_model=AdminCommandListResponse)
async def get_admin_commands(_: User = Depends(require_admin_user)) -> AdminCommandListResponse:
    """获取命令治理页数据。"""

    return build_command_list()


@admin_router.get("/plugins", response_model=AdminPluginListResponse)
async def get_admin_plugins(_: User = Depends(require_admin_user)) -> AdminPluginListResponse:
    """获取已加载命令插件列表。"""

    return build_plugin_list()


@admin_router.get("/skills", response_model=AdminSkillListResponse)
async def get_admin_skills(_: User = Depends(require_admin_user)) -> AdminSkillListResponse:
    """获取项目内 skill 列表。"""

    return build_skill_list()


@admin_router.get("/models", response_model=AdminModelListResponse)
async def get_admin_models(_: User = Depends(require_admin_user)) -> AdminModelListResponse:
    """获取模型配置列表。"""

    return build_model_list()


@admin_router.get("/bots", response_model=AdminBotListResponse)
async def get_admin_bots(_: User = Depends(require_admin_user)) -> AdminBotListResponse:
    """获取当前运行中的 bot 列表。"""

    return build_bot_list()


@admin_router.get("/agents", response_model=AdminAgentOverviewResponse)
async def get_admin_agents(_: User = Depends(require_admin_user)) -> AdminAgentOverviewResponse:
    """获取 Agent 运行态数据。"""

    return await build_agent_overview()


@admin_router.get("/database", response_model=AdminDatabaseOverviewResponse)
async def get_admin_database(_: User = Depends(require_admin_user)) -> AdminDatabaseOverviewResponse:
    """获取数据库核心统计。"""

    return await build_database_overview()


@admin_router.get("/system", response_model=AdminSystemStatusResponse)
async def get_admin_system(_: User = Depends(require_admin_user)) -> AdminSystemStatusResponse:
    """获取系统状态与环境信息。"""

    return build_system_status()
