from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from .. import audit
from ..runtime import command_state, nonebot
from ..schemas import AvailabilityUpdateRequest
from ..security import manager_auth

router = APIRouter()


@router.get("/nonebot")
async def nonebot_overview(_=Depends(manager_auth)):
    """返回 NoneBot 运行时总览。"""

    return nonebot.get_nonebot_overview()


@router.get("/nonebot/plugins")
async def list_nonebot_plugins(_=Depends(manager_auth)):
    """列出 NoneBot 插件清单。"""

    return nonebot.list_plugins()


@router.get("/nonebot/commands")
async def list_nonebot_commands(_=Depends(manager_auth)):
    """列出 NoneBot 命令清单。"""

    return nonebot.list_commands()


@router.get("/nonebot/availability")
async def get_nonebot_availability(_=Depends(manager_auth)):
    """读取命令与插件软开关状态。"""

    return command_state.availability_payload()


@router.patch("/nonebot/commands/{command_name}/availability")
async def update_nonebot_command_availability(
    command_name: str,
    payload: AvailabilityUpdateRequest,
    session=Depends(manager_auth),
):
    """更新一条命令的软开关状态。"""

    try:
        result = command_state.update_command_state(command_name, payload.enabled, payload.reason)
        audit.log_event(
            "nonebot",
            "update_command_availability",
            "completed",
            detail={"command": command_name, "enabled": payload.enabled},
            session=session,
        )
        return result
    except ValueError as error:
        audit.log_event(
            "nonebot",
            "update_command_availability",
            "failed",
            detail={"command": command_name, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.patch("/nonebot/plugins/{plugin_module}/availability")
async def update_nonebot_plugin_availability(
    plugin_module: str,
    payload: AvailabilityUpdateRequest,
    session=Depends(manager_auth),
):
    """更新一个插件模块的软开关状态。"""

    try:
        result = command_state.update_plugin_state(plugin_module, payload.enabled, payload.reason)
        audit.log_event(
            "nonebot",
            "update_plugin_availability",
            "completed",
            detail={"plugin_module": plugin_module, "enabled": payload.enabled},
            session=session,
        )
        return result
    except ValueError as error:
        audit.log_event(
            "nonebot",
            "update_plugin_availability",
            "failed",
            detail={"plugin_module": plugin_module, "error": str(error)},
            session=session,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.get("/nonebot/adapters")
async def list_nonebot_adapters(_=Depends(manager_auth)):
    """列出 NoneBot 适配器清单。"""

    return nonebot.list_adapters()


@router.get("/nonebot/bots")
async def list_nonebot_bots(_=Depends(manager_auth)):
    """列出当前在线 Bot 清单。"""

    return nonebot.list_bots()
