from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from . import audit, agents, databases, groups, llm_models, logs, nonebot_runtime, operations, prompts, settings_store, skills
from .schemas import (
    LoginRequest,
    TokenResponse,
    AdminPatchRequest,
    AutomationScriptCreateRequest,
    AutomationScriptUpdateRequest,
    DatabaseRowUpdateRequest,
    StatusCheckRequest,
    PromptUpdateRequest,
    SettingsPatchRequest,
    ModelSettingsRequest,
    TerminalExecuteRequest,
)
from .security import SESSION_TTL_SECONDS, manager_auth, manager_auth_token, token_store
from .status import check_system_metrics, get_status

router = APIRouter(prefix="/api/v1/manager", tags=["Manager"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    """使用启动令牌登录本地管理后台。

    Args:
        payload: 登录请求体，包含启动令牌。

    Returns:
        TokenResponse: 新创建的 bearer 会话令牌。
    """
    session_token, _ = token_store.login(payload.token)
    audit.log_event("auth", "login", "completed")
    return TokenResponse(access_token=session_token, expires_in=SESSION_TTL_SECONDS)


@router.get("/auth/me")
async def auth_me(session=Depends(manager_auth)):
    """返回当前管理端会话信息。"""
    return {
        "authenticated": True,
        "role": "local_manager",
        "issued_at": session.issued_at,
        "expires_at": session.expires_at,
    }


@router.post("/auth/logout")
async def logout(session_token: str = Depends(manager_auth_token)):
    """注销当前管理端会话。

    Args:
        session_token: 当前 bearer token。

    Returns:
        dict[str, bool]: 注销结果。
    """
    token_store.logout(session_token)
    audit.log_event("auth", "logout", "completed")
    return {"logged_out": True}


@router.get("/overview")
async def overview(_=Depends(manager_auth)):
    """返回总览页所需的聚合数据。"""
    status_payload = await get_status()
    runs = await agents.list_runs(page=1, page_size=5)
    checkpoints = await agents.list_checkpoints(status="needs_confirm", page=1, page_size=5)
    skill_items = skills.list_skills()["items"]
    prompt_items = prompts.list_prompts()["items"]
    model_items = llm_models.list_models()["items"]
    alerts = []
    for key, value in status_payload.items():
        if isinstance(value, dict) and value.get("status") in {"warning", "error", "not_configured"}:
            alerts.append({"source": key, "level": value.get("status"), "message": value.get("message", "")})
    return {
        "runtime": status_payload.get("runtime", {}),
        "assets": {
            "skills": len(skill_items),
            "prompts": len(prompt_items),
            "models": len(model_items),
            "agent_runs": runs["total"],
            "pending_workflows": checkpoints["total"],
        },
        "alerts": alerts,
        "recent_runs": runs["items"],
    }


@router.get("/status")
async def status_overview(_=Depends(manager_auth)):
    """返回完整系统状态。"""
    return await get_status()


@router.post("/status/check")
async def status_check(payload: StatusCheckRequest, _=Depends(manager_auth)):
    """按指定分组执行系统状态检查。

    Args:
        payload: 指定需要检查的状态分组。

    Returns:
        dict[str, Any]: 所选分组的状态结果。
    """
    return await get_status(payload.targets)


@router.get("/system/metrics")
async def system_metrics(_=Depends(manager_auth)):
    """返回系统资源监控指标。"""
    return check_system_metrics()


@router.get("/settings")
async def get_settings(_=Depends(manager_auth)):
    """读取设置页完整配置。"""
    return settings_store.get_settings()


@router.patch("/settings")
async def update_settings(payload: SettingsPatchRequest, session=Depends(manager_auth)):
    """更新本地后台可编辑配置。

    Args:
        payload: 按分组提交的设置更新请求。
        session: 当前管理端会话。

    Returns:
        dict[str, Any]: 设置保存结果。

    Raises:
        HTTPException: 当字段校验失败或缺少依赖时抛出。
    """
    try:
        result = settings_store.update_settings(payload.dict(exclude_unset=True))
        audit.log_event(
            "settings",
            "update_settings",
            "completed",
            detail={"changed_keys": result.get("changed_keys", [])},
            session=session,
        )
        return result
    except ValueError as error:
        audit.log_event("settings", "update_settings", "failed", detail={"error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        audit.log_event("settings", "update_settings", "failed", detail={"error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.post("/settings/security/rotate-token")
async def rotate_token(session=Depends(manager_auth)):
    """轮换后台启动令牌并使现有会话失效。"""
    token_store.rotate_startup_token(log_token=True)
    audit.log_event("settings", "rotate_token", "completed", session=session)
    return {
        "rotated": True,
        "new_token_preview": token_store.preview_startup_token(),
        "message": "New manager token has been printed to the application log.",
    }


@router.get("/users")
async def list_users(
    q: str | None = None,
    role: str | None = None,
    is_admin: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """列出用户中心表格数据。"""
    from .users import list_users as _list_users

    return await _list_users(q=q, role=role, is_admin=is_admin, page=page, page_size=page_size)


@router.get("/users/{user_id}")
async def get_user(user_id: int, _=Depends(manager_auth)):
    """读取单个用户详情。

    Args:
        user_id: 用户 ID。

    Returns:
        dict[str, Any]: 用户详情数据。

    Raises:
        HTTPException: 当用户不存在时抛出 404。
    """
    from .users import get_user_detail

    try:
        return await get_user_detail(user_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error


@router.patch("/users/{user_id}/admin")
async def patch_user_admin(user_id: int, payload: AdminPatchRequest, session=Depends(manager_auth)):
    """修改用户管理员状态。"""
    from .users import set_user_admin

    try:
        result = await set_user_admin(user_id, payload.is_admin)
        audit.log_event(
            "users",
            "patch_user_admin",
            "completed",
            detail={"user_id": user_id, "is_admin": payload.is_admin},
            session=session,
        )
        return result
    except KeyError as error:
        audit.log_event(
            "users",
            "patch_user_admin",
            "failed",
            detail={"user_id": user_id, "error": "User not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, session=Depends(manager_auth)):
    """删除用户账号及其可安全清理的关联数据。"""
    from .users import UserMutationError, delete_user_account

    try:
        result = await delete_user_account(user_id)
        audit.log_event(
            "users",
            "delete_user",
            "completed",
            detail={"user_id": user_id},
            session=session,
        )
        return result
    except KeyError as error:
        audit.log_event(
            "users",
            "delete_user",
            "failed",
            detail={"user_id": user_id, "error": "User not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error
    except UserMutationError as error:
        payload = error.to_payload()
        audit.log_event(
            "users",
            "delete_user",
            "failed",
            detail={"user_id": user_id, "error": payload},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=payload) from error


@router.delete("/users/{user_id}/binds/{bind_id}")
async def delete_user_bind(user_id: int, bind_id: int, session=Depends(manager_auth)):
    """删除用户的一条平台绑定。"""
    from .users import delete_user_bind as _delete_user_bind

    try:
        result = await _delete_user_bind(user_id, bind_id)
        audit.log_event(
            "users",
            "delete_user_bind",
            "completed",
            detail={"user_id": user_id, "bind_id": bind_id},
            session=session,
        )
        return result
    except KeyError as error:
        audit.log_event(
            "users",
            "delete_user_bind",
            "failed",
            detail={"user_id": user_id, "bind_id": bind_id, "error": "Bind not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bind not found") from error


@router.get("/groups")
async def list_group_items(
    q: str | None = None,
    platform_id: str | None = None,
    join_method: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """列出群组中心表格数据。"""
    return await groups.list_groups(
        q=q,
        platform_id=platform_id,
        join_method=join_method,
        page=page,
        page_size=page_size,
    )


@router.get("/groups/{group_id}")
async def get_group_item(group_id: int, _=Depends(manager_auth)):
    """读取单个群组详情。"""
    try:
        return await groups.get_group_detail(group_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found") from error


@router.get("/skills")
async def list_skill_items(_=Depends(manager_auth)):
    """列出 Skill 清单。"""
    return skills.list_skills()


@router.get("/skills/{name}")
async def get_skill(name: str, _=Depends(manager_auth)):
    """读取单个 Skill 详情。"""
    try:
        return skills.get_skill(name)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found") from error


@router.post("/skills/reload")
async def reload_skills(session=Depends(manager_auth)):
    """重新加载 Skill。"""
    result = skills.reload_skills()
    audit.log_event(
        "skills",
        "reload_skills",
        "completed",
        detail={"loaded_classes": result.get("loaded_classes", [])},
        session=session,
    )
    return result


@router.get("/prompts")
async def list_prompt_items(_=Depends(manager_auth)):
    """列出 Prompt 清单。"""
    return prompts.list_prompts()


@router.get("/prompts/{name}")
async def get_prompt(name: str, _=Depends(manager_auth)):
    """读取单个 Prompt 内容。"""
    try:
        return prompts.get_prompt(name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.put("/prompts/{name}")
async def update_prompt(name: str, payload: PromptUpdateRequest, session=Depends(manager_auth)):
    """更新单个 Prompt 模板。"""
    try:
        result = prompts.update_prompt(name, payload.content)
        audit.log_event(
            "prompts",
            "update_prompt",
            "completed" if result.get("saved") else "failed",
            detail={"name": name, "saved": result.get("saved"), "valid": result.get("valid")},
            session=session,
        )
        return result
    except FileNotFoundError as error:
        audit.log_event(
            "prompts", "update_prompt", "failed", detail={"name": name, "error": str(error)}, session=session
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        audit.log_event(
            "prompts", "update_prompt", "failed", detail={"name": name, "error": str(error)}, session=session
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/prompts/{name}/validate")
async def validate_prompt(name: str, _=Depends(manager_auth)):
    """校验单个 Prompt 模板。"""
    try:
        return prompts.validate_prompt(name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/models")
async def list_model_items(_=Depends(manager_auth)):
    """列出模型配置清单。"""
    return llm_models.list_models()


@router.put("/models")
async def save_model_items(payload: ModelSettingsRequest, session=Depends(manager_auth)):
    """保存模型配置。"""
    try:
        result = llm_models.save_models(payload.dict(exclude_unset=True))
        audit.log_event(
            "models",
            "save_models",
            "completed",
            detail={"model_count": len(result.get("items", [])) if isinstance(result.get("items"), list) else None},
            session=session,
        )
        return result
    except ValueError as error:
        audit.log_event("models", "save_models", "failed", detail={"error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        audit.log_event("models", "save_models", "failed", detail={"error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.post("/models/{name}/test")
async def test_model(name: str, session=Depends(manager_auth)):
    """测试指定模型配置。"""
    try:
        result = await llm_models.test_model(name)
        audit.log_event(
            "models", "test_model", "completed", detail={"name": name, "ok": result.get("ok")}, session=session
        )
        return result
    except KeyError as error:
        audit.log_event(
            "models", "test_model", "failed", detail={"name": name, "error": "Model config not found"}, session=session
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found") from error
    except Exception as error:  # noqa: BLE001
        audit.log_event("models", "test_model", "failed", detail={"name": name, "error": str(error)}, session=session)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.get("/agents/runs")
async def list_agent_runs(
    status: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """列出 Agent 运行记录。"""
    return await agents.list_runs(status=status, kind=kind, q=q, page=page, page_size=page_size)


@router.get("/agents/runs/{trace_id}")
async def get_agent_run(trace_id: str, _=Depends(manager_auth)):
    """读取单个 Agent 运行详情。"""
    try:
        return await agents.get_run(trace_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found") from error


@router.get("/agents/checkpoints")
async def list_agent_checkpoints(
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """列出 Agent 工作流检查点。"""
    return await agents.list_checkpoints(status=status, page=page, page_size=page_size)


@router.get("/agents/checkpoints/{user_id}")
async def get_agent_checkpoint(user_id: int, _=Depends(manager_auth)):
    """读取指定用户的 Agent 检查点。"""
    try:
        return await agents.get_checkpoint(user_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent checkpoint not found") from error


@router.delete("/agents/checkpoints/{user_id}")
async def delete_agent_checkpoint(user_id: int, _=Depends(manager_auth)):
    """删除指定用户的 Agent 检查点。"""
    try:
        return await agents.delete_checkpoint(user_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent checkpoint not found") from error


@router.get("/integrations")
async def integrations(_=Depends(manager_auth)):
    """返回集成页所需的第三方能力状态。"""
    status_payload = await get_status(["models", "cos", "ragflow"])
    return {
        "mcp": {
            "status": "planned",
            "message": "MCP registry is not implemented in the current repository.",
        },
        "ragflow": status_payload.get("ragflow", {}),
        "cos": status_payload.get("cos", {}),
        "models": status_payload.get("models", {}),
    }


@router.get("/nonebot")
async def nonebot_overview(_=Depends(manager_auth)):
    """返回 NoneBot 运行时总览。"""
    return nonebot_runtime.get_nonebot_overview()


@router.get("/nonebot/plugins")
async def list_nonebot_plugins(_=Depends(manager_auth)):
    """列出 NoneBot 插件清单。"""
    return nonebot_runtime.list_plugins()


@router.get("/nonebot/commands")
async def list_nonebot_commands(_=Depends(manager_auth)):
    """列出 NoneBot 命令清单。"""
    return nonebot_runtime.list_commands()


@router.get("/nonebot/adapters")
async def list_nonebot_adapters(_=Depends(manager_auth)):
    """列出 NoneBot 适配器清单。"""
    return nonebot_runtime.list_adapters()


@router.get("/nonebot/bots")
async def list_nonebot_bots(_=Depends(manager_auth)):
    """列出当前在线 Bot 清单。"""
    return nonebot_runtime.list_bots()


@router.get("/databases")
async def list_database_connections(_=Depends(manager_auth)):
    """列出管理端可用数据库连接。"""
    return await databases.list_connections()


@router.get("/databases/{database_id}/schema")
async def get_database_schema(
    database_id: str,
    schema: str | None = None,
    _=Depends(manager_auth),
):
    """读取数据库表结构和外键关系。"""
    try:
        return await databases.get_schema(database_id, schema=schema)
    except databases.DatabaseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found") from error


@router.get("/databases/{database_id}/tables")
async def list_database_tables(
    database_id: str,
    schema: str | None = None,
    _=Depends(manager_auth),
):
    """列出数据库表摘要。"""
    try:
        return await databases.list_tables(database_id, schema=schema)
    except databases.DatabaseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found") from error


@router.get("/databases/{database_id}/tables/{table_name}/rows")
async def get_database_table_rows(
    database_id: str,
    table_name: str,
    schema: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(manager_auth),
):
    """分页读取数据表中的数据行。"""
    try:
        return await databases.get_table_rows(
            database_id,
            table_name,
            schema=schema,
            page=page,
            page_size=page_size,
        )
    except databases.DatabaseNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found") from error
    except databases.TableNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found") from error


@router.patch("/databases/{database_id}/tables/{table_name}/rows")
async def update_database_table_row(
    database_id: str,
    table_name: str,
    payload: DatabaseRowUpdateRequest,
    schema: str | None = None,
    session=Depends(manager_auth),
):
    """更新数据表中的一行记录。"""
    try:
        result = await databases.update_table_row(
            database_id,
            table_name,
            pk=payload.pk,
            values=payload.values,
            schema=schema,
        )
        audit.log_event(
            "databases",
            "update_table_row",
            "completed",
            detail={"database_id": database_id, "schema": schema, "table": table_name},
            session=session,
        )
        return result
    except databases.DatabaseNotFoundError as error:
        audit.log_event(
            "databases",
            "update_table_row",
            "failed",
            detail={"database_id": database_id, "table": table_name, "error": "Database connection not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Database connection not found") from error
    except databases.TableNotFoundError as error:
        audit.log_event(
            "databases",
            "update_table_row",
            "failed",
            detail={"database_id": database_id, "table": table_name, "error": "Table not found"},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found") from error
    except databases.RowUpdateError as error:
        audit.log_event(
            "databases",
            "update_table_row",
            "failed",
            detail={"database_id": database_id, "table": table_name, "error": error.to_payload()},
            session=session,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error.to_payload(),
        ) from error
    except ValueError as error:
        audit.log_event(
            "databases",
            "update_table_row",
            "failed",
            detail={"database_id": database_id, "table": table_name, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/logs")
async def list_log_items(_=Depends(manager_auth)):
    """列出可读取的日志文件。"""
    return logs.list_logs()


@router.get("/logs/read")
async def read_log(
    path: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    _=Depends(manager_auth),
):
    """按偏移量读取日志。"""
    try:
        return logs.read_log(path, offset=offset, limit=limit)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/logs/tail")
async def tail_log(
    path: str,
    lines: int = Query(300, ge=1, le=2000),
    _=Depends(manager_auth),
):
    """读取日志末尾若干行。"""
    try:
        return logs.tail_log(path, lines=lines)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/operations/actions")
async def list_operation_actions(_=Depends(manager_auth)):
    """列出预置运维动作。"""
    return operations.list_actions()


@router.post("/operations/actions/{action_id}/run")
async def run_operation_action(action_id: str, session=Depends(manager_auth)):
    """执行预置运维动作。"""
    try:
        return await operations.run_action(action_id, session=session)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation action not found") from error


@router.get("/operations/terminal/commands")
async def list_terminal_commands(_=Depends(manager_auth)):
    """列出允许执行的预置终端命令。"""
    return operations.list_terminal_commands()


@router.post("/operations/terminal/commands/{command_id}/run")
async def run_terminal_command(command_id: str, session=Depends(manager_auth)):
    """执行预置终端命令。"""
    try:
        return await operations.run_terminal_command(command_id, session=session)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Terminal command not found") from error


@router.post("/operations/terminal/run")
async def execute_terminal_command(payload: TerminalExecuteRequest, session=Depends(manager_auth)):
    """执行前端输入的终端命令。"""
    try:
        return await operations.execute_terminal_command(
            payload.command,
            cwd=payload.cwd,
            timeout=payload.timeout,
            session=session,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/operations/scripts")
async def list_automation_scripts(_=Depends(manager_auth)):
    """列出自动化脚本库。"""
    return operations.list_automation_scripts()


@router.post("/operations/scripts")
async def create_automation_script(payload: AutomationScriptCreateRequest, session=Depends(manager_auth)):
    """创建自动化脚本。"""
    try:
        return operations.create_automation_script(payload.dict(exclude_unset=True), session=session)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.patch("/operations/scripts/{script_id}")
async def update_automation_script(
    script_id: str,
    payload: AutomationScriptUpdateRequest,
    session=Depends(manager_auth),
):
    """更新自动化脚本。"""
    try:
        return operations.update_automation_script(script_id, payload.dict(exclude_unset=True), session=session)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation script not found") from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/operations/scripts/{script_id}")
async def delete_automation_script(script_id: str, session=Depends(manager_auth)):
    """删除自动化脚本。"""
    try:
        return operations.delete_automation_script(script_id, session=session)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation script not found") from error


@router.post("/operations/scripts/{script_id}/run")
async def run_automation_script(script_id: str, session=Depends(manager_auth)):
    """执行自动化脚本。"""
    try:
        return await operations.run_automation_script(script_id, session=session)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation script not found") from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/operations/audit-log")
async def list_audit_log(
    event_type: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    _=Depends(manager_auth),
):
    """读取后台操作审计日志。"""
    return audit.list_events(limit=limit, event_type=event_type)
