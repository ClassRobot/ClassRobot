from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .. import audit
from ..runtime import operations as operation_service
from ..schemas import AutomationScriptCreateRequest, AutomationScriptUpdateRequest, TerminalExecuteRequest
from ..security import manager_auth

router = APIRouter()


@router.get("/operations/actions")
async def list_operation_actions(_=Depends(manager_auth)):
    """列出预置运维动作。"""

    return operation_service.list_actions()


@router.post("/operations/actions/{action_id}/run")
async def run_operation_action(action_id: str, session=Depends(manager_auth)):
    """执行预置运维动作。"""

    try:
        return await operation_service.run_action(action_id, session=session)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation action not found") from error


@router.get("/operations/terminal/commands")
async def list_terminal_commands(_=Depends(manager_auth)):
    """列出允许执行的预置终端命令。"""

    return operation_service.list_terminal_commands()


@router.post("/operations/terminal/commands/{command_id}/run")
async def run_terminal_command(command_id: str, session=Depends(manager_auth)):
    """执行预置终端命令。"""

    try:
        return await operation_service.run_terminal_command(command_id, session=session)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Terminal command not found") from error


@router.post("/operations/terminal/run")
async def execute_terminal_command(payload: TerminalExecuteRequest, session=Depends(manager_auth)):
    """执行前端输入的终端命令。"""

    try:
        return await operation_service.execute_terminal_command(
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

    return operation_service.list_automation_scripts()


@router.post("/operations/scripts")
async def create_automation_script(payload: AutomationScriptCreateRequest, session=Depends(manager_auth)):
    """创建自动化脚本。"""

    try:
        return operation_service.create_automation_script(payload.dict(exclude_unset=True), session=session)
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
        return operation_service.update_automation_script(script_id, payload.dict(exclude_unset=True), session=session)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation script not found") from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/operations/scripts/{script_id}")
async def delete_automation_script(script_id: str, session=Depends(manager_auth)):
    """删除自动化脚本。"""

    try:
        return operation_service.delete_automation_script(script_id, session=session)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation script not found") from error


@router.post("/operations/scripts/{script_id}/run")
async def run_automation_script(script_id: str, session=Depends(manager_auth)):
    """执行自动化脚本。"""

    try:
        return await operation_service.run_automation_script(script_id, session=session)
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
