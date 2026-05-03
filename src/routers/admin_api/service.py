import importlib
import os
import platform
from collections import Counter
from datetime import datetime

from fastapi import FastAPI, HTTPException, status
from nonebot import get_app, get_bots, get_loaded_plugins
from sqlalchemy.exc import IntegrityError

from src.agents.skills.registry import skill_registry
from src.plugins.autogpt.util import chat_session_manager
from src.plugins.helper import helper_menu
from utils.config import (
    autogpt_dir,
    cache_dir,
    data_dir,
    global_config,
    managers_dist_dir,
    project_root,
    task_dir,
    temp_dir,
)
from utils.helper.schema import HELPER_SCOPE_TITLES
from utils.llm.config import plugin_config
from utils.models import (
    User,
    Tasks,
    Classes,
    Teacher,
    Student,
    Curricula,
    ScheduledNotice,
    StudentLeave,
    AgentWorkflowRun,
    AgentWorkflowCheckpoint,
)

from .schemas import (
    AdminAgentOverviewResponse,
    AdminAgentSessionItem,
    AdminAuthStatusResponse,
    AdminBotItem,
    AdminBotListResponse,
    AdminCommandItem,
    AdminCommandListResponse,
    AdminDatabaseOverviewResponse,
    AdminDatabaseTableMetric,
    AdminMetric,
    AdminModelItem,
    AdminModelListResponse,
    AdminNameValue,
    AdminOverviewResponse,
    AdminPluginItem,
    AdminPluginListResponse,
    AdminSkillItem,
    AdminSkillListResponse,
    AdminSystemDirectory,
    AdminSystemStatusResponse,
    AdminUserCreateRequest,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserUpdateRequest,
)
from .security import get_admin_session_secret


def _counter_to_items(counter: Counter[str], title_map: dict[str, str] | None = None) -> list[AdminNameValue]:
    """把 Counter 统一转换成前端可直接消费的统计数组。"""

    items: list[AdminNameValue] = []
    for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        items.append(AdminNameValue(name=(title_map or {}).get(key, key), value=value))
    return items


def serialize_user(user: User) -> AdminUserItem:
    """将 ORM 用户对象转换成后台用户摘要。"""

    return AdminUserItem(
        id=user.id,
        nickname=user.nickname,
        username=user.username,
        email=user.email,
        phone=user.phone,
        gender=user.gender,
        is_admin=bool(user.is_admin),
        roles=[str(role) for role in user.roles],
        has_teacher_profile=user.teacher is not None,
        has_student_profile=user.student is not None,
        bind_count=len(user.binds),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def build_auth_status(admin_count: int) -> AdminAuthStatusResponse:
    """构建后台认证基础状态。"""

    session_secret_configured = bool(global_config.admin_session_secret or global_config.admin_api_token)
    if not session_secret_configured and os.getenv("ENVIRONMENT") in {"dev", "development", "test"}:
        session_secret_configured = True
    return AdminAuthStatusResponse(
        auth_mode="admin-user-password",
        admin_account_count=admin_count,
        session_secret_configured=session_secret_configured,
        frontend_dist_exists=managers_dist_dir.exists(),
        generated_at=datetime.now(),
    )


async def build_overview() -> AdminOverviewResponse:
    """构建后台首页总览数据。"""

    scope_counter: Counter[str] = Counter()
    for helper in helper_menu.helpers:
        for scope in helper.display_scopes:
            scope_counter[str(scope)] += 1

    workflow_runs = await AgentWorkflowRun.filter().all()
    workflow_status_counter = Counter(run.status for run in workflow_runs if run.status)

    metrics = [
        AdminMetric(
            key="commands",
            label="命令总数",
            value=len(helper_menu.helpers),
            description="当前已注册并进入帮助系统的命令数量。",
        ),
        AdminMetric(
            key="users",
            label="用户总数",
            value=await User.filter().count(),
            description="数据库中已创建的用户数量。",
        ),
        AdminMetric(
            key="admins",
            label="管理员账号",
            value=await User.filter(is_admin=True).count(),
            description="当前具备后台登录权限的管理员账号数量。",
        ),
        AdminMetric(
            key="classes",
            label="班级总数",
            value=await Classes.filter().count(),
            description="当前系统中已存在的班级数量。",
        ),
        AdminMetric(
            key="tasks",
            label="任务总数",
            value=await Tasks.filter().count(),
            description="作业/任务记录总量。",
        ),
        AdminMetric(
            key="active_sessions",
            label="活跃会话",
            value=len(chat_session_manager.sessions),
            description="内存中仍在保活的 AutoGPT 会话数量。",
        ),
        AdminMetric(
            key="pending_workflows",
            label="待确认工作流",
            value=await AgentWorkflowCheckpoint.filter(status="needs_confirm").count(),
            description="仍等待人工确认或补充信息的工作流数量。",
        ),
    ]

    return AdminOverviewResponse(
        generated_at=datetime.now(),
        metrics=metrics,
        command_scope_distribution=_counter_to_items(
            scope_counter, {str(key): value for key, value in HELPER_SCOPE_TITLES.items()}
        ),
        workflow_status_distribution=_counter_to_items(workflow_status_counter),
    )


def build_command_list() -> AdminCommandListResponse:
    """构建命令管理页数据。"""

    scope_counter: Counter[str] = Counter()
    items: list[AdminCommandItem] = []
    for helper in sorted(helper_menu.helpers, key=lambda item: item.command):
        display_scopes = sorted(str(scope) for scope in helper.display_scopes)
        for scope in display_scopes:
            scope_counter[scope] += 1
        items.append(
            AdminCommandItem(
                command=helper.command,
                description=helper.description,
                aliases=sorted(helper.aliases),
                scopes=display_scopes,
                roles=sorted(str(role) for role in helper.roles),
                exclude_roles=sorted(str(role) for role in helper.exclude_roles),
                tags=sorted(helper.tags),
                params=[str(param) for param in helper.params],
                ai_description=helper.ai_description,
            )
        )

    return AdminCommandListResponse(
        generated_at=datetime.now(),
        total=len(items),
        scope_distribution=_counter_to_items(scope_counter, {str(key): value for key, value in HELPER_SCOPE_TITLES.items()}),
        items=items,
    )


def _plugin_category(module_name: str) -> str:
    """根据模块路径归类插件来源。"""

    if module_name.startswith("src.managers."):
        return "manager"
    if module_name.startswith("src.plugins."):
        return "plugin"
    if module_name.startswith("src.others."):
        return "other"
    return "system"


def build_plugin_list() -> AdminPluginListResponse:
    """构建命令插件列表。"""

    items: list[AdminPluginItem] = []
    for plugin in sorted(get_loaded_plugins(), key=lambda item: getattr(item, "module_name", "") or str(item)):
        module_name = getattr(plugin, "module_name", "") or getattr(plugin, "name", "") or str(plugin)
        module = getattr(plugin, "module", None)
        if module is None and module_name:
            try:
                module = importlib.import_module(module_name)
            except Exception:  # noqa: BLE001
                module = None
        helpers = list(getattr(module, "__helpers__", [])) if module is not None else []
        items.append(
            AdminPluginItem(
                name=getattr(plugin, "name", None) or module_name.split(".")[-1],
                module_name=module_name,
                category=_plugin_category(module_name),
                helper_count=len(helpers),
                commands=sorted(helper.command for helper in helpers),
            )
        )

    return AdminPluginListResponse(generated_at=datetime.now(), total=len(items), items=items)


def build_skill_list() -> AdminSkillListResponse:
    """构建项目内 skill 列表。"""

    items = [
        AdminSkillItem(
            name=manifest.name,
            description=manifest.description,
            root=str(manifest.root),
            runtime_loaded=manifest.name in skill_registry._classes,
        )
        for manifest in skill_registry.manifests.values()
    ]
    items.sort(key=lambda item: item.name)
    return AdminSkillListResponse(generated_at=datetime.now(), total=len(items), items=items)


def build_model_list() -> AdminModelListResponse:
    """构建 LLM 配置列表。"""

    items = [
        AdminModelItem(
            name=config.name,
            model=config.model,
            url=config.url,
            priority=config.priority,
            tasks=list(config.tasks),
            multi_modal=config.multi_modal,
            supports_functools=config.supports_functools,
        )
        for config in plugin_config.llm_configs
    ]
    return AdminModelListResponse(generated_at=datetime.now(), total=len(items), items=items)


def build_bot_list() -> AdminBotListResponse:
    """构建当前运行 bot 列表。"""

    items: list[AdminBotItem] = []
    for _, bot in sorted(get_bots().items(), key=lambda item: item[0]):
        adapter = bot.adapter.get_name() if hasattr(bot.adapter, "get_name") else bot.adapter.__class__.__name__
        items.append(
            AdminBotItem(
                self_id=str(bot.self_id),
                adapter=adapter,
                type=bot.__class__.__name__,
                connected=True,
            )
        )
    return AdminBotListResponse(generated_at=datetime.now(), total=len(items), items=items)


async def build_agent_overview() -> AdminAgentOverviewResponse:
    """构建 Agent 运行态总览。"""

    workflow_runs = await AgentWorkflowRun.filter().all()
    approval_counter = Counter(run.approval_status for run in workflow_runs if run.approval_status)
    recent_sessions = sorted(chat_session_manager.sessions.values(), key=lambda item: item.update_time, reverse=True)[:10]

    session_items = [
        AdminAgentSessionItem(
            user_id=session.user_id,
            updated_at=datetime.fromtimestamp(session.update_time),
            lock=session.lock,
            helper_count=len(session.helpers.helpers),
            has_pending_workflow=session.pending_workflow is not None,
            last_trace_id=session.last_trace_id,
            last_intent=(
                session.last_turn_result.route.intent
                if session.last_turn_result is not None and session.last_turn_result.route is not None
                else None
            ),
            pending_goal=session.pending_workflow.goal if session.pending_workflow else None,
        )
        for session in recent_sessions
    ]

    metrics = [
        AdminMetric(
            key="memory_sessions",
            label="内存会话",
            value=len(chat_session_manager.sessions),
            description="当前进程内仍持有的聊天会话数量。",
        ),
        AdminMetric(
            key="locked_sessions",
            label="处理中会话",
            value=sum(1 for session in chat_session_manager.sessions.values() if session.lock),
            description="仍处于锁定、正在执行中的会话数量。",
        ),
        AdminMetric(
            key="pending_workflows",
            label="待确认会话",
            value=sum(1 for session in chat_session_manager.sessions.values() if session.pending_workflow is not None),
            description="会话内还挂着待确认工作流的数量。",
        ),
        AdminMetric(
            key="workflow_runs",
            label="工作流历史",
            value=len(workflow_runs),
            description="数据库中保存的工作流运行总数。",
        ),
        AdminMetric(
            key="workflow_checkpoints",
            label="工作流检查点",
            value=await AgentWorkflowCheckpoint.filter().count(),
            description="用于恢复待确认流程的最新检查点数量。",
        ),
    ]

    return AdminAgentOverviewResponse(
        generated_at=datetime.now(),
        metrics=metrics,
        approval_status_distribution=_counter_to_items(approval_counter),
        recent_sessions=session_items,
    )


async def build_database_overview() -> AdminDatabaseOverviewResponse:
    """构建数据库统计总览。"""

    tables = [
        AdminDatabaseTableMetric(key="users", label="用户", count=await User.filter().count()),
        AdminDatabaseTableMetric(key="teachers", label="教师", count=await Teacher.filter().count()),
        AdminDatabaseTableMetric(key="students", label="学生", count=await Student.filter().count()),
        AdminDatabaseTableMetric(key="classes", label="班级", count=await Classes.filter().count()),
        AdminDatabaseTableMetric(key="tasks", label="任务", count=await Tasks.filter().count()),
        AdminDatabaseTableMetric(key="curricula", label="课表项", count=await Curricula.filter().count()),
        AdminDatabaseTableMetric(key="notices", label="通知任务", count=await ScheduledNotice.filter().count()),
        AdminDatabaseTableMetric(key="leaves", label="请假记录", count=await StudentLeave.filter().count()),
        AdminDatabaseTableMetric(
            key="workflow_runs",
            label="工作流运行",
            count=await AgentWorkflowRun.filter().count(),
        ),
    ]
    return AdminDatabaseOverviewResponse(generated_at=datetime.now(), tables=tables)


def build_system_status() -> AdminSystemStatusResponse:
    """构建系统状态页数据。"""

    app = get_app()
    route_count = len(app.routes) if isinstance(app, FastAPI) else 0
    plugin_names = sorted(
        {
            getattr(plugin, "name", None) or getattr(plugin, "module_name", None) or str(plugin)
            for plugin in get_loaded_plugins()
        }
    )
    directories = [
        AdminSystemDirectory(key="project_root", label="项目根目录", path=str(project_root), exists=project_root.exists()),
        AdminSystemDirectory(key="data_dir", label="数据目录", path=str(data_dir), exists=data_dir.exists()),
        AdminSystemDirectory(key="cache_dir", label="缓存目录", path=str(cache_dir), exists=cache_dir.exists()),
        AdminSystemDirectory(key="task_dir", label="任务目录", path=str(task_dir), exists=task_dir.exists()),
        AdminSystemDirectory(key="temp_dir", label="临时目录", path=str(temp_dir), exists=temp_dir.exists()),
        AdminSystemDirectory(key="autogpt_dir", label="AutoGPT 数据目录", path=str(autogpt_dir), exists=autogpt_dir.exists()),
        AdminSystemDirectory(
            key="managers_dist_dir",
            label="后台前端构建目录",
            path=str(managers_dist_dir),
            exists=managers_dist_dir.exists(),
        ),
    ]
    return AdminSystemStatusResponse(
        generated_at=datetime.now(),
        app_name="ClassRobot Managers",
        environment=os.getenv("ENVIRONMENT", "development"),
        python_version=platform.python_version(),
        platform=platform.platform(),
        fastapi_enabled=isinstance(app, FastAPI),
        route_count=route_count,
        plugin_count=len(plugin_names),
        loaded_plugins=plugin_names,
        directories=directories,
    )


async def build_user_list() -> AdminUserListResponse:
    """构建后台用户管理列表。"""

    users = await User.select.order_by(User.id.desc())
    items = [serialize_user(user) for user in users]
    return AdminUserListResponse(generated_at=datetime.now(), total=len(items), items=items)


def _normalize_optional_text(value: str | None) -> str | None:
    """将空字符串归一化为 None。"""

    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


async def create_user(payload: AdminUserCreateRequest) -> AdminUserItem:
    """创建后台用户。"""

    try:
        user = await User(
            nickname=payload.nickname.strip(),
            username=payload.username.strip(),
            password=payload.password,
            email=_normalize_optional_text(payload.email),
            phone=_normalize_optional_text(payload.phone),
            gender=_normalize_optional_text(payload.gender),
            is_admin=payload.is_admin,
        ).create()
    except IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名、邮箱或手机号已存在。") from error
    return serialize_user(await User.filter(id=user.id).first() or user)


async def update_user(target_user: User, payload: AdminUserUpdateRequest, current_admin: User) -> AdminUserItem:
    """更新后台用户。"""

    updates = payload.dict(exclude_unset=True)
    if not updates:
        return serialize_user(target_user)

    if current_admin.id == target_user.id and updates.get("is_admin") is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能撤销自己当前的管理员身份。")

    if updates.get("is_admin") is False and target_user.is_admin:
        admin_count = await User.filter(is_admin=True).count()
        if admin_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="系统至少需要保留一个管理员账号。")

    for field in ("nickname", "username"):
        if field in updates and isinstance(updates[field], str):
            updates[field] = updates[field].strip()
    for field in ("email", "phone", "gender"):
        if field in updates:
            updates[field] = _normalize_optional_text(updates[field])

    try:
        user = await target_user.update(**updates)
    except IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名、邮箱或手机号已存在。") from error
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")
    return serialize_user(user)


async def delete_user(target_user: User, current_admin: User) -> None:
    """删除后台用户。"""

    if current_admin.id == target_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除当前已登录的管理员账号。")
    if target_user.is_admin:
        admin_count = await User.filter(is_admin=True).count()
        if admin_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="系统至少需要保留一个管理员账号。")
    await target_user.delete()


async def get_user_or_404(user_id: int) -> User:
    """根据用户 ID 获取后台用户，不存在则抛出 404。"""

    user = await User.filter(id=user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在。")
    return user


def ensure_session_secret_ready() -> None:
    """确保后台登录态密钥可用。"""

    get_admin_session_secret()
