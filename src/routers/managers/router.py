from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from . import agents, llm_models, logs, operations, prompts, settings_store, skills
from .schemas import (
    LoginRequest,
    TokenResponse,
    AdminPatchRequest,
    StatusCheckRequest,
    PromptUpdateRequest,
    SettingsPatchRequest,
    ModelSettingsRequest,
)
from .security import SESSION_TTL_SECONDS, manager_auth, manager_auth_token, token_store
from .status import get_status

router = APIRouter(prefix="/api/v1/manager", tags=["Manager"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    session_token, _ = token_store.login(payload.token)
    return TokenResponse(access_token=session_token, expires_in=SESSION_TTL_SECONDS)


@router.get("/auth/me")
async def auth_me(session=Depends(manager_auth)):
    return {
        "authenticated": True,
        "role": "local_manager",
        "issued_at": session.issued_at,
        "expires_at": session.expires_at,
    }


@router.post("/auth/logout")
async def logout(session_token: str = Depends(manager_auth_token)):
    token_store.logout(session_token)
    return {"logged_out": True}


@router.get("/overview")
async def overview(_=Depends(manager_auth)):
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
    return await get_status()


@router.post("/status/check")
async def status_check(payload: StatusCheckRequest, _=Depends(manager_auth)):
    return await get_status(payload.targets)


@router.get("/settings")
async def get_settings(_=Depends(manager_auth)):
    return settings_store.get_settings()


@router.patch("/settings")
async def update_settings(payload: SettingsPatchRequest, _=Depends(manager_auth)):
    try:
        return settings_store.update_settings(payload.dict(exclude_unset=True))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.post("/settings/security/rotate-token")
async def rotate_token(_=Depends(manager_auth)):
    token_store.rotate_startup_token(log_token=True)
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
    from .users import list_users as _list_users

    return await _list_users(q=q, role=role, is_admin=is_admin, page=page, page_size=page_size)


@router.get("/users/{user_id}")
async def get_user(user_id: int, _=Depends(manager_auth)):
    from .users import get_user_detail

    try:
        return await get_user_detail(user_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error


@router.patch("/users/{user_id}/admin")
async def patch_user_admin(user_id: int, payload: AdminPatchRequest, _=Depends(manager_auth)):
    from .users import set_user_admin

    try:
        return await set_user_admin(user_id, payload.is_admin)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from error


@router.delete("/users/{user_id}/binds/{bind_id}")
async def delete_user_bind(user_id: int, bind_id: int, _=Depends(manager_auth)):
    from .users import delete_user_bind as _delete_user_bind

    try:
        return await _delete_user_bind(user_id, bind_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bind not found") from error


@router.get("/skills")
async def list_skill_items(_=Depends(manager_auth)):
    return skills.list_skills()


@router.get("/skills/{name}")
async def get_skill(name: str, _=Depends(manager_auth)):
    try:
        return skills.get_skill(name)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found") from error


@router.post("/skills/reload")
async def reload_skills(_=Depends(manager_auth)):
    return skills.reload_skills()


@router.get("/prompts")
async def list_prompt_items(_=Depends(manager_auth)):
    return prompts.list_prompts()


@router.get("/prompts/{name}")
async def get_prompt(name: str, _=Depends(manager_auth)):
    try:
        return prompts.get_prompt(name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.put("/prompts/{name}")
async def update_prompt(name: str, payload: PromptUpdateRequest, _=Depends(manager_auth)):
    try:
        return prompts.update_prompt(name, payload.content)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.post("/prompts/{name}/validate")
async def validate_prompt(name: str, _=Depends(manager_auth)):
    try:
        return prompts.validate_prompt(name)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/models")
async def list_model_items(_=Depends(manager_auth)):
    return llm_models.list_models()


@router.put("/models")
async def save_model_items(payload: ModelSettingsRequest, _=Depends(manager_auth)):
    try:
        return llm_models.save_models(payload.dict(exclude_unset=True))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.post("/models/{name}/test")
async def test_model(name: str, _=Depends(manager_auth)):
    try:
        return await llm_models.test_model(name)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found") from error
    except Exception as error:  # noqa: BLE001
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
    return await agents.list_runs(status=status, kind=kind, q=q, page=page, page_size=page_size)


@router.get("/agents/runs/{trace_id}")
async def get_agent_run(trace_id: str, _=Depends(manager_auth)):
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
    return await agents.list_checkpoints(status=status, page=page, page_size=page_size)


@router.get("/agents/checkpoints/{user_id}")
async def get_agent_checkpoint(user_id: int, _=Depends(manager_auth)):
    try:
        return await agents.get_checkpoint(user_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent checkpoint not found") from error


@router.delete("/agents/checkpoints/{user_id}")
async def delete_agent_checkpoint(user_id: int, _=Depends(manager_auth)):
    try:
        return await agents.delete_checkpoint(user_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent checkpoint not found") from error


@router.get("/integrations")
async def integrations(_=Depends(manager_auth)):
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


@router.get("/logs")
async def list_log_items(_=Depends(manager_auth)):
    return logs.list_logs()


@router.get("/logs/read")
async def read_log(
    path: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    _=Depends(manager_auth),
):
    try:
        return logs.read_log(path, offset=offset, limit=limit)
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/operations/actions")
async def list_operation_actions(_=Depends(manager_auth)):
    return operations.list_actions()


@router.post("/operations/actions/{action_id}/run")
async def run_operation_action(action_id: str, _=Depends(manager_auth)):
    try:
        return await operations.run_action(action_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation action not found") from error
